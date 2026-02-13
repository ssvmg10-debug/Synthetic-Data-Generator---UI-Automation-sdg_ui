"""
Per-application config for UI automation (Phase 5).
Maps site URL/host to app_key and app-specific selectors and behavior.
Used by Planner (inject cookie step) and Generator (cookie/search selectors).
"""
from typing import Dict, Any, Optional
import re

# Host pattern -> config. Use "lg.com" to match www.lg.com and lg.com
APP_CONFIGS: Dict[str, Dict[str, Any]] = {
    "lg.com": {
        "app_key": "lg_in",
        "base_url": "https://www.lg.com/in",
        "name": "LG India",
        "inject_cookie_step_after_navigate": True,
        "cookie_accept_selectors": [
            "button:has-text('Accept all')",
            "a:has-text('Accept all')",
            "button:has-text('Save & Proceed')",
            "button:has-text('Accept')",
            "[id*='cookie'] button:has-text('Accept')",
            ".cmp-button:has-text('Accept all')",
            "button:has-text('Reject All')",  # fallback to close banner
        ],
        "search_box_selectors": [
            "input[type='search']",
            "input[placeholder*='Search']",
            "input[aria-label*='Search']",
            "[role='search'] input",
        ],
        "search_submit_selectors": [
            "button[type='submit']",
            "button:has(svg)",
            "[aria-label*='Search']",
        ],
    },
}


def _normalize_host(url: str) -> Optional[str]:
    """Extract host from URL for lookup (e.g. www.lg.com -> lg.com for config key)."""
    if not url or not isinstance(url, str):
        return None
    url = url.strip().lower()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = (parsed.netloc or "").strip()
        if not host:
            return None
        # Match config by parent domain: www.lg.com -> lg.com
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return None


def get_app_config_for_url(url: str) -> Optional[Dict[str, Any]]:
    """
    Return app config for the given URL, or None.
    URL can be full (https://www.lg.com/in) or host (www.lg.com).
    """
    host = _normalize_host(url)
    if not host:
        return None
    # Exact match
    if host in APP_CONFIGS:
        return APP_CONFIGS[host].copy()
    # Suffix match (e.g. lg.com matches www.lg.com already via normalize; check for subdomains)
    for pattern, config in APP_CONFIGS.items():
        if host == pattern or host.endswith("." + pattern):
            return config.copy()
    return None


def should_inject_cookie_step(url: str) -> bool:
    """True if we should inject a cookie-accept step after navigate for this URL."""
    cfg = get_app_config_for_url(url)
    return bool(cfg and cfg.get("inject_cookie_step_after_navigate"))
