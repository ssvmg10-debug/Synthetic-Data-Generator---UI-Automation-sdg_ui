"""
Application Knowledge Engine (AKE) for UI Automation
---------------------------------------------------

This module provides lightweight, generic DOM introspection for enterprise UIs.
It builds an in-page "akeMap" of semantic intents → selector candidates that
the Generator and Healer agents can use as high-quality first choices.

The goal is similar to KaneAI / testRigor style semantic targeting, but kept
fully generic (no app-specific hardcoding): we look for common patterns across
modern ecommerce/enterprise apps (search, cart, checkout, login, cookie banners).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def get_ake_script() -> str:
    """
    Return a self-contained JS function (as a string) that, when evaluated in
    the browser (`eval("(" + s + ")()")`), crawls the current DOM and returns a
    JSON-serializable map:

        {
          search_fields: [selector, ...],
          search_submit: [selector, ...],
          cookie_accept: [selector, ...],
          login: [selector, ...],
          add_to_cart: [selector, ...],
          cart: [selector, ...],
        }

    Selectors are CSS / Playwright-compatible and derived from ids, names,
    aria-labels, placeholders and innerText, where available.

    This is intentionally conservative: it prefers simple, robust selectors and
    de-duplicates them. The Generator still layers its own generic selectors
    after these.
    """

    # NOTE: Keep this JS free of backticks to avoid nesting issues; use classic
    # string quotes and simple concatenation where needed.
    return r"""
() => {
  function unique(arr) {
    const out = [];
    const seen = new Set();
    for (const v of arr) {
      if (!v) continue;
      if (!seen.has(v)) {
        seen.add(v);
        out.push(v);
      }
    }
    return out;
  }

  function buildSelector(el) {
    if (!el || el.nodeType !== 1) return null;
    if (el.id) {
      return "#" + el.id;
    }
    const name = el.getAttribute("name");
    if (name) {
      return el.tagName.toLowerCase() + "[name='" + name + "']";
    }
    const aria = el.getAttribute("aria-label");
    if (aria) {
      return "[aria-label*='" + aria.replace(/'/g, "\\'") + "']";
    }
    const placeholder = el.getAttribute("placeholder");
    if (placeholder) {
      return el.tagName.toLowerCase() + "[placeholder*='" + placeholder.replace(/'/g, "\\'") + "']";
    }
    const text = (el.innerText || el.textContent || "").trim();
    if (text) {
      // Playwright text selector; keep it short.
      const short = text.length > 40 ? text.slice(0, 40) : text;
      return "text=" + short.replace(/\s+/g, " ");
    }
    return null;
  }

  function collectSearchFields(doc) {
    const out = [];
    const candidates = Array.from(
      doc.querySelectorAll(
        "input[type='search'], input[placeholder*='search' i], input[name*='search' i], input[aria-label*='search' i]"
      )
    );
    for (const el of candidates) {
      const sel = buildSelector(el);
      if (sel) out.push(sel);
    }
    return unique(out);
  }

  function collectSearchSubmit(doc) {
    const out = [];
    const candidates = Array.from(
      doc.querySelectorAll(
        "button[type='submit'], input[type='submit'], button, a"
      )
    );
    for (const el of candidates) {
      const txt = (el.innerText || el.textContent || "").toLowerCase();
      if (!txt) continue;
      if (txt.includes("search") || txt.includes("go") || txt.includes("find")) {
        const sel = buildSelector(el);
        if (sel) out.push(sel);
      }
    }
    return unique(out);
  }

  function collectCookieAccept(doc) {
    const out = [];
    const candidates = Array.from(
      doc.querySelectorAll("button, a, [role='button']")
    );
    for (const el of candidates) {
      const txt = (el.innerText || el.textContent || "").toLowerCase();
      if (!txt) continue;
      if (
        txt.includes("accept") ||
        txt.includes("agree") ||
        txt.includes("allow all") ||
        txt.includes("accept all")
      ) {
        const sel = buildSelector(el);
        if (sel) out.push(sel);
      }
    }
    return unique(out);
  }

  function collectLogin(doc) {
    const out = [];
    const candidates = Array.from(
      doc.querySelectorAll("a, button, [role='button']")
    );
    for (const el of candidates) {
      const txt = (el.innerText || el.textContent || "").toLowerCase();
      if (!txt) continue;
      if (
        txt.includes("sign in") ||
        txt.includes("signin") ||
        txt.includes("log in") ||
        txt.includes("login") ||
        txt.includes("my account")
      ) {
        const sel = buildSelector(el);
        if (sel) out.push(sel);
      }
    }
    return unique(out);
  }

  function collectAddToCart(doc) {
    const out = [];
    const candidates = Array.from(
      doc.querySelectorAll("button, a, [role='button']")
    );
    for (const el of candidates) {
      const txt = (el.innerText || el.textContent || "").toLowerCase();
      if (!txt) continue;
      if (
        txt.includes("add to cart") ||
        txt.includes("add to bag") ||
        txt.includes("add to basket") ||
        txt.includes("buy now")
      ) {
        const sel = buildSelector(el);
        if (sel) out.push(sel);
      }
    }
    return unique(out);
  }

  function collectCart(doc) {
    const out = [];
    const candidates = Array.from(
      doc.querySelectorAll("a, button, [role='button']")
    );
    for (const el of candidates) {
      const txt = (el.innerText || el.textContent || "").toLowerCase();
      if (!txt) continue;
      if (
        txt.includes("cart") ||
        txt.includes("basket") ||
        txt.includes("bag")
      ) {
        const sel = buildSelector(el);
        if (sel) out.push(sel);
      }
    }
    return unique(out);
  }

  const doc = document;
  const ake = {};
  try {
    ake.search_fields = collectSearchFields(doc);
    ake.search_submit = collectSearchSubmit(doc);
    ake.cookie_accept = collectCookieAccept(doc);
    ake.login = collectLogin(doc);
    ake.add_to_cart = collectAddToCart(doc);
    ake.cart = collectCart(doc);
  } catch (e) {
    console.error("AKE collection error:", e);
  }
  return ake;
}
"""


def selector_list_from_ake(ake_map: Optional[Dict[str, Any]], intent: str) -> List[str]:
    """
    Given an AKE map (returned from get_ake_script() evaluation) and an intent
    name, return a list of selector strings to try. This is used by the
    Generator to prepend AKE-derived selectors to its layered selectors.
    """

    if not ake_map or not isinstance(ake_map, dict):
        return []

    key = None
    if intent in ("search_box", "search_field"):
        key = "search_fields"
    elif intent in ("search_submit",):
        key = "search_submit"
    elif intent in ("cookie_accept",):
        key = "cookie_accept"
    elif intent in ("login", "sign_in"):
        key = "login"
    elif intent in ("add_to_cart", "buy_now"):
        key = "add_to_cart"
    elif intent in ("cart", "view_cart", "open_cart"):
        key = "cart"

    if not key:
        return []

    vals = ake_map.get(key) or []
    out: List[str] = []
    for v in vals:
        if isinstance(v, str) and v.strip():
            out.append(v.strip())
        elif isinstance(v, dict):
            sel = v.get("selector")
            if isinstance(sel, str) and sel.strip():
                out.append(sel.strip())
    # Limit to first few high-signal selectors
    return out[:10]

