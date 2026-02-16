"""
UI Intent taxonomy and classifier for enterprise UI automation.
Maps human instructions to UI intents so Planner/Generator never output generic role=button.
"""
from typing import Dict, Any, List, Optional
import re
import logging

logger = logging.getLogger(__name__)

# Playwright locator_hint: prefer get_by_role / get_by_placeholder / get_by_label (resilient to DOM changes)
# Keys: role, name (optional, for role), placeholder, label. Executor tries these before CSS selector.
LOCATOR_HINT_KEY = "locator_hint"

# Intent taxonomy: intent -> semantic_target, fallback_semantics, selector_hints, and optional locator_hint
INTENT_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "search_box": {
        "semantic_target": "input/search",
        "fallback_semantics": ["input", "input[type=search]", "input[placeholder*='Search']", "[aria-label*='Search']", "search icon", "button with search icon"],
        "locator_hint": {"role": "searchbox"},
        "selector_hints": [
            "input[type='search']",
            "input[name='q']",
            "input[name='search']",
            "input[placeholder*='Search']",
            "input[aria-label*='Search']",
            "[role='search'] input",
            "input[type='text']",
        ],
    },
    "search_icon": {
        "semantic_target": "link/button",
        "fallback_semantics": ["search", "search icon", "open search", "search link"],
        "locator_hint": {"role": "link", "name": "Search"},
        "selector_hints": [
            "a:has-text('Search')",
            "button:has-text('Search')",
            "[aria-label*='Search']",
            ".search-icon",
            "[href*='search']",
            "nav a:has-text('Search')",
        ],
    },
    "search_submit": {
        "semantic_target": "button/submit",
        "fallback_semantics": ["button", "submit", "search button", "magnifying icon"],
        "locator_hint": {"role": "button", "name": "Search"},
        "selector_hints": [
            "button[type='submit']",
            "form[role='search'] button[type='submit']",
            "[aria-label*='Search']",
            "button:has-text('Search')",
            "button:has(svg)",
        ],
    },
    "cookie_accept": {
        "semantic_target": "button",
        "fallback_semantics": ["Accept all", "Accept", "I agree", "OK", "Close cookie", "Save & Proceed", "Reject All"],
        "locator_hint": {"role": "button", "name": "Accept all"},
        "selector_hints": [
            "[role='button']:has-text('Accept all')",
            "button:has-text('Accept all')",
            "button:has-text('Accept')",
            "a:has-text('Accept all')",
            "[id*='cookie'] button",
            ".cookie-accept",
            "button:has-text('I agree')",
        ],
    },
    "login": {
        "semantic_target": "button/link",
        "fallback_semantics": ["Sign in", "Login", "Log in", "Sign in button"],
        "locator_hint": {"role": "link", "name": "Sign in"},
        "selector_hints": ["a:has-text('Sign in')", "a:has-text('Login')", "button:has-text('Sign in')", "[href*='login']"],
    },
    "product_select": {
        "semantic_target": "link/button",
        "fallback_semantics": ["product link", "Buy now", "Add to cart", "product card"],
        "selector_hints": ["a[href*='product']", ".product a", "button:has-text('Buy now')", "button:has-text('Add to cart')", "[data-product]"],
    },
    "select_product_with_condition": {
        "semantic_target": "product_card",
        "fallback_semantics": ["product under price", "Buy now under", "first product below"],
        "selector_hints": ["button:has-text('Buy Now')", "a:has-text('Know More')", ".cmp-button"],
    },
    "add_to_cart": {
        "semantic_target": "button",
        "fallback_semantics": ["Add to cart", "Add to bag", "Buy"],
        "locator_hint": {"role": "button", "name": "Add to cart"},
        "selector_hints": ["button:has-text('Add to cart')", "[id*='add-to-cart']", ".add-to-cart", "button[name='add']"],
    },
    "cart": {
        "semantic_target": "link/button",
        "fallback_semantics": ["Cart", "View cart", "My cart", "Basket"],
        "locator_hint": {"role": "link", "name": "Cart"},
        "selector_hints": ["a[href*='cart']", "a:has-text('Cart')", "[aria-label*='cart']", ".cart-icon"],
    },
    "checkout": {
        "semantic_target": "button/link",
        "fallback_semantics": ["Checkout", "Check out", "Proceed to checkout"],
        "locator_hint": {"role": "button", "name": "Checkout"},
        "selector_hints": ["button:has-text('Checkout')", "a:has-text('Checkout')", "[data-action='checkout']", ".checkout-btn"],
    },
    "guest_checkout": {
        "semantic_target": "button/link",
        "fallback_semantics": ["Continue as guest", "Guest", "Continue as guest or Continue"],
        "locator_hint": {"role": "button", "name": "Continue as guest"},
        "selector_hints": ["button:has-text('Continue as guest')", "button:has-text('Guest')", "a:has-text('Continue as guest')", "button:has-text('Continue')"],
    },
    "email_field": {
        "semantic_target": "input",
        "fallback_semantics": ["email", "Email address"],
        "locator_hint": {"role": "textbox", "name": "email"},
        "selector_hints": ["input[type='email']", "input[name*='email']", "input[placeholder*='Email']", "#email"],
    },
    "pincode_zip": {
        "semantic_target": "input",
        "fallback_semantics": ["pincode", "zip", "postal code", "postcode"],
        "locator_hint": {"placeholder": "Pincode"},
        "selector_hints": ["input[name*='zip']", "input[name*='postal']", "input[placeholder*='Pincode']", "input[placeholder*='Zip']", "#zip", "#pincode"],
    },
    "pincode_check": {
        "semantic_target": "button",
        "fallback_semantics": ["Check", "Check availability", "Verify pincode"],
        "locator_hint": {"role": "button", "name": "Check"},
        "selector_hints": ["button:has-text('Check')", "button:has-text('Check availability')", "[aria-label*='Check']"],
    },
    "billing_shipping": {
        "semantic_target": "input/textarea",
        "fallback_semantics": ["address", "name", "phone", "city", "state", "billing", "shipping"],
        "locator_hint": {"placeholder": "Address"},
        "selector_hints": ["input[name*='address']", "input[name*='name']", "input[name*='phone']", "input[name*='city']", "textarea[name*='address']"],
    },
    "pay_now": {
        "semantic_target": "button",
        "fallback_semantics": ["Pay now", "Place order", "Submit order"],
        "locator_hint": {"role": "button", "name": "Pay now"},
        "selector_hints": ["button:has-text('Pay now')", "button[type='submit']", "[name='paynow']", "button:has-text('Place order')"],
    },
    "menu_shop": {
        "semantic_target": "button/link",
        "fallback_semantics": ["Shop", "Menu", "Open menu", "Hamburger"],
        "selector_hints": ["button[aria-label*='menu']", "a:has-text('Shop')", ".menu-toggle", ".hamburger", "[class*='menu']"],
    },
    "generic_click": {
        "semantic_target": "button/link",
        "fallback_semantics": ["button", "link", "element"],
        "selector_hints": ["button", "a", "[role='button']"],
    },
    "generic_type": {
        "semantic_target": "input/textarea",
        "fallback_semantics": ["input", "field", "editable"],
        "selector_hints": ["input", "textarea", "[contenteditable='true']"],
    },
}


def classify_intent(action: str, element: str, description: str = "") -> str:
    """
    Classify UI intent from action + element (+ optional description).
    Returns intent key from INTENT_TAXONOMY (e.g. search_box, cookie_accept).
    """
    text = f"{action} {element} {description}".lower()
    el = (element or "").lower()
    desc = (description or "").lower()

    if action == "type" or action == "fill":
        if any(w in el or w in desc for w in ["search", "search box", "search bar", "query"]):
            return "search_box"
        if any(w in el or w in desc for w in ["email", "e-mail"]):
            return "email_field"
        if any(w in el or w in desc for w in ["pincode", "zip", "postal", "postcode"]):
            return "pincode_zip"
        if any(w in el or w in desc for w in ["address", "billing", "shipping", "name", "phone", "city"]):
            return "billing_shipping"
        return "generic_type"

    if action == "click":
        if any(w in el or w in desc for w in ["search option", "search icon", "open search", "click search"]):
            return "search_icon"
        if any(w in el or w in desc for w in ["search", "search button", "magnify"]):
            return "search_submit" if "submit" in el or "button" in el else "search_box"
        if any(w in el or w in desc for w in ["cookie", "accept all", "accept", "privacy", "i agree", "reject all"]):
            return "cookie_accept"
        if any(w in el or w in desc for w in ["sign in", "signin", "login", "log in"]):
            return "login"
        if any(w in el or w in desc for w in ["buy now", "buy now button", "add to cart", "add to bag"]):
            return "add_to_cart"
        if any(w in el or w in desc for w in ["cart", "view cart", "my cart", "basket"]):
            return "cart"
        if any(w in el or w in desc for w in ["checkout", "check out", "proceed"]):
            return "checkout"
        if any(w in el or w in desc for w in ["check", "check availability", "check pincode"]) and any(w in (el + " " + desc) for w in ["pincode", "zip", "delivery", "availability"]):
            return "pincode_check"
        if any(w in el or w in desc for w in ["guest", "continue as guest", "complete purchase as guest"]):
            return "guest_checkout"
        if any(w in el or w in desc for w in ["pay now", "place order", "paynow"]):
            return "pay_now"
        if any(w in el or w in desc for w in ["shop", "menu", "hamburger", "open menu"]):
            return "menu_shop"
        if any(w in el or w in desc for w in ["product", "first product", "buy now for"]):
            return "product_select"
        return "generic_click"

    return "generic_click" if action == "click" else "generic_type"


def get_intent_semantics(intent: str) -> Dict[str, Any]:
    """Return semantic_target and fallback_semantics for an intent."""
    return INTENT_TAXONOMY.get(intent, INTENT_TAXONOMY["generic_click"]).copy()


def get_selector_hints_for_intent(intent: str) -> List[str]:
    """Return ordered selector hints for this intent (for Generator/Healer)."""
    entry = INTENT_TAXONOMY.get(intent)
    if not entry:
        return []
    return list(entry.get("selector_hints", []))


def get_locator_hint_for_intent(intent: str) -> Optional[Dict[str, Any]]:
    """Return Playwright locator_hint (role/placeholder/label) for this intent. Executor uses get_by_role/get_by_placeholder first."""
    entry = INTENT_TAXONOMY.get(intent)
    if not entry:
        return None
    hint = entry.get("locator_hint")
    if isinstance(hint, dict) and hint:
        return hint
    return None
