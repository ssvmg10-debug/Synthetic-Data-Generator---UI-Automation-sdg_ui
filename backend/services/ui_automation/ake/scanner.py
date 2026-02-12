"""
AKE Scanner: returns a JavaScript snippet that runs in page.evaluate() and returns
application map (search_fields, cookie_accept, login, etc.) for use by Generator/Healer.
"""
from typing import Dict, Any, List


def get_ake_script() -> str:
    """
    Return a single JS string that when run in page.evaluate() returns an object:
    {
      search_fields: [{ selector, score, tag, placeholder }],
      search_submit: [{ selector, score }],
      cookie_accept: [{ selector, score, text }],
      login: [{ selector, score }],
      shadow_roots: boolean
    }
    Uses only DOM APIs (no Playwright inside evaluate).
    """
    return r"""
() => {
  const out = { search_fields: [], search_submit: [], cookie_accept: [], login: [], shadow_roots: false };
  const score = (sel, s) => ({ selector: sel, score: s });

  // Search inputs: input[type=search], placeholder*Search, name*search, aria-label*search
  try {
    const inputs = document.querySelectorAll('input[type="search"], input[type="text"], input[placeholder], input[name]');
    inputs.forEach(el => {
      const p = (el.getAttribute('placeholder') || '').toLowerCase();
      const n = (el.getAttribute('name') || '').toLowerCase();
      const a = (el.getAttribute('aria-label') || '').toLowerCase();
      const id = (el.getAttribute('id') || '').toLowerCase();
      let s = 0;
      if (el.type === 'search') s = 0.95;
      else if (p.includes('search') || n.includes('search') || a.includes('search') || id.includes('search')) s = 0.9;
      else if (p || n) s = 0.5;
      if (s > 0) out.search_fields.push({ selector: el.id ? '#' + el.id : (el.name ? 'input[name="' + el.getAttribute('name') + '"]' : 'input[placeholder*="' + (el.getAttribute('placeholder') || '').substring(0, 20) + '"]'), score: s, tag: el.tagName, placeholder: el.getAttribute('placeholder') || '' });
    });
    if (out.search_fields.length === 0) {
      const any = document.querySelector('input');
      if (any) out.search_fields.push({ selector: 'input[type="text"]', score: 0.4, tag: 'input', placeholder: '' });
    }
  } catch (_) {}

  // Search submit: button[type=submit], button with text Search, [aria-label*="search"]
  try {
    const buttons = document.querySelectorAll('button[type="submit"], input[type="submit"], button, [role="button"]');
    buttons.forEach(el => {
      const t = (el.innerText || el.value || el.getAttribute('aria-label') || '').toLowerCase();
      if (t.includes('search') || el.type === 'submit') out.search_submit.push({ selector: el.tagName.toLowerCase() + (el.innerText ? ':has-text("' + (el.innerText.trim().substring(0, 20)) + '")' : ''), score: t.includes('search') ? 0.9 : 0.5 });
    });
  } catch (_) {}

  // Cookie / Accept: buttons and links with Accept, I agree, OK, Cookie, Reject
  try {
    const nodes = document.querySelectorAll('button, a, [role="button"]');
    nodes.forEach(el => {
      const t = (el.innerText || el.getAttribute('aria-label') || '').toLowerCase();
      if (t.includes('accept') || t.includes('agree') || t.includes('cookie') || t.includes('reject') || t.includes('save & proceed') || t.includes('close')) {
        const sel = el.id ? '#' + el.id : (el.tagName.toLowerCase() + ':has-text("' + (el.innerText || '').trim().substring(0, 25).replace(/"/g, '') + '")');
        out.cookie_accept.push({ selector: sel, score: t.includes('accept all') ? 0.95 : 0.85, text: (el.innerText || '').trim().substring(0, 40) });
      }
    });
  } catch (_) {}

  // Login: links/buttons with Sign in, Login
  try {
    document.querySelectorAll('a, button').forEach(el => {
      const t = (el.innerText || el.getAttribute('aria-label') || '').toLowerCase();
      const h = (el.getAttribute('href') || '').toLowerCase();
      if (t.includes('sign in') || t.includes('login') || h.includes('login')) out.login.push({ selector: el.tagName.toLowerCase() + ':has-text("' + (el.innerText || '').trim().substring(0, 15).replace(/"/g, '') + '")', score: 0.9 });
    });
  } catch (_) {}

  // Shadow roots present?
  try {
    out.shadow_roots = !!document.querySelector('*').shadowRoot;
  } catch (_) {}

  return out;
}
"""


def parse_ake_result(ake_map: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Normalize AKE result (from page.evaluate or from run). Ensures each key has a list of {selector, score}.
    """
    normalized: Dict[str, List[Dict[str, Any]]] = {}
    for key in ["search_fields", "search_submit", "cookie_accept", "login"]:
        raw = ake_map.get(key)
        if isinstance(raw, list):
            normalized[key] = [x if isinstance(x, dict) and "selector" in x else {"selector": str(x), "score": 0.8} for x in raw]
        else:
            normalized[key] = []
    return normalized


def selector_list_from_ake(ake_map: Dict[str, Any], intent: str) -> List[str]:
    """
    Given AKE map and intent (e.g. search_box, cookie_accept), return ordered list of selectors to try.
    """
    normalized = parse_ake_result(ake_map)
    intent_to_key = {
        "search_box": "search_fields",
        "search_submit": "search_submit",
        "cookie_accept": "cookie_accept",
        "login": "login",
    }
    key = intent_to_key.get(intent)
    if not key or key not in normalized:
        return []
    items = normalized[key]
    items_sorted = sorted(items, key=lambda x: x.get("score", 0), reverse=True)
    return [x.get("selector", "") for x in items_sorted if x.get("selector")]
