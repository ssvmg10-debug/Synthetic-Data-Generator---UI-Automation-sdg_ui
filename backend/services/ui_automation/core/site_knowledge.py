"""
Site Knowledge Cache
====================

Lightweight site-level knowledge built from pages we visit.

Goals:
- Capture clickable elements (links/buttons) per URL once, persist to disk.
- Reuse this across tests to resolve common actions like
  "Home Appliances", "All Water Purifiers", "Buy Now", etc.

Design:
- For each visited URL we store a mapping:
    label_lower -> {text, tag, href}
- Stored in a JSON file on disk so it survives process restarts.
- Runtime helpers can:
    - record_from_page(page): snapshot current clickable elements
    - get_best_candidate(url, label): find element info for a label
    - try_click(page, label): click using stored knowledge

This is intentionally simple and generic so it can work for LG and
other sites without hard-coding.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse, urlunparse

from playwright.async_api import Page

logger = logging.getLogger(__name__)


ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
SITE_KNOWLEDGE_FILE = ROOT_DIR / "site_knowledge.json"


def _normalize(label: str) -> str:
    return (label or "").strip().lower()[:200]


def _normalize_url(url: str) -> str:
    """Canonicalize URL so same page doesn't fragment cache (strip fragment, trailing slash)."""
    if not url or not url.strip():
        return url or ""
    try:
        parsed = urlparse(url.strip())
        path = (parsed.path or "/").rstrip("/") or "/"
        return urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, ""))
    except Exception:
        return url.strip()


class SiteKnowledge:
    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or SITE_KNOWLEDGE_FILE
        # pages[url][label_lower] = { "text": str, "tag": str, "href": str | None }
        self._pages: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    pages = data.get("pages", {}) if isinstance(data, dict) else {}
                    if isinstance(pages, dict):
                        self._pages = {
                            str(url): (page_map or {})
                            for url, page_map in pages.items()
                            if isinstance(page_map, dict)
                        }
        except Exception as e:
            logger.debug(f"SiteKnowledge load failed: {e}")

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump({"pages": self._pages}, f, indent=2)
        except Exception as e:
            logger.debug(f"SiteKnowledge save failed: {e}")

    async def record_from_page(self, page: Page, max_elements: int = 200) -> None:
        """
        Capture clickable elements from current page and persist them.

        We only store small, human-readable labels (short innerText or aria-label).
        """
        try:
            url = _normalize_url(page.url)
        except Exception:
            return

        try:
            elements = await page.evaluate(
                """
                (maxCount) => {
                  const out = [];
                  const nodes = document.querySelectorAll('a, button, [role="button"], [role="link"]');
                  const limit = Math.min(nodes.length, maxCount || 200);
                  for (let i = 0; i < limit; i++) {
                    const n = nodes[i];
                    const text = (n.innerText || n.getAttribute('aria-label') || '').trim();
                    if (!text || text.length > 80) continue;
                    const tag = (n.tagName || '').toLowerCase();
                    const href = n.getAttribute('href');
                    const role = (n.getAttribute('role') || '').toLowerCase();
                    const ariaLabel = (n.getAttribute('aria-label') || '').trim().substring(0, 100);
                    const dataTestid = (n.getAttribute('data-testid') || n.getAttribute('data-test-id') || '').trim().substring(0, 100);
                    let css = '';
                    const esc = (s) => (s || '').replace(/'/g, "\\\\'").substring(0, 200);
                    if (href && typeof href === 'string' && !href.startsWith('#') && href.indexOf('javascript:') !== 0)
                      css = "a[href='" + esc(href) + "']";
                    else if (dataTestid) css = '[data-testid="' + (dataTestid || '').replace(/"/g, '\\\\"') + '"]';
                    else if (ariaLabel && (tag === 'button' || role === 'button')) css = '[aria-label="' + (ariaLabel || '').replace(/"/g, '\\\\"').substring(0, 80) + '"]';
                    else if (ariaLabel) css = '[aria-label="' + (ariaLabel || '').replace(/"/g, '\\\\"').substring(0, 80) + '"]';
                    const parentChain = [];
                    let p = n.parentElement;
                    for (let d = 0; p && d < 4; d++) { parentChain.push((p.tagName || '').toLowerCase()); p = p.parentElement; }
                    out.push({
                      tag, text, href,
                      role: role || (tag === 'a' ? 'link' : tag === 'button' ? 'button' : ''),
                      aria_label: ariaLabel,
                      data_testid: dataTestid,
                      css: css || (tag === 'a' && href ? "a[href='" + esc(href) + "']" : ''),
                      parent_chain: parentChain,
                    });
                  }
                  return out;
                }
                """,
                max_elements,
            )
        except Exception as e:
            logger.debug(f"SiteKnowledge record_from_page evaluate failed: {e}")
            return

        if not isinstance(elements, list):
            return

        page_map = self._pages.setdefault(url, {})
        updated = False

        for el in elements:
            if not isinstance(el, dict):
                continue
            text = str(el.get("text") or "").strip()
            if not text:
                continue
            key = _normalize(text)
            if not key:
                continue
            # First writer wins; keeps original mapping stable. V3: store rich selectors for ELR bootstrap.
            if key not in page_map:
                page_map[key] = {
                    "text": text,
                    "tag": str(el.get("tag") or ""),
                    "href": el.get("href"),
                    "css": el.get("css"),
                    "role": el.get("role"),
                    "aria_label": el.get("aria_label"),
                    "data_testid": el.get("data_testid"),
                    "parent_chain": el.get("parent_chain"),
                }
                updated = True

        if updated:
            logger.debug(f"SiteKnowledge updated for {url} with {len(page_map)} labels")
            self._save()

    def get_pages_for_bootstrap(self) -> Dict[str, Any]:
        """Return {pages: ...} for ELR bootstrap_from_site_knowledge (V3)."""
        return {"pages": self._pages}

    def get_best_candidate(self, url: str, label: str) -> Optional[Dict[str, Any]]:
        """
        Return best candidate element info for (url, label), using:
        - exact label match
        - substring / contains match
        Falls back to base URL (scheme+host) when path-specific map missing.
        """
        if not label:
            return None
        label_key = _normalize(label)
        if not label_key:
            return None
        url = _normalize_url(url)

        # Direct URL map
        page_map = self._pages.get(url) or {}
        cand = self._match_in_page(page_map, label_key)
        if cand:
            return cand

        # Fallback to origin (scheme + host) if we have entries there
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            base = f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            base = None

        if base and base in self._pages:
            cand = self._match_in_page(self._pages[base], label_key)
            if cand:
                return cand

        # Path prefix: use longest stored URL that is a prefix of current (e.g. category page for PDP)
        try:
            best_prefix: Optional[str] = None
            best_len = -1
            for stored_url in self._pages:
                if url == stored_url:
                    continue
                if not url.startswith(stored_url):
                    continue
                # stored_url is prefix of url; require boundary (end or /)
                if len(url) > len(stored_url) and url[len(stored_url)] != "/":
                    continue
                if len(stored_url) > best_len:
                    best_len = len(stored_url)
                    best_prefix = stored_url
            if best_prefix:
                cand = self._match_in_page(self._pages[best_prefix], label_key)
                if cand:
                    return cand
        except Exception:
            pass

        return None

    @staticmethod
    def _match_in_page(page_map: Dict[str, Dict[str, Any]], label_key: str) -> Optional[Dict[str, Any]]:
        if not page_map:
            return None
        # 1) exact key
        if label_key in page_map:
            return page_map[label_key]
        # 2) substring / contains (both directions)
        for k, v in page_map.items():
            if label_key in k or k in label_key:
                return v
        return None

    async def try_click(self, page: Page, label: str, timeout_ms: int = 8000) -> Optional[str]:
        """
        Try to click element for label using stored knowledge.
        Uses href and text strategies; scopes to nav/header for dropdown links.
        Returns selector string used on success; None on failure.
        """
        SCROLL_TIMEOUT_MS = 5000
        HOVER_TIMEOUT_MS = 2000
        try:
            url = _normalize_url(page.url)
        except Exception:
            return None

        cand = self.get_best_candidate(url, label)
        if not cand:
            logger.info("  SiteKnowledge: no candidate for label=%r url=%s", label, url[:80] if url else "")
            return None

        text = cand.get("text") or label
        href = cand.get("href")
        tag = (cand.get("tag") or "").lower()

        async def _safe_scroll_and_click(locator, desc: str) -> bool:
            try:
                await locator.scroll_into_view_if_needed(timeout=SCROLL_TIMEOUT_MS)
            except Exception as se:
                logger.debug("  SiteKnowledge scroll_into_view skipped for %s: %s", desc, se)
            try:
                await locator.click(timeout=timeout_ms)
                return True
            except Exception:
                return False

        # 1) Prefer href: try page-wide, then scoped to nav/header/dropdown (for mega-menu links)
        if href and isinstance(href, str) and href.strip():
            href_variants = [href.strip()]
            h = href.strip()
            if h.endswith("/"):
                href_variants.append(h[:-1])
            elif "/" in h:
                href_variants.append(h + "/")
            for href_clean in href_variants:
                for scope_desc, scope_sel in [
                    ("page", None),
                    ("nav", "nav, [role='navigation'], header"),
                    ("menu", "[role='menu'], [class*='menu'], [class*='dropdown'], [class*='mega'], [class*='MegaMenu']"),
                ]:
                    try:
                        if scope_sel is None:
                            loc = page.locator(f'a[href="{href_clean}"]')
                        else:
                            scope = page.locator(scope_sel)
                            if await scope.count() == 0:
                                continue
                            loc = scope.first.locator(f'a[href="{href_clean}"]')
                        if await loc.count() == 0:
                            continue
                        elem = loc.first
                        if await _safe_scroll_and_click(elem, f"href {scope_desc}"):
                            logger.info("  ✅ SiteKnowledge clicked via href: %r -> %s (%s)", text, href_clean[:50], scope_desc)
                            return f'a[href="{href_clean}"]'
                    except Exception as e:
                        logger.debug("  SiteKnowledge href (%s) failed: %s", scope_desc, e)
                        continue

        # 2) Role/aria-label based (for icon-only buttons like search - no visible text)
        import re
        try:
            for role, name_pattern in [
                ("button", re.compile(re.escape(text), re.I)),
                ("link", re.compile(re.escape(text), re.I)),
            ]:
                loc = page.get_by_role(role, name=name_pattern)
                if await loc.count() > 0:
                    elem = loc.first
                    if await _safe_scroll_and_click(elem, f"role {role}"):
                        logger.info("  ✅ SiteKnowledge clicked via role=%s name=%r", role, text)
                        return f"role={role}[name=/{re.escape(text)}/i]"
        except Exception as e:
            logger.debug("  SiteKnowledge role/aria failed: %s", e)
        try:
            for attr in ["aria-label", "title"]:
                loc = page.locator(f"[{attr}*='{text}' i]")
                if await loc.count() > 0:
                    elem = loc.first
                    if await _safe_scroll_and_click(elem, f"attr {attr}"):
                        logger.info("  ✅ SiteKnowledge clicked via %s=%r", attr, text)
                        return f"[{attr}*='{text}' i]"
        except Exception as e:
            logger.debug("  SiteKnowledge attr failed: %s", e)

        # 3) Text-based: try scoped to nav first for nav-like labels, then page-wide
        pattern = re.compile(re.escape(text), re.I)
        for scope_desc, scope in [
            ("nav", page.locator("nav, [role='navigation'], header, [class*='menu'], [class*='dropdown']").first),
            ("page", None),
        ]:
            try:
                if scope is not None and await scope.count() > 0:
                    loc = scope.get_by_text(pattern)
                else:
                    loc = page.get_by_text(pattern)
                count = await loc.count()
                if count == 0:
                    continue
                elem = loc.first
                if tag == "button" and not href:
                    try:
                        await elem.hover(timeout=HOVER_TIMEOUT_MS)
                        await page.wait_for_timeout(300)
                    except Exception as h:
                        logger.debug("  SiteKnowledge hover skipped: %s", h)
                if await _safe_scroll_and_click(elem, f"text {scope_desc}"):
                    logger.info("  ✅ SiteKnowledge clicked via text: %r (%s)", text, scope_desc)
                    return f"text=/{re.escape(text)}/i"
            except Exception as e:
                logger.debug("  SiteKnowledge text (%s) failed: %s", scope_desc, e)
                continue

        logger.info("  SiteKnowledge: all strategies failed for %r", text)
        return None


# Singleton instance used by executor
site_knowledge = SiteKnowledge()

