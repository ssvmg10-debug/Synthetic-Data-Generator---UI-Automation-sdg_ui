"""
Adapter: PlannerAgent plan (dict) → TestCase for DeterministicExecutorV2.
Keeps all V2 fixes; planning can come from Planner when use_planner_agents=True.
Combined workflow: enrich_plan_with_generator_selectors adds GeneratorAgent's layered
selectors (registry + AKE + step selectors) so V2 tries them first during execution.
"""
import logging
import re
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from .test_model import TestCase, TestStep, StepType, Intent

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Map Planner step "intent" (string) to executor Intent enum
PLAN_INTENT_TO_EXECUTOR: Dict[str, Intent] = {
    "search_box": Intent.SEARCH,
    "search_submit": Intent.CLICK,
    "search_icon": Intent.CLICK,
    "cookie_accept": Intent.CLICK,
    "login": Intent.CLICK,
    "product_select": Intent.CLICK,
    "select_product_with_condition": Intent.CLICK,
    "add_to_cart": Intent.ADD_TO_CART,
    "cart": Intent.CLICK,
    "checkout": Intent.CHECKOUT,
    "guest_checkout": Intent.CONTINUE_AS_GUEST,
    "email_field": Intent.FILL_EMAIL,
    "pincode_zip": Intent.FILL_PINCODE,
    "billing_shipping": Intent.FILL_FORM,
    "pay_now": Intent.CLICK,
    "menu_shop": Intent.CLICK,
    "generic_click": Intent.CLICK,
    "generic_type": Intent.TYPE,
}


def _plan_action_to_step_type(action: str) -> StepType:
    action = (action or "click").strip().lower()
    if action in ("navigate", "goto"):
        return StepType.NAVIGATION
    if action in ("type", "fill"):
        return StepType.INPUT
    if action in ("verify", "check", "assert", "validate"):
        return StepType.ASSERTION
    if action == "wait":
        return StepType.WAIT
    return StepType.ACTION


def _plan_step_to_intent(step: Dict[str, Any], action: str) -> Intent:
    # Prioritize action for navigate/goto so step 1 is always GOTO (page.goto), not TYPE
    action = (action or "").strip().lower()
    if action in ("navigate", "goto"):
        return Intent.GOTO
    if action in ("type", "fill"):
        return Intent.TYPE
    if action in ("verify", "check", "assert"):
        return Intent.PAGE_LOADED
    if action == "wait":
        return Intent.WAIT
    intent_str = (step.get("intent") or "").strip().lower()
    if intent_str and intent_str in PLAN_INTENT_TO_EXECUTOR:
        return PLAN_INTENT_TO_EXECUTOR[intent_str]
    return Intent.CLICK


def _extract_url_from_text(text: str) -> Optional[str]:
    """Extract first http(s) URL from text. Handles LLM output like 'navigate to https://www.lg.com/in'."""
    if not text or not isinstance(text, str):
        return None
    m = re.search(r"https?://[^\s<>\"')\]]+", text.strip())
    return m.group(0).rstrip(".,;") if m else None


def _normalize_click_target(target: Optional[str]) -> Optional[str]:
    """
    Normalize CLICK/action targets for site_knowledge and element_resolver.
    Strips LLM suffixes (menu, button, link, etc.) so 'Air Solutions menu' -> 'Air Solutions'.
    Also normalizes guest checkout and other common phrases.
    """
    if not target or not isinstance(target, str):
        return target
    t = target.strip()
    # Guest checkout: "continue with this condition (complete purchase as guest)" -> "continue as guest"
    if "guest" in t.lower() and ("continue" in t.lower() or "condition" in t.lower()):
        t = "continue as guest"
    else:
        # Strip trailing parentheticals
        t = re.sub(r"\s*\([^)]*\)\s*$", "", t).strip() or t
    suffixes = (
        " menu", " button", " link", " option", " item", " tab", " icon",
        " checkbox", " banner", " filter", " in delivery method",
        " option in delivery method",
    )
    for suffix in suffixes:
        if t.lower().endswith(suffix) and len(t) > len(suffix):
            t = t[: -len(suffix)].strip()
            break
    # V3: "Product card" / "any one product" / "first product" → "any product" for listing-page clicks
    product_aliases = ("product card", "any one product", "first product", "one product", "any product card")
    if t and t.lower().strip() in product_aliases:
        t = "any product"
    return t if t else target.strip()


def _plan_step_to_target(step: Dict[str, Any], action: str, intent: Intent) -> Optional[str]:
    element = (step.get("element") or "").strip()
    desc = (step.get("description") or "").strip()

    # Navigation: prefer explicit URL/value; never keep "Click ..." descriptions as target
    if intent == Intent.GOTO:
        raw = (step.get("value") or "").strip() or None
        if raw and raw.startswith(("http://", "https://")):
            return raw
        # LLM may put "navigate to https://..." in value/description; extract URL
        return _extract_url_from_text(raw or desc) or raw or None

    # For non-navigation, prefer structured element field when present
    if element:
        return element

    if intent == Intent.FILL_PINCODE:
        return "pincode"
    if intent == Intent.SEARCH:
        return "search"
    # V3: TYPE step — normalize "type X in search input" to target "search" so resolver finds search box
    if intent == Intent.TYPE:
        combined = f"{(element or '')} {(desc or '')}".lower()
        if "search" in combined and any(x in combined for x in ("input", "box", "field", "query")):
            return "search"

    # Shorten "Click ..."/"Type ..."/etc. from description so target is just the label
    for prefix in ("Click ", "click ", "Type ", "type ", "Fill ", "fill ", "Select ", "select "):
        if desc.startswith(prefix) and len(desc) > len(prefix):
            return desc[len(prefix):].strip()
    return desc or None


def enrich_plan_with_elr(plan: Dict[str, Any], page_url: Optional[str] = None) -> Dict[str, Any]:
    """
    V3 Locator Enrichment Layer: for each step with target + intent, lookup ELR and inject
    locator_candidates (ordered selectors) and elr_lookup_key so executor tries deterministic first.
    """
    if not plan or not plan.get("steps"):
        return plan
    url = (page_url or plan.get("url") or "").strip() or "https://example.com"
    try:
        from .locator_registry import locator_registry, get_elr_lookup_key
    except ImportError:
        return plan
    for step in plan.get("steps", []):
        if not isinstance(step, dict):
            continue
        action = (step.get("action") or "click").strip().lower()
        intent = _plan_step_to_intent(step, action)
        target = _plan_step_to_target(step, action, intent)
        if intent == Intent.GOTO or not target:
            continue
        target = _normalize_click_target(target) or target
        intent_str = intent.value if hasattr(intent, "value") else str(intent)
        entry = locator_registry.get(url, target, intent_str)
        if entry:
            step["locator_candidates"] = locator_registry.get_all_selectors_ordered(entry)
            step["elr_lookup_key"] = get_elr_lookup_key(url, target, intent_str)
            step["elr_entry"] = entry
    return plan


def enrich_plan_with_generator_selectors(plan: Dict[str, Any], db: Optional["Session"] = None) -> Dict[str, Any]:
    """
    Enrich each step in the plan with generator_selectors (same layered list
    GeneratorAgent would use: registry + AKE + step selectors). Used by the
    combined workflow so V2 executor can try these selectors first.
    """
    if not plan or not plan.get("steps"):
        return plan
    try:
        from services.ui_automation.agents.generator.agent import _get_selectors_list
        from services.ui_automation.registry import get_registry_selectors
    except ImportError:
        return plan
    url = (plan.get("url") or "").strip() or "https://example.com"
    ake_map = None
    for step in plan.get("steps", []):
        if not isinstance(step, dict):
            continue
        registry_list: List[str] = []
        if db:
            try:
                registry_list = get_registry_selectors(db, url, step.get("intent")) or []
            except Exception:
                registry_list = []
        selectors = _get_selectors_list(step, ake_map, registry_list=registry_list)
        if selectors:
            step["generator_selectors"] = selectors
    return plan


def plan_to_test_case(plan: Dict[str, Any], start_url: Optional[str] = None) -> TestCase:
    """
    Convert PlannerAgent plan to TestCase for DeterministicExecutorV2.
    Preserves step order and maps action/intent to StepType and Intent.
    """
    steps_raw = plan.get("steps") or []
    url = (plan.get("url") or "").strip() or start_url or "https://example.com"
    test_name = (plan.get("test_name") or "Generated Test").strip()
    test_steps: List[TestStep] = []
    seen_nav = False

    for i, s in enumerate(steps_raw):
        if not isinstance(s, dict):
            continue
        step_id = i + 1
        action = (s.get("action") or "click").strip().lower()
        step_type = _plan_action_to_step_type(action)
        intent = _plan_step_to_intent(s, action)
        target = _plan_step_to_target(s, action, intent)
        value = (s.get("value") or "").strip() or None

        # First navigate step: ensure we have URL (target is what executor uses for page.goto)
        if intent == Intent.GOTO:
            if not target and value:
                target = value if value.startswith(("http://", "https://")) else _extract_url_from_text(value)
            if not target and url:
                target = url
            if target and not target.startswith(("http://", "https://")):
                target = _extract_url_from_text(target) or target
            seen_nav = True

        # Pass through selector hints for resolver/healing; include Generator's layered selectors when present
        metadata: Dict[str, Any] = {}
        if s.get("selector"):
            metadata["selector"] = s["selector"]
        if s.get("selectors"):
            metadata["selectors"] = s["selectors"]
        if s.get("generator_selectors"):
            metadata["generator_selectors"] = s["generator_selectors"]
        if s.get("locator_hint"):
            metadata["locator_hint"] = s["locator_hint"]
        if s.get("semantic_target"):
            metadata["semantic_target"] = s["semantic_target"]
        # V3: ELR locator enrichment (injected by enrich_plan_with_elr or enrich_test_case_with_elr)
        if s.get("locator_candidates"):
            metadata["locator_candidates"] = s["locator_candidates"]
        if s.get("elr_lookup_key"):
            metadata["elr_lookup_key"] = s["elr_lookup_key"]
        if s.get("elr_entry"):
            metadata["elr_entry"] = s["elr_entry"]

        # Normalize CLICK/action targets (e.g. "Air Solutions menu" -> "Air Solutions")
        if intent != Intent.GOTO and target:
            target = _normalize_click_target(target) or target

        test_steps.append(
            TestStep(
                id=step_id,
                type=step_type,
                intent=intent,
                target=target or None,
                value=value,
                metadata=metadata,
            )
        )
    test_case = TestCase(
        id=plan.get("test_id") or "plan",
        title=test_name,
        steps=test_steps,
    )
    # V3: enrich with ELR if not already in plan (e.g. when plan was not passed through enrich_plan_with_elr)
    try:
        from .locator_registry import locator_registry, get_elr_lookup_key
        start_url = (plan.get("url") or url or "").strip() or url
        for step in test_case.steps:
            if step.intent in (Intent.CLICK, Intent.SELECT) and step.target:
                entry = locator_registry.get(start_url, step.target, step.intent.value if hasattr(step.intent, "value") else str(step.intent))
                if entry and not (step.metadata or {}).get("locator_candidates"):
                    step.metadata = step.metadata or {}
                    step.metadata["locator_candidates"] = locator_registry.get_all_selectors_ordered(entry)
                    step.metadata["elr_lookup_key"] = get_elr_lookup_key(start_url, step.target, step.intent.value if hasattr(step.intent, "value") else str(step.intent))
                    step.metadata["elr_entry"] = entry
    except Exception:
        pass
    return test_case
