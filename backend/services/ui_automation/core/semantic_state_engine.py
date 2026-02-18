"""
Production Semantic State Engine

State determined by primary DOM signals and structure, not URL alone.
Each state must satisfy at least 2 of its signals.
"""
import logging
from enum import Enum
from playwright.async_api import Page
from typing import List, Tuple

logger = logging.getLogger(__name__)


class SemanticState(str, Enum):
    """Semantic page states for e-commerce."""
    HOME = "home"
    CATEGORY = "category"
    PRODUCT_LIST = "product_list"
    PRODUCT_DETAIL = "product_detail"
    CART = "cart"
    CHECKOUT = "checkout"
    PAYMENT = "payment"
    ORDER_CONFIRMATION = "order_confirmation"
    UNKNOWN = "unknown"


# (description, locator_selector_or_text)
CATEGORY_SIGNALS: List[Tuple[str, str]] = [
    ("product_cards_5_plus", "div[class*='product']:visible, article[class*='product']:visible, [data-product]:visible"),
    ("filter_sidebar", "[class*='filter']:visible, [class*='sidebar']:visible, aside:visible"),
    ("breadcrumb", "[class*='breadcrumb']:visible, nav[aria-label*='breadcrumb']:visible"),
    ("pagination", "[class*='pagination']:visible, [class*='page-number']:visible, a[rel='next']:visible"),
]
PRODUCT_DETAIL_SIGNALS: List[Tuple[str, str]] = [
    ("single_h1", "h1"),
    ("price_element", "[class*='price']:visible, [data-price]:visible"),
    ("buy_now_button", "button:has-text('Buy'), button:has-text('Add to Cart'), [role='button']:has-text('Buy')"),
    ("product_specs", "[class*='spec']:visible, [class*='description']:visible, [class*='detail']:visible"),
]
CHECKOUT_SIGNALS: List[Tuple[str, str]] = [
    ("billing_fields", "input[name*='address'], input[placeholder*='address'], input[name*='email'], [class*='billing']:visible"),
    ("payment_options", "[class*='payment']:visible, [class*='payment-method']:visible"),
    ("place_order_button", "button:has-text('Place Order'), button:has-text('Pay'), button:has-text('Order')"),
]
CART_SIGNALS: List[Tuple[str, str]] = [
    ("cart_items", "[class*='cart']:visible, [class*='cart-item']:visible, text=Shopping Cart"),
    ("checkout_button", "button:has-text('Checkout'), a:has-text('Checkout')"),
]
AUTH_GUEST_SIGNALS: List[Tuple[str, str]] = [
    ("email_field", "input[type='email']:visible, input[name*='email']:visible"),
    ("guest_option", "text=Continue as guest, text=Guest checkout, text=Checkout as guest"),
]


async def _count_matches(page: Page, selector: str) -> int:
    try:
        return await page.locator(selector).count()
    except Exception:
        return 0


async def _signals_satisfied(page: Page, signals: List[Tuple[str, str]], min_count: int = 2) -> bool:
    satisfied = 0
    for _name, sel in signals:
        n = await _count_matches(page, sel)
        if "product_cards" in _name and n >= 5:
            satisfied += 1
        elif "single_h1" in _name and n == 1:
            satisfied += 1
        elif n > 0:
            satisfied += 1
    return satisfied >= min_count


async def detect_semantic_state(page: Page) -> SemanticState:
    """
    True production state: DOM signals + structure.
    State is semantic, not URL-based. At least 2 signals must match per state.
    URL is used to avoid false positives: do not return CHECKOUT/CART when URL clearly indicates category/list.
    """
    try:
        url = page.url.lower()
        # Do not classify as checkout/cart when URL is clearly category or product list (any site)
        url_looks_like_category = any(
            p in url for p in [
                "/category", "/categories", "/c/", "/shop", "/products", "/collections",
                "/air-solutions", "/air-conditioners", "/split-ac", "/home-appliances",
                "/tv", "/audio", "/refrigerators", "/washing", "/listing", "/listings", "/search?"
            ]
        ) and "/checkout" not in url and "/cart" not in url

        # CHECKOUT: billing + payment or place order (skip if URL is category-like to avoid footer false positive)
        if not url_looks_like_category and await _signals_satisfied(page, CHECKOUT_SIGNALS, 2):
            return SemanticState.CHECKOUT
        # CART (skip if URL is category-like)
        if not url_looks_like_category and await _signals_satisfied(page, CART_SIGNALS, 2):
            return SemanticState.CART
        # PRODUCT_DETAIL: H1 + price or Buy Now
        if await _signals_satisfied(page, PRODUCT_DETAIL_SIGNALS, 2):
            return SemanticState.PRODUCT_DETAIL
        # CATEGORY: product grid + filter or breadcrumb or pagination
        if await _signals_satisfied(page, CATEGORY_SIGNALS, 2):
            return SemanticState.CATEGORY
        # PRODUCT_LIST: many product cards (same as category for our purposes)
        product_cards = await _count_matches(
            page,
            "div[class*='product']:visible, article[class*='product']:visible, a[href*='/product']:visible",
        )
        if product_cards >= 3:
            return SemanticState.PRODUCT_LIST
        # Payment / order confirmation
        if await page.locator("text=Order Confirmed, text=Thank you for your order").count() > 0:
            return SemanticState.ORDER_CONFIRMATION
        if await page.locator("input[placeholder*='card'], input[name*='card']").count() > 0:
            return SemanticState.PAYMENT
        # URL fallback for compatibility
        url = page.url.lower()
        if "/checkout" in url:
            return SemanticState.CHECKOUT
        if "/cart" in url or "/bag" in url:
            return SemanticState.CART
        if "/product" in url or "/p/" in url:
            return SemanticState.PRODUCT_DETAIL
        if "/order" in url or "/confirmation" in url:
            return SemanticState.ORDER_CONFIRMATION
    except Exception as e:
        logger.debug(f"Semantic state detection error: {e}")
    return SemanticState.UNKNOWN


def semantic_state_to_app_state(semantic: SemanticState) -> str:
    """Map SemanticState to legacy AppState/PageState string."""
    return semantic.value
