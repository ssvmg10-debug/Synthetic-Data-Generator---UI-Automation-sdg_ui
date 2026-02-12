"""
UI Intent taxonomy and classifier for enterprise UI automation.
Maps human instructions to UI intents so Planner/Generator never output generic role=button.
"""
from typing import Dict, Any, List, Optional
import re
import logging

logger = logging.getLogger(__name__)

# Intent taxonomy: intent -> semantic_target (preferred element type) and fallback semantics
INTENT_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "search_box": {
        "semantic_target": "input/search",
        "fallback_semantics": ["input", "input[type=search]", "input[placeholder*='Search']", "[aria-label*='Search']", "search icon", "button with search icon"],
        "selector_hints": ["input[type='search']", "input[placeholder*='Search']", "input[name*='search']", "[aria-label*='Search']", "input[type='text']"],
    },
    "search_submit": {
        "semantic_target": "button/submit",
        "fallback_semantics": ["button", "submit", "search button", "magnifying icon"],
        "selector_hints": ["button[type='submit']", "button:has-text('Search')", "[aria-label*='Search']", "button:has(svg)"],
    },
    "cookie_accept": {
        "semantic_target": "button",
        "fallback_semantics": ["Accept all", "Accept", "I agree", "OK", "Close cookie", "Save & Proceed", "Reject All"],
        "selector_hints": ["button:has-text('Accept')", "button:has-text('Accept all')", "[id*='cookie'] button", ".cookie-accept", "button:has-text('I agree')"],
    },
    "login": {
        "semantic_target": "button/link",
        "fallback_semantics": ["Sign in", "Login", "Log in", "Sign in button"],
        "selector_hints": ["a:has-text('Sign in')", "a:has-text('Login')", "button:has-text('Sign in')", "[href*='login']"],
    },
    "product_select": {
        "semantic_target": "link/button",
        "fallback_semantics": ["product link", "Buy now", "Add to cart", "product card"],
        "selector_hints": ["a[href*='product']", ".product a", "button:has-text('Buy now')", "button:has-text('Add to cart')", "[data-product]"],
    },
    "add_to_cart": {
        "semantic_target": "button",
        "fallback_semantics": ["Add to cart", "Add to bag", "Buy"],
        "selector_hints": ["button:has-text('Add to cart')", "[id*='add-to-cart']", ".add-to-cart", "button[name='add']"],
    },
    "cart": {
        "semantic_target": "link/button",
        "fallback_semantics": ["Cart", "View cart", "My cart", "Basket"],
        "selector_hints": ["a[href*='cart']", "a:has-text('Cart')", "[aria-label*='cart']", ".cart-icon"],
    },
    "checkout": {
        "semantic_target": "button/link",
        "fallback_semantics": ["Checkout", "Check out", "Proceed to checkout"],
        "selector_hints": ["button:has-text('Checkout')", "a:has-text('Checkout')", "[data-action='checkout']", ".checkout-btn"],
    },
    "guest_checkout": {
        "semantic_target": "button/link",
        "fallback_semantics": ["Continue as guest", "Guest", "Continue as guest or Continue"],
        "selector_hints": ["button:has-text('Continue as guest')", "button:has-text('Guest')", "a:has-text('Continue as guest')", "button:has-text('Continue')"],
    },
    "email_field": {
        "semantic_target": "input",
        "fallback_semantics": ["email", "Email address"],
        "selector_hints": ["input[type='email']", "input[name*='email']", "input[placeholder*='Email']", "#email"],
    },
    "pincode_zip": {
        "semantic_target": "input",
        "fallback_semantics": ["pincode", "zip", "postal code", "postcode"],
        "selector_hints": ["input[name*='zip']", "input[name*='postal']", "input[placeholder*='Pincode']", "input[placeholder*='Zip']", "#zip", "#pincode"],
    },
    "billing_shipping": {
        "semantic_target": "input/textarea",
        "fallback_semantics": ["address", "name", "phone", "city", "state", "billing", "shipping"],
        "selector_hints": ["input[name*='address']", "input[name*='name']", "input[name*='phone']", "input[name*='city']", "textarea[name*='address']"],
    },
    "pay_now": {
        "semantic_target": "button",
        "fallback_semantics": ["Pay now", "Place order", "Submit order"],
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
        if any(w in el or w in desc for w in ["search", "search icon", "search button", "magnify"]):
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
