"""
Production-Grade Resolution Decision Engine

Deterministic First, Adaptive Second:
- Step A: Build Candidate Graph (structured clickable elements)
- Step B: Intent Classification (before scoring)
- Step C: Weighted Scoring (production formula, repeatable)
- Step D: Confidence Rule (intent-specific thresholds, single best candidate)
- Fallbacks: Reranking → Container Restriction → Coordinate Click → DOM Traversal
- Healing Agent only when all deterministic paths fail (<5% execution path).
"""
import json
import logging
import re
import time
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from playwright.async_api import Page, Locator

from .smart_resolver import (
    similarity,
    exact_word_match,
    partial_similarity,
    get_button_aliases,
    GENERIC_NAV_LINK_BLOCKLIST,
    _target_words,
    _link_text_has_target_word,
    _product_spec_penalty,
)

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """Target intent for scoring strategy and thresholds."""
    CATEGORY = "CATEGORY"
    SUBCATEGORY = "SUBCATEGORY"
    PRODUCT = "PRODUCT"
    PRIMARY_CTA = "PRIMARY_CTA"
    CHECKOUT_CTA = "CHECKOUT_CTA"
    AUTH_CTA = "AUTH_CTA"
    OPTION = "OPTION"
    GENERIC = "GENERIC"


# Intent-specific minimum scores (no second candidate; fail with structured error if below)
INTENT_THRESHOLDS = {
    IntentType.CATEGORY: 0.35,
    IntentType.SUBCATEGORY: 0.35,
    IntentType.PRODUCT: 0.40,
    IntentType.PRIMARY_CTA: 0.45,
    IntentType.CHECKOUT_CTA: 0.50,
    IntentType.AUTH_CTA: 0.45,
    IntentType.OPTION: 0.40,
    IntentType.GENERIC: 0.35,
}

# Strong confidence gate (enterprise: don't click weak match — fail or use fallback only)
# If best_score >= threshold but < STRONG, we try coordinate/DOM fallback only; no selector click
STRONG_CONFIDENCE = {
    IntentType.CATEGORY: 0.50,
    IntentType.SUBCATEGORY: 0.50,
    IntentType.PRODUCT: 0.52,
    IntentType.PRIMARY_CTA: 0.55,
    IntentType.CHECKOUT_CTA: 0.58,
    IntentType.AUTH_CTA: 0.55,
    IntentType.OPTION: 0.52,
    IntentType.GENERIC: 0.50,
}

# E2: config path for tunable thresholds
_RESOLUTION_CONFIG_PATH = Path(__file__).resolve().parent / "flow_config" / "resolution_config.json"


def _get_thresholds() -> Tuple[Dict[IntentType, float], Dict[IntentType, float]]:
    """E2: Load thresholds from config if present; else use module defaults."""
    thresh = dict(INTENT_THRESHOLDS)
    strong = dict(STRONG_CONFIDENCE)
    try:
        if _RESOLUTION_CONFIG_PATH.exists():
            with open(_RESOLUTION_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in (cfg.get("intent_thresholds") or {}).items():
                try:
                    thresh[IntentType(k)] = float(v)
                except (ValueError, KeyError):
                    pass
            for k, v in (cfg.get("strong_confidence") or {}).items():
                try:
                    strong[IntentType(k)] = float(v)
                except (ValueError, KeyError):
                    pass
    except Exception:
        pass
    return thresh, strong


@dataclass
class CandidateNode:
    """Single clickable element in the candidate graph. B1: rich fingerprint for multi-attribute scoring."""
    id: str = ""
    text: str = ""
    role: str = ""
    tag: str = ""
    visible: bool = True
    bounding_box: Optional[Dict[str, float]] = None
    parent_container: str = ""
    aria_label: str = ""
    href: str = ""
    is_primary_button: bool = False
    in_main_section: bool = False
    semantic_type: str = ""  # button, link, product_card
    locator: Any = field(default=None, repr=False)  # Playwright Locator for click
    selector: Optional[str] = None
    # B1: rich fingerprint
    data_testid: str = ""
    aria_describedby: str = ""
    placeholder: str = ""
    name: str = ""
    type: str = ""  # input type, etc.
    alt: str = ""
    ancestor_path: str = ""  # e.g. "main>div.content>div.card" (3 levels up tag+class)
    ordinal_in_section: int = 0  # 1-based index among same semantic_type in same container


def _normalize_target(target: str) -> str:
    """Normalize target for cache key and comparison."""
    return (target or "").strip().lower()[:200]


async def build_candidate_graph(page: Page, scope_locator: Any = None) -> List[CandidateNode]:
    """
    Step A — Build Candidate Graph. C2: when scope_locator set, restrict to descendants (anchor-based).
    """
    root = scope_locator if scope_locator is not None else page
    candidates: List[CandidateNode] = []
    seen_keys: set = set()

    async def add_from_locator(locator, semantic_type: str):
        try:
            elements = await locator.all()
            for el in elements:
                try:
                    text = (await el.inner_text(timeout=300)).strip()
                    tag = await el.evaluate("el => el.tagName ? el.tagName.toLowerCase() : ''")
                    role = await el.get_attribute("role") or ""
                    aria_label = await el.get_attribute("aria-label") or ""
                    href = await el.get_attribute("href") or ""
                    elem_id = await el.get_attribute("id") or ""
                    data_testid = await el.get_attribute("data-testid") or await el.get_attribute("data-test-id") or ""
                    aria_describedby = await el.get_attribute("aria-describedby") or ""
                    placeholder = await el.get_attribute("placeholder") or ""
                    name = await el.get_attribute("name") or ""
                    type_attr = await el.get_attribute("type") or ""
                    alt = await el.get_attribute("alt") or ""

                    try:
                        box = await el.evaluate("""el => {
                            const r = el.getBoundingClientRect();
                            return { x: r.x, y: r.y, width: r.width, height: r.height };
                        }""")
                    except Exception:
                        box = None

                    try:
                        in_main = await el.evaluate("""el => {
                            const m = el.closest('main, #main, [class*="content"], [class*="main"], [role="main"], [class*="product"], [class*="checkout"]');
                            return !!m;
                        }""")
                    except Exception:
                        in_main = False

                    try:
                        visible = await el.evaluate("""el => {
                            const r = el.getBoundingClientRect();
                            const style = window.getComputedStyle(el);
                            return r.width > 0 && r.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
                        }""")
                    except Exception:
                        visible = True

                    try:
                        in_viewport = await el.evaluate("""el => {
                            const r = el.getBoundingClientRect();
                            return r.top >= 0 && r.left >= 0 && r.bottom <= window.innerHeight && r.right <= window.innerWidth;
                        }""")
                    except Exception:
                        in_viewport = False
                    if not visible:
                        continue

                    # Dedupe by (tag, text slice)
                    key = (tag, (text or aria_label or href)[:80])
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    is_primary = bool(
                        role == "button"
                        or "primary" in (await el.get_attribute("class") or "").lower()
                        or "btn-primary" in (await el.get_attribute("class") or "").lower()
                    )
                    if semantic_type == "button" and not role:
                        role = "button"

                    try:
                        sel = await el.evaluate("""el => {
                            if (el.id && !el.id.match(/^\\d/)) return '#' + el.id;
                            const c = (el.className && typeof el.className === 'string') ? el.className.trim().split(/\\s+/).filter(Boolean).slice(0, 2).join('.') : '';
                            if (c) return el.tagName.toLowerCase() + '.' + c.replace(/\\./g, '.');
                            return el.tagName ? el.tagName.toLowerCase() : 'div';
                        }""")
                    except Exception:
                        sel = None

                    # B1: ancestor path (3 levels) and ordinal in section (1-based index of same tag in container)
                    ancestor_path = ""
                    ordinal_in_section = 0
                    try:
                        anc_ord = await el.evaluate("""el => {
                            const getPath = (e, depth) => {
                                let path = [], node = e;
                                for (let i = 0; i < depth && node; i++) {
                                    const tag = node.tagName ? node.tagName.toLowerCase() : '';
                                    const cls = (node.className && typeof node.className === 'string') ? node.className.trim().split(/\\s+/)[0] : '';
                                    path.push(cls ? tag + '.' + cls : tag);
                                    node = node.parentElement;
                                }
                                return path.reverse().join('>');
                            };
                            const parent = el.closest('main, [class*="content"], [class*="product"], [class*="checkout"], [role="main"]') || el.parentElement;
                            let ord = 0;
                            if (parent) {
                                const sameTag = Array.from(parent.querySelectorAll(el.tagName || '*')).filter(n => parent.contains(n) && n.tagName === el.tagName);
                                const idx = sameTag.indexOf(el);
                                ord = idx >= 0 ? idx + 1 : 0;
                            }
                            return { path: getPath(el, 3), ordinal: ord };
                        }""")
                        ancestor_path = anc_ord.get("path", "") or ""
                        ordinal_in_section = int(anc_ord.get("ordinal", 0) or 0)
                    except Exception:
                        pass

                    node = CandidateNode(
                        id=elem_id,
                        text=text or aria_label or "",
                        role=role or tag,
                        tag=tag,
                        visible=visible,
                        bounding_box=box,
                        parent_container="",
                        aria_label=aria_label,
                        href=href,
                        is_primary_button=is_primary,
                        in_main_section=bool(in_main),
                        semantic_type=semantic_type,
                        locator=el,
                        selector=sel,
                        data_testid=data_testid,
                        aria_describedby=aria_describedby,
                        placeholder=placeholder,
                        name=name,
                        type=type_attr,
                        alt=alt,
                        ancestor_path=ancestor_path,
                        ordinal_in_section=ordinal_in_section,
                    )
                    candidates.append(node)
                except Exception as e:
                    logger.debug(f"Skip element: {e}")
                    continue
        except Exception as e:
            logger.debug(f"build_candidate_graph locator error: {e}")

    # Buttons and button-like (C2: root = page or container)
    await add_from_locator(root.locator("button:visible, [role='button']:visible"), "button")
    await add_from_locator(root.locator("a[href]:visible"), "link")
    await add_from_locator(
        root.locator("div[class*='product']:visible, article[class*='product']:visible, a[class*='product']:visible, [data-product]:visible"),
        "product_card",
    )

    logger.debug(f"Candidate graph: {len(candidates)} nodes")
    return candidates


def classify_intent(target: str, step_intent: Optional[str] = None) -> IntentType:
    """
    Step B — Intent Classification.
    Determines scoring strategy and minimum threshold.
    """
    t = (target or "").lower()
    step = (step_intent or "").lower()

    if "checkout" in t or "checkout" in step:
        return IntentType.CHECKOUT_CTA
    if "guest" in t or "guest" in step or "continue as guest" in t:
        return IntentType.AUTH_CTA
    if any(k in t for k in ["buy now", "buy now", "add to cart", "add to bag", "purchase"]):
        return IntentType.PRIMARY_CTA
    if any(k in t for k in ["free delivery", "free shipping", "standard delivery", "delivery"]):
        return IntentType.OPTION
    if any(k in t for k in ["star", "ac", "split", "lg", "samsung", "product", "model", "kw", "ton", "btu"]):
        return IntentType.PRODUCT
    if any(k in t for k in ["air", "solution", "conditioner", "category", "appliances"]):
        if any(k in t for k in ["split", "window", "duct"]):
            return IntentType.SUBCATEGORY
        return IntentType.CATEGORY
    return IntentType.GENERIC


def _word_overlap_score(target: str, text: str) -> float:
    """Word overlap component (0–1)."""
    if not target or not text:
        return 0.0
    tw = _target_words(target)
    if not tw:
        return 0.5
    text_words = set(re.findall(r"\b\w+\b", text.lower()))
    matches = sum(1 for w in tw if w in text_words)
    return min(1.0, matches / len(tw) * 1.2)


def _candidate_fingerprint(candidate: CandidateNode) -> Dict[str, Any]:
    """B3: fingerprint for element history matching."""
    return {
        "data_testid": candidate.data_testid or "",
        "aria_label": candidate.aria_label or "",
        "ancestor_path": candidate.ancestor_path or "",
        "ordinal_in_section": candidate.ordinal_in_section or 0,
        "tag": candidate.tag or "",
        "role": candidate.role or "",
        "text_preview": (candidate.text or "")[:80],
    }


def production_weighted_score(
    candidate: CandidateNode,
    target: str,
    intent_type: IntentType,
    section_hint: Optional[str] = None,
    ordinal: Optional[int] = None,
    stored_fingerprint: Optional[Dict[str, Any]] = None,
    a11y_role_name_set: Optional[set] = None,
) -> float:
    """
    Step C — Production weighted scoring. B2: multi-attribute boost (data-testid, aria-label, ancestor, ordinal).
    final_score =
      semantic_similarity * 0.45 +
      word_overlap_score * 0.20 +
      role_weight * 0.10 +
      container_weight * 0.10 +
      visual_position_weight * 0.05 +
      primary_button_weight * 0.10 +
      (optional boosts: data_testid/aria match, ancestor match, ordinal match)
    """
    text = (candidate.text or candidate.aria_label or "").strip()
    target_aliases = get_button_aliases(target)
    best_semantic = 0.0
    for alias in target_aliases:
        word_match = exact_word_match(alias, text)
        full = similarity(alias, text)
        partial = partial_similarity(alias, text)
        sub = 0.85 if (alias in (text or "").lower() or (text or "").lower() in alias) else 0.0
        best_semantic = max(best_semantic, word_match, full, partial, sub)
    if intent_type == IntentType.PRODUCT and len(target) > 30 and len(text) > 30:
        best_semantic *= _product_spec_penalty(target, text)

    word_overlap = _word_overlap_score(target, text)

    role_weight = 1.0 if candidate.semantic_type in ("button", "link") else 0.6
    if intent_type in (IntentType.PRIMARY_CTA, IntentType.CHECKOUT_CTA, IntentType.AUTH_CTA):
        if candidate.semantic_type == "button" or candidate.role == "button":
            role_weight = 1.0
        else:
            role_weight = 0.7

    container_weight = 1.0 if candidate.in_main_section else 0.5

    # Visual position: prefer viewport (we don't have in_viewport on node; use bbox)
    visual_position_weight = 0.7
    if candidate.bounding_box:
        try:
            # Assume viewport ~ 1920x1080 or page size; center-ish is good
            x, y = candidate.bounding_box.get("x", 0), candidate.bounding_box.get("y", 0)
            if 0 <= x <= 2000 and 0 <= y <= 1500:
                visual_position_weight = 1.0
        except Exception:
            pass

    primary_button_weight = 1.0 if candidate.is_primary_button else 0.5
    if intent_type in (IntentType.PRIMARY_CTA, IntentType.CHECKOUT_CTA, IntentType.AUTH_CTA):
        primary_button_weight = 1.0 if candidate.is_primary_button or "button" in (candidate.role or "") else 0.6

    # Blocklist for category/product/CTA: skip generic nav links
    if intent_type in (IntentType.CATEGORY, IntentType.SUBCATEGORY, IntentType.PRODUCT, IntentType.PRIMARY_CTA, IntentType.CHECKOUT_CTA):
        if text.lower().strip() in GENERIC_NAV_LINK_BLOCKLIST:
            return 0.0
        if candidate.semantic_type == "link" and _target_words(target) and not _link_text_has_target_word(text, _target_words(target)):
            return 0.0

    semantic_similarity = min(1.0, best_semantic)
    score = (
        semantic_similarity * 0.45
        + min(1.0, word_overlap) * 0.20
        + min(1.0, role_weight) * 0.10
        + min(1.0, container_weight) * 0.10
        + min(1.0, visual_position_weight) * 0.05
        + min(1.0, primary_button_weight) * 0.10
    )
    # B2: multi-attribute boost
    target_lower = (target or "").lower()
    if (candidate.data_testid or candidate.aria_label) and target_lower:
        attr_text = (candidate.data_testid or candidate.aria_label or "").lower()
        if target_lower in attr_text or any(w in attr_text for w in _target_words(target)):
            score += 0.15
    if section_hint and candidate.ancestor_path and section_hint.lower() in candidate.ancestor_path.lower():
        score += 0.08
    if ordinal and candidate.ordinal_in_section == ordinal:
        score += 0.12
    # B3: element history — boost when candidate matches last successful fingerprint
    if stored_fingerprint:
        try:
            from .element_history import fingerprint_match_score
            cand_fp = _candidate_fingerprint(candidate)
            match = fingerprint_match_score(cand_fp, stored_fingerprint.get("fingerprint") or stored_fingerprint)
            if match > 0:
                score += 0.12 * match
        except Exception:
            pass
    # D3: accessibility tree — small boost when candidate matches an a11y node (role + name)
    if a11y_role_name_set and (candidate.text or candidate.aria_label):
        cand_role = (candidate.role or candidate.semantic_type or "").strip().lower()
        cand_name = (candidate.text or candidate.aria_label or "").strip().lower()
        if cand_role and cand_name and (
            (cand_role, cand_name) in a11y_role_name_set
            or (cand_role, cand_name[:80]) in a11y_role_name_set
        ):
            score += 0.05
    return min(1.0, score)


def _apply_container_restriction(candidates: List[Tuple[CandidateNode, float]], restrict_to_main: bool) -> List[Tuple[CandidateNode, float]]:
    """Fallback 2: keep only main section / product grid / checkout container."""
    if not restrict_to_main:
        return candidates
    return [(c, s) for c, s in candidates if c.in_main_section]


def _rerank_candidates(
    candidates: List[Tuple[CandidateNode, float]],
    target: str,
    intent_type: IntentType,
    remove_generic_nav: bool = True,
    increase_word_overlap: bool = False,
) -> List[Tuple[CandidateNode, float]]:
    """Fallback 1: remove generic nav, optionally increase word-overlap weight (re-score)."""
    if remove_generic_nav:
        filtered = []
        target_w = _target_words(target)
        for c, s in candidates:
            if c.text.lower().strip() in GENERIC_NAV_LINK_BLOCKLIST:
                continue
            if c.semantic_type == "link" and target_w and not _link_text_has_target_word(c.text, target_w):
                continue
            filtered.append((c, s))
        candidates = filtered if filtered else candidates
    if increase_word_overlap:
        # Re-score with higher word overlap (simplified: boost score if word overlap is high)
        def boosted(c: CandidateNode, s: float) -> float:
            wo = _word_overlap_score(target, c.text or "")
            return min(1.0, s + wo * 0.15)
        candidates = [(c, boosted(c, s)) for c, s in candidates]
        candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates


async def _click_by_coordinates(page: Page, candidate: CandidateNode) -> bool:
    """Fallback 3: click at bounding box center (no selector)."""
    if not candidate.bounding_box:
        return False
    try:
        x = candidate.bounding_box.get("x", 0) + candidate.bounding_box.get("width", 0) / 2
        y = candidate.bounding_box.get("y", 0) + candidate.bounding_box.get("height", 0) / 2
        await page.mouse.click(x, y)
        return True
    except Exception as e:
        logger.debug(f"Coordinate click failed: {e}")
        return False


async def _dom_traversal_click(page: Page, target: str, intent_type: IntentType) -> bool:
    """
    Fallback 4: DOM relationship — e.g. find product card container, then CTA inside.
    """
    target_lower = target.lower()
    if "buy now" in target_lower or "add to cart" in target_lower:
        # Find product card / main product section, then button inside
        containers = await page.locator("[class*='product']:visible, [class*='detail']:visible, main:visible").all()
        for cont in containers[:5]:
            try:
                btn = cont.locator("button:has-text('Buy'), button:has-text('Add to Cart'), [role='button']:has-text('Buy')").first
                if await btn.count() > 0:
                    await btn.scroll_into_view_if_needed(timeout=2000)
                    await btn.click(timeout=3000)
                    return True
            except Exception:
                continue
    return False


async def _container_for_section(page: Page, section_hint: str) -> Any:
    """C2: Resolve container locator from section hint (e.g. checkout -> [class*='checkout'])."""
    if not section_hint:
        return None
    hint = section_hint.replace("_", " ").lower()
    selectors = []
    if "product" in hint:
        selectors.append("[class*='product']")
    if "checkout" in hint:
        selectors.append("[class*='checkout']")
    if "form" in hint:
        selectors.append("form")
    if "main" in hint or "content" in hint:
        selectors.append("main")
        selectors.append("[role='main']")
    if not selectors:
        selectors = ["main", "[class*='content']", "[role='main']"]
    try:
        combined = ", ".join(selectors[:3])
        loc = page.locator(combined)
        if await loc.count() > 0:
            return loc.first
    except Exception:
        pass
    return None


async def _get_a11y_role_name_set(page: Page) -> set:
    """D3: Collect (role, name) from page accessibility snapshot for score boost."""
    out: set = set()
    try:
        snapshot = await page.accessibility.snapshot(interesting_only=True)
        if not snapshot:
            return out

        def _collect(node: Optional[Dict[str, Any]]) -> None:
            if not node:
                return
            role = (node.get("role") or "").strip().lower()
            name = (node.get("name") or "").strip()
            if role and name:
                name_lower = name.lower()
                out.add((role, name_lower))
                if len(name_lower) > 80:
                    out.add((role, name_lower[:80]))
            for ch in node.get("children") or []:
                _collect(ch)

        _collect(snapshot)
    except Exception as e:
        logger.debug("a11y snapshot failed: %s", e)
    return out


async def resolve_click(
    page: Page,
    target: str,
    intent_type: Optional[IntentType] = None,
    step_intent: Optional[str] = None,
    section_hint: Optional[str] = None,
    ordinal: Optional[int] = None,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Resolution Decision Engine entry: single best candidate, confidence rule, then fallbacks.
    B2/C1/C3: section_hint and ordinal used for multi-attribute scoring. C2: scope graph to container when section_hint set.
    """
    start_ts = time.perf_counter()
    intent_type = intent_type or classify_intent(target, step_intent)
    thresh_map, strong_map = _get_thresholds()
    threshold = thresh_map.get(intent_type, 0.35)

    # D1: learned wait — wait up to p95 of past success delays before building graph
    try:
        from .element_history import ElementHistory
        learned_ms = ElementHistory().get_learned_wait_ms(page.url, intent_type.value, _normalize_target(target))
        if learned_ms and learned_ms > 600:
            await page.wait_for_timeout(learned_ms)
    except Exception:
        pass

    scope = await _container_for_section(page, section_hint or "") if section_hint else None
    candidates_raw = await build_candidate_graph(page, scope_locator=scope)
    if not candidates_raw:
        logger.warning("Candidate graph empty")
        return False, None, None

    # B3: get stored fingerprint for this step (if any)
    stored_fp = None
    try:
        from .element_history import ElementHistory
        norm = _normalize_target(target)
        hist = ElementHistory()
        stored_fp = hist.get(page.url, intent_type.value, norm)
    except Exception:
        pass

    # D3: optional a11y snapshot for role+name score boost
    a11y_set: set = set()
    try:
        a11y_set = await _get_a11y_role_name_set(page)
    except Exception:
        pass

    scored: List[Tuple[CandidateNode, float]] = []
    for c in candidates_raw:
        s = production_weighted_score(
            c, target, intent_type,
            section_hint=section_hint, ordinal=ordinal,
            stored_fingerprint=stored_fp,
            a11y_role_name_set=a11y_set if a11y_set else None,
        )
        if s > 0:
            scored.append((c, s))
    scored.sort(key=lambda x: x[1], reverse=True)

    # Single best candidate only
    if not scored:
        logger.warning("No scored candidates")
        return False, None, None

    best_candidate, best_score = scored[0]
    if best_score < threshold:
        logger.warning(f"Best score {best_score:.2f} below threshold {threshold} for intent {intent_type.value}")
        # Fallback 1: contextual reranking
        scored = _rerank_candidates(scored, target, intent_type, remove_generic_nav=True, increase_word_overlap=True)
        if scored:
            best_candidate, best_score = scored[0]
        if best_score < threshold:
            # Fallback 2: container restriction
            restricted = _apply_container_restriction(scored, restrict_to_main=True)
            if restricted:
                best_candidate, best_score = restricted[0]
            if best_score < threshold:
                # E3: structured error for debugging/tuning
                err_info = {
                    "error": "below_threshold",
                    "intent_type": intent_type.value,
                    "best_score": best_score,
                    "threshold": threshold,
                    "candidate_count": len(scored),
                    "top_candidates": [(c.text or c.aria_label or "")[:50] for c, _ in scored[:3]],
                }
                return False, None, err_info

    strong = strong_map.get(intent_type, 0.50)
    # Enterprise: don't selector-click on weak match; try coordinate/DOM only, else fail with structured error
    use_selector_click = best_score >= strong
    if not use_selector_click:
        logger.warning(f"Best score {best_score:.2f} below strong confidence {strong}; trying coordinate/DOM fallback only")

    # Execute: selector click only if strong match; else try coordinate then DOM
    # A3: Playwright actionability — wait for visible/attached before click; rely on click() built-in auto-wait
    if use_selector_click:
        try:
            await best_candidate.locator.scroll_into_view_if_needed(timeout=2000)
            await best_candidate.locator.wait_for(state="visible", timeout=3000)
            await page.wait_for_timeout(200)  # minimal stability; Playwright click() does actionability
            await best_candidate.locator.click(timeout=3000)
            logger.info(f"Clicked (resolution engine): '{best_candidate.text[:50]}' score={best_score:.2f}")
            duration_ms = int((time.perf_counter() - start_ts) * 1000)
            info = {
                "selector": best_candidate.selector or f"{best_candidate.tag}:has-text('{(best_candidate.text or '')[:50]}')",
                "bounding_box": best_candidate.bounding_box,
                "in_main_section": best_candidate.in_main_section,
                "intent_type": intent_type.value,
                "fingerprint": _candidate_fingerprint(best_candidate),
                "duration_ms": duration_ms,
            }
            return True, best_candidate.selector, info
        except Exception as e:
            logger.debug(f"Click failed: {e}")
    # Fallback 3: coordinate click
    if await _click_by_coordinates(page, best_candidate):
        info = {"selector": None, "bounding_box": best_candidate.bounding_box, "intent_type": intent_type.value}
        return True, None, info
    # Fallback 4: DOM traversal
    if await _dom_traversal_click(page, target, intent_type):
        return True, None, {"intent_type": intent_type.value}
    # E3: structured error when best match was below strong or fallbacks failed
    err_info = {
        "error": "fallbacks_failed",
        "intent_type": intent_type.value,
        "best_score": best_score,
        "strong_confidence": strong,
        "candidate_count": len(scored),
        "top_candidates": [(c.text or c.aria_label or "")[:50] for c, _ in scored[:3]],
    }
    if not use_selector_click:
        logger.warning(f"Structured fail: best_score={best_score:.2f} < strong={strong} for intent {intent_type.value}")
    return False, None, err_info


async def resolve_click_with_fallbacks(
    page: Page,
    target: str,
    step_intent: Optional[str] = None,
    section_hint: Optional[str] = None,
    ordinal: Optional[int] = None,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Full chain: Resolution Engine → Rerank (on fail) → Container Restriction → Coordinate → DOM Traversal.
    Does NOT call Healing Agent; caller uses this then escalates to healing only if all fail.
    """
    intent_type = classify_intent(target, step_intent)
    # First attempt
    ok, selector, info = await resolve_click(
        page, target, intent_type, step_intent, section_hint=section_hint, ordinal=ordinal
    )
    if ok:
        return True, selector, info
    # Already did rerank/container inside resolve_click when below threshold; try coordinate/DOM again with fresh graph
    stored_fp = None
    try:
        from .element_history import ElementHistory
        hist = ElementHistory()
        stored_fp = hist.get(page.url, intent_type.value, _normalize_target(target))
    except Exception:
        pass
    candidates_raw = await build_candidate_graph(page)
    def _score(c):
        return production_weighted_score(
            c, target, intent_type,
            section_hint=section_hint, ordinal=ordinal,
            stored_fingerprint=stored_fp,
        )
    scored = [(c, _score(c)) for c in candidates_raw if _score(c) > 0]
    scored.sort(key=lambda x: x[1], reverse=True)
    if scored:
        best_candidate, _ = scored[0]
        if await _click_by_coordinates(page, best_candidate):
            return True, None, {"bounding_box": best_candidate.bounding_box}
        if await _dom_traversal_click(page, target, intent_type):
            return True, None, {}
    return False, None, None
