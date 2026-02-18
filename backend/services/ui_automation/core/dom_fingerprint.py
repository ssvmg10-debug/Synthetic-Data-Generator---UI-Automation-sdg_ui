"""
DOM Fingerprint Engine — V3 Enterprise

When a selector breaks, instead of jumping to healing:
- Search page for elements with similar DOM fingerprint
- Compute similarity score (structural: tag, parent_chain, attributes, text_hash, sibling_index)
- If similarity > threshold (e.g. 0.75) → use found element and optionally promote new selector to ELR

No AI needed. Provides deterministic structural recovery.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple

from playwright.async_api import Page, Locator

logger = logging.getLogger(__name__)

# Similarity above this → consider same element (structural recovery)
DEFAULT_SIMILARITY_THRESHOLD = 0.75

# JS to extract fingerprint from an element (run in browser)
_EXTRACT_FINGERPRINT_JS = """
(el) => {
  if (!el || !el.nodeName) return null;
  const tag = (el.tagName || '').toLowerCase();
  const text = (el.innerText || el.textContent || '').trim().substring(0, 500);
  const getParentChain = (node, depth) => {
    const chain = [];
    let n = node.parentElement;
    let d = 0;
    while (n && d < depth) {
      chain.push((n.tagName || '').toLowerCase());
      n = n.parentElement;
      d++;
    }
    return chain;
  };
  const parent_chain = getParentChain(el, 5);
  const attrs = {};
  for (const a of (el.attributes || [])) {
    const name = (a.name || '').toLowerCase();
    if (['id', 'class', 'data-testid', 'data-test-id', 'aria-label', 'role', 'name', 'href'].includes(name))
      attrs[name] = (a.value || '').trim().substring(0, 200);
  }
  const attribute_hash = Object.keys(attrs).sort().map(k => k + '=' + (attrs[k] || '')).join('|');
  let sibling_index = 0;
  let sib = el.previousElementSibling;
  while (sib) { sibling_index++; sib = sib.previousElementSibling; }
  const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : {};
  const area = (rect.width || 0) * (rect.height || 0);
  return {
    tag,
    text_hash: text ? text.length + '_' + text.substring(0, 80).replace(/\\s+/g, ' ') : '',
    parent_chain,
    attribute_hash: attribute_hash ? attribute_hash.substring(0, 300) : '',
    sibling_index,
    area: Math.round(area),
    role: (el.getAttribute('role') || '').toLowerCase(),
    aria_label: (el.getAttribute('aria-label') || '').trim().substring(0, 100),
    data_testid: (el.getAttribute('data-testid') || el.getAttribute('data-test-id') || '').trim().substring(0, 100),
  };
}
"""

# JS to collect all clickable-like elements and their fingerprints (for find_by_fingerprint)
_COLLECT_CANDIDATES_JS = """
() => {
  const nodes = document.querySelectorAll('a, button, [role="button"], [role="link"], input[type="submit"], [onclick]');
  const out = [];
  const limit = Math.min(nodes.length, 150);
  for (let i = 0; i < limit; i++) {
    const el = nodes[i];
    const rect = el.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) continue;
    const style = window.getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none' || style.opacity === '0') continue;
    const tag = (el.tagName || '').toLowerCase();
    const text = (el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim().substring(0, 500);
    const getParentChain = (node, depth) => {
      const chain = [];
      let n = node.parentElement;
      let d = 0;
      while (n && d < depth) { chain.push((n.tagName || '').toLowerCase()); n = n.parentElement; d++; }
      return chain;
    };
    const parent_chain = getParentChain(el, 5);
    const attrs = {};
    for (const a of (el.attributes || [])) {
      const name = (a.name || '').toLowerCase();
      if (['id', 'class', 'data-testid', 'data-test-id', 'aria-label', 'role', 'name', 'href'].includes(name))
        attrs[name] = (a.value || '').trim().substring(0, 200);
    }
    const attribute_hash = Object.keys(attrs).sort().map(k => k + '=' + (attrs[k] || '')).join('|').substring(0, 300);
    let sibling_index = 0;
    let sib = el.previousElementSibling;
    while (sib) { sibling_index++; sib = sib.previousElementSibling; }
    const area = (rect.width || 0) * (rect.height || 0);
    let selector = '';
    if (el.id && !el.id.match(/^[0-9]/)) selector = '#' + el.id;
    else if (el.getAttribute('data-testid')) selector = '[data-testid="' + (el.getAttribute('data-testid') || '').replace(/"/g, '\\"') + '"]';
    else if (el.getAttribute('data-test-id')) selector = '[data-test-id="' + (el.getAttribute('data-test-id') || '').replace(/"/g, '\\"') + '"]';
    else selector = tag + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\\s+/)[0].substring(0, 30) : '');
    out.push({
      selector,
      tag,
      text_hash: text ? text.length + '_' + text.substring(0, 80).replace(/\\s+/g, ' ') : '',
      parent_chain,
      attribute_hash,
      sibling_index,
      area: Math.round(area),
      role: (el.getAttribute('role') || '').toLowerCase(),
      aria_label: (el.getAttribute('aria-label') || '').trim().substring(0, 100),
      data_testid: (el.getAttribute('data-testid') || el.getAttribute('data-test-id') || '').trim().substring(0, 100),
      href: (el.getAttribute('href') || '').trim().substring(0, 200),
      text_preview: text.substring(0, 80),
    });
  }
  return out;
}
"""


def _norm(fp: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize fingerprint for comparison (ensure keys exist)."""
    return {
        "tag": (fp.get("tag") or "").lower(),
        "text_hash": (fp.get("text_hash") or "").strip(),
        "parent_chain": list(fp.get("parent_chain") or [])[:5],
        "attribute_hash": (fp.get("attribute_hash") or "").strip()[:300],
        "sibling_index": int(fp.get("sibling_index") or 0),
        "role": (fp.get("role") or "").lower(),
        "aria_label": (fp.get("aria_label") or "").strip()[:100],
        "data_testid": (fp.get("data_testid") or "").strip()[:100],
    }


def fingerprint_similarity(stored: Dict[str, Any], candidate: Dict[str, Any]) -> float:
    """
    Compute structural similarity between two fingerprints. Returns 0–1.
    Weights: tag + parent_chain (structure), attribute_hash, text_hash, sibling_index.
    """
    s = _norm(stored)
    c = _norm(candidate)
    score = 0.0
    weights = 0.0

    # Tag match (required for same element type)
    if s["tag"]:
        weights += 0.25
        if s["tag"] == c["tag"]:
            score += 0.25
    else:
        weights += 0.25

    # Parent chain (structural context)
    if s["parent_chain"]:
        weights += 0.25
        sp = s["parent_chain"]
        cp = c["parent_chain"]
        if sp == cp:
            score += 0.25
        elif len(sp) > 0 and len(cp) > 0:
            matches = sum(1 for i, t in enumerate(sp) if i < len(cp) and cp[i] == t)
            score += 0.25 * (matches / max(len(sp), len(cp)))
    else:
        weights += 0.25

    # Attribute hash (id, class, data-testid, aria, etc.)
    if s["attribute_hash"]:
        weights += 0.25
        if s["attribute_hash"] == c["attribute_hash"]:
            score += 0.25
        elif s["attribute_hash"] and c["attribute_hash"]:
            # Partial: same keys or overlapping values
            sa = set(s["attribute_hash"].split("|"))
            ca = set(c["attribute_hash"].split("|"))
            inter = len(sa & ca)
            score += 0.25 * (inter / max(len(sa), len(ca), 1))
    else:
        weights += 0.25

    # Text hash (content)
    if s["text_hash"]:
        weights += 0.15
        if s["text_hash"] == c["text_hash"]:
            score += 0.15
        elif s["text_hash"].split("_")[0] == c["text_hash"].split("_")[0]:  # length match
            score += 0.07
    else:
        weights += 0.15

    # Sibling index (position among siblings)
    if s.get("sibling_index") is not None and c.get("sibling_index") is not None:
        weights += 0.10
        if s["sibling_index"] == c["sibling_index"]:
            score += 0.10
        elif abs(s["sibling_index"] - c["sibling_index"]) <= 1:
            score += 0.05
    else:
        weights += 0.10

    if weights <= 0:
        return 0.0
    return round(score / (weights or 1), 3)


async def capture_fingerprint_from_locator(page: Page, locator: Locator) -> Optional[Dict[str, Any]]:
    """
    Capture DOM fingerprint from the first element matched by locator.
    Used after successful resolution to store in ELR for future fingerprint recovery.
    """
    try:
        first = locator.first
        return await first.evaluate(_EXTRACT_FINGERPRINT_JS)
    except Exception as e:
        logger.debug("capture_fingerprint_from_locator failed: %s", e)
        return None


async def capture_fingerprint_from_selector(page: Page, selector: str) -> Optional[Dict[str, Any]]:
    """Capture fingerprint from element found by selector."""
    try:
        loc = page.locator(selector).first
        return await loc.evaluate(_EXTRACT_FINGERPRINT_JS)
    except Exception as e:
        logger.debug("capture_fingerprint_from_selector failed: %s", e)
        return None


async def find_by_fingerprint(
    page: Page,
    stored_fingerprint: Dict[str, Any],
    min_similarity: float = DEFAULT_SIMILARITY_THRESHOLD,
    intent_target: Optional[str] = None,
) -> Optional[Tuple[str, float]]:
    """
    Search page for element with similar DOM fingerprint. Returns (selector, similarity) of best match
    above min_similarity, or None. Optional intent_target can filter candidates by text/aria overlap.
    """
    if not stored_fingerprint or not stored_fingerprint.get("tag"):
        return None
    try:
        candidates = await page.evaluate(_COLLECT_CANDIDATES_JS)
    except Exception as e:
        logger.debug("find_by_fingerprint collect failed: %s", e)
        return None
    if not isinstance(candidates, list) or not candidates:
        return None

    stored_norm = _norm(stored_fingerprint)
    best_selector: Optional[str] = None
    best_score = 0.0

    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        c_norm = _norm(cand)
        sim = fingerprint_similarity(stored_norm, c_norm)
        if sim < min_similarity:
            continue
        # Optional: boost if intent_target appears in text_preview/aria_label
        if intent_target and (cand.get("text_preview") or cand.get("aria_label") or ""):
            target_lower = intent_target.lower()
            preview = ((cand.get("text_preview") or "") + " " + (cand.get("aria_label") or "")).lower()
            if target_lower in preview or any(w in preview for w in target_lower.split()):
                sim = min(1.0, sim + 0.1)
        if sim > best_score:
            best_score = sim
            sel = cand.get("selector") or ""
            if sel and cand.get("tag"):
                # Prefer unique selector
                if cand.get("data_testid"):
                    sel = f'[data-testid="{cand.get("data_testid", "").replace(chr(34), "")}"]'
                elif cand.get("href"):
                    sel = f"a[href=\"{cand.get('href', '')[:100].replace(chr(34), '')}\"]"
                best_selector = sel or f"{cand.get('tag', 'div')}:has-text('{(cand.get('text_preview') or '')[:50]}')"

    if best_selector and best_score >= min_similarity:
        return (best_selector, best_score)
    return None
