"""
Per-application config for UI automation (Phase 5).

ROLE: App config provides FALLBACK selectors only – not the core execution driver.
- Cookie/consent: inject step + fallback selectors when page intelligence doesn't need to run.
- Rare edge selectors: when Page Intelligence Engine or semantic actions don't apply.
- Core logic is state-aware + component-aware (PageModel, select_product_with_condition, etc.).

Selector order: prefer stable (role+name, aria-label, data-*), then semantic (type, placeholder),
then text. Each list is tried in order until one matches.

For https://www.lg.com/in: covers full journey (cookie, search, products, cart, checkout, guest, pincode, billing).
"""
from typing import Dict, Any, Optional
import re

# Intent -> app_config key (selectors list). Used by router and generator.
INTENT_TO_SELECTORS_KEY: Dict[str, str] = {
    "cookie_accept": "cookie_accept_selectors",
    "search_box": "search_box_selectors",
    "search_submit": "search_submit_selectors",
    "search_icon": "search_icon_selectors",
    "login": "login_selectors",
    "product_select": "product_select_selectors",
    "select_product_with_condition": "product_select_selectors",
    "add_to_cart": "add_to_cart_selectors",
    "cart": "cart_selectors",
    "checkout": "checkout_selectors",
    "guest_checkout": "guest_checkout_selectors",
    "pincode_zip": "pincode_zip_selectors",
    "pincode_check": "check_button_selectors",
    "billing_shipping": "billing_shipping_selectors",
    "pay_now": "pay_now_selectors",
    "email_field": "email_field_selectors",
    "menu_shop": "menu_shop_selectors",
}

# Sandbox / test environment (set UI_AUTOMATION_STAGING=1, UI_AUTOMATION_MOCK_PAYMENT=1)
def use_staging() -> bool:
    return __import__("os").environ.get("UI_AUTOMATION_STAGING", "").strip() in ("1", "true", "yes")


def use_mock_payment_endpoint() -> bool:
    return __import__("os").environ.get("UI_AUTOMATION_MOCK_PAYMENT", "").strip() in ("1", "true", "yes")


# Host pattern -> config. Use "lg.com" to match www.lg.com and lg.com
APP_CONFIGS: Dict[str, Dict[str, Any]] = {
    "lg.com": {
        "app_key": "lg_in",
        "base_url": "https://www.lg.com/in",
        "name": "LG India",
        "inject_cookie_step_after_navigate": True,
        "use_flow_engine": True,  # Use state-machine flow engine (domain-aware) for LG
        "use_staging": False,  # Override at runtime via use_staging()
        "mock_payment_endpoint": False,  # Override via use_mock_payment_endpoint()
        # --- Cookie / consent (banner on first load) ---
        "cookie_accept_selectors": [
            "[role='button']:has-text('Accept all')",
            "button:has-text('Accept all')",
            "a:has-text('Accept all')",
            "button:has-text('Accept')",
            "a:has-text('Accept')",
            "button:has-text('Save & Proceed')",
            "[id*='cookie'] button",
            "[id*='consent'] button:has-text('Accept')",
            ".cmp-button:has-text('Accept all')",
            ".cookie-accept",
            "button:has-text('Reject All')",
        ],
        # --- Search: icon/link to open search, then input and submit ---
        "search_icon_selectors": [
            "a:has-text('Search')",
            "button:has-text('Search')",
            "[aria-label*='Search']",
            ".search-icon",
            "[href*='search']",
            "nav a:has-text('Search')",
        ],
        "search_box_selectors": [
            "input[type='search']",
            "input[name='q']",
            "input[name='search']",
            "input[placeholder*='Search']",
            "input[placeholder*='search']",
            "input[aria-label*='Search']",
            "[role='search'] input",
            "#search",
            ".search-input",
            "input[type='text']",
        ],
        "search_submit_selectors": [
            "button[type='submit']",
            "form[role='search'] button[type='submit']",
            "[aria-label*='Search']",
            "button:has-text('Search')",
            "button:has(svg)",
            ".search-submit",
            "button[type='button']:has(svg)",
        ],
        # --- Login / account ---
        "login_selectors": [
            "a:has-text('Sign in')",
            "a:has-text('Sign in / Join us')",
            "a:has-text('Join us')",
            "button:has-text('Sign in')",
            "[href*='login']",
            "[aria-label*='Sign in']",
        ],
        # --- Product: Buy Now, product links, Know More, Learn more ---
        "product_select_selectors": [
            "a:has-text('Buy Now')",
            "button:has-text('Buy Now')",
            "a:has-text('Know More')",
            "a:has-text('Learn more')",
            "a:has-text('Learn More')",
            ".cmp-button:has-text('Buy Now')",
            "[href*='/in/'] .cmp-button",
            "a[href*='product']",
            ".product a",
        ],
        "add_to_cart_selectors": [
            "button:has-text('Buy Now')",
            "button:has-text('Add to cart')",
            "button:has-text('Add to bag')",
            "a:has-text('Buy Now')",
            "[data-action*='cart']",
            ".add-to-cart",
        ],
        # --- Cart & checkout ---
        "cart_selectors": [
            "a:has-text('Cart')",
            "[aria-label*='Cart']",
            "[href*='cart']",
            ".cart-icon",
        ],
        "checkout_selectors": [
            "button:has-text('Checkout')",
            "a:has-text('Checkout')",
            "button:has-text('Check out')",
            "a:has-text('Check out')",
            "[data-action*='checkout']",
            ".checkout-btn",
        ],
        "guest_checkout_selectors": [
            "button:has-text('Continue as guest')",
            "a:has-text('Continue as guest')",
            "button:has-text('Continue as Guest')",
            "button:has-text('Guest')",
            "button:has-text('Continue')",
            "a:has-text('Continue')",
        ],
        # --- Pincode / zip (LG India delivery check) ---
        "pincode_zip_selectors": [
            "input[name*='pincode']",
            "input[name*='zip']",
            "input[placeholder*='Pincode']",
            "input[placeholder*='Pin code']",
            "input[placeholder*='Zip']",
            "input[aria-label*='Pincode']",
            "#pincode",
            "#zip",
        ],
        # --- Check button after pincode ---
        "check_button_selectors": [
            "button:has-text('Check')",
            "button:has-text('Check availability')",
            "[aria-label*='Check']",
        ],
        # --- Billing / shipping / address ---
        "billing_shipping_selectors": [
            "input[name*='address']",
            "input[name*='name']",
            "input[name*='phone']",
            "input[name*='email']",
            "input[name*='city']",
            "input[placeholder*='Address']",
            "input[placeholder*='Name']",
            "input[placeholder*='Phone']",
            "textarea[name*='address']",
        ],
        "email_field_selectors": [
            "input[type='email']",
            "input[name*='email']",
            "input[placeholder*='Email']",
            "#email",
        ],
        "pay_now_selectors": [
            "button:has-text('Pay now')",
            "button:has-text('Place order')",
            "button:has-text('Place Order')",
            "button[type='submit']",
            "[name*='pay']",
        ],
        # --- Menu / shop (header navigation) ---
        "menu_shop_selectors": [
            "a:has-text('Shop')",
            "button:has-text('Open Menu')",
            "button[aria-label*='menu']",
            "[aria-label*='Menu']",
            ".menu-toggle",
            "a:has-text('Close Menu')",
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


def get_selectors_for_intent(cfg: Optional[Dict[str, Any]], intent: str) -> list:
    """
    Return the list of selectors from app config for the given intent, or [].
    Used by router and generator to get layered selectors for any step intent.
    """
    if not cfg or not intent:
        return []
    key = INTENT_TO_SELECTORS_KEY.get(intent)
    if not key:
        return []
    return list(cfg.get(key) or [])
