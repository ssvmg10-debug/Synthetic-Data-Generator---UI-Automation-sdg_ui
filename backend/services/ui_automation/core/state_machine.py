"""
🔒 PHASE 1 — APPLICATION STATE MACHINE
Deterministic state tracking and validation
"""
import logging
from enum import Enum
from playwright.async_api import Page
from typing import Optional

logger = logging.getLogger(__name__)


class AppState(Enum):
    """Application states for e-commerce flow"""
    HOME = "home"
    CATEGORY = "category"
    PRODUCT_LIST = "product_list"
    PRODUCT_DETAIL = "product_detail"
    CART = "cart"
    CHECKOUT = "checkout"
    PAYMENT = "payment"
    ORDER_CONFIRMATION = "order_confirmation"
    UNKNOWN = "unknown"


class StateDetectionRules:
    """URL and DOM-based state detection rules"""
    
    @staticmethod
    def detect_by_url(url: str) -> AppState:
        """Detect state from URL patterns"""
        url_lower = url.lower()
        
        # Order matters - most specific first
        if "/order" in url_lower or "/confirmation" in url_lower or "/success" in url_lower:
            return AppState.ORDER_CONFIRMATION
        
        if "/payment" in url_lower or "/pay" in url_lower:
            return AppState.PAYMENT
        
        if "/checkout" in url_lower:
            return AppState.CHECKOUT
        
        if "/cart" in url_lower or "/basket" in url_lower or "/bag" in url_lower:
            return AppState.CART
        
        # Product detail pages - very specific patterns
        if "/products/" in url_lower or "/product/" in url_lower or "/p/" in url_lower:
            return AppState.PRODUCT_DETAIL
        
        # Product list/category pages
        if any(cat in url_lower for cat in [
            "/air-conditioners", "/split-ac", "/category/", "/c/",
            "/search", "/products", "/shop"
        ]):
            return AppState.PRODUCT_LIST
        
        # Category/section pages
        if any(cat in url_lower for cat in ["/air-solutions", "/appliances", "/category"]):
            return AppState.CATEGORY
        
        # Homepage patterns
        if url_lower.endswith("/") or url_lower.endswith("/in") or url_lower.endswith("/home"):
            return AppState.HOME
        
        return AppState.UNKNOWN
    
    @staticmethod
    async def detect_by_dom(page: Page) -> AppState:
        """Detect state from DOM elements (fallback)"""
        try:
            # Check for order confirmation
            if await page.locator("text=Order Confirmed, text=Thank you for your order").count() > 0:
                return AppState.ORDER_CONFIRMATION
            
            # Check for payment page
            if await page.locator("input[type='text'][placeholder*='card'], input[name*='card']").count() > 0:
                return AppState.PAYMENT
            
            # Check for checkout page
            if await page.locator("text=Checkout, text=Delivery Address").count() > 0:
                return AppState.CHECKOUT
            
            # Check for cart page
            if await page.locator("text=Shopping Cart, text=Cart Items, .cart-items").count() > 0:
                return AppState.CART
            
            # Check for product detail (Buy button, Add to Cart)
            if await page.locator("button:has-text('Buy'), button:has-text('Add to Cart')").count() > 0:
                # Verify it's a detail page, not a listing
                if await page.locator(".product-title, .product-name, h1.product").count() > 0:
                    return AppState.PRODUCT_DETAIL
            
            # Check for product list (multiple product cards)
            product_cards = await page.locator("a[href*='/product'], div.product-card, .product-item").count()
            if product_cards >= 3:
                return AppState.PRODUCT_LIST
            
            return AppState.UNKNOWN
            
        except Exception as e:
            logger.debug(f"DOM detection error: {e}")
            return AppState.UNKNOWN


async def detect_state(page: Page) -> AppState:
    """
    🔒 DETERMINISTIC STATE DETECTION
    
    Priority:
    1. URL-based detection (fast, reliable)
    2. DOM-based detection (fallback)
    
    Returns:
        AppState: Current application state
    """
    url = page.url
    logger.debug(f"🔍 Detecting state from URL: {url}")
    
    # Try URL-based detection first
    state = StateDetectionRules.detect_by_url(url)
    
    if state != AppState.UNKNOWN:
        logger.info(f"✅ State detected (URL): {state.value}")
        return state
    
    # Fallback to DOM-based detection
    logger.debug("⚠️ URL detection inconclusive, trying DOM...")
    state = await StateDetectionRules.detect_by_dom(page)
    
    logger.info(f"✅ State detected (DOM): {state.value}")
    return state


async def validate_state_transition(
    page: Page,
    expected_state: AppState,
    timeout: int = 5000,
    retry_on_mismatch: bool = True
) -> bool:
    """
    🔒 STRICT STATE VALIDATION
    
    After every instruction, verify we're in the expected state.
    
    Args:
        page: Playwright page
        expected_state: Expected state after action
        timeout: Max wait time for state transition
        retry_on_mismatch: Whether to retry detection once if mismatch
    
    Returns:
        bool: True if state matches, raises exception otherwise
    
    Raises:
        StateTransitionError: If state doesn't match after retries
    """
    logger.info(f"🎯 Validating state transition to: {expected_state.value}")
    
    # Wait for navigation to complete
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=timeout)
    except:
        logger.debug("Load state wait timeout (may already be loaded)")
    
    # Small wait for client-side rendering
    await page.wait_for_timeout(500)
    
    # Detect current state
    current_state = await detect_state(page)
    
    if current_state == expected_state:
        logger.info(f"✅ State validation PASSED: {current_state.value}")
        return True
    
    # Retry once if mismatch (for dynamic content)
    if retry_on_mismatch:
        logger.warning(f"⚠️ State mismatch! Expected: {expected_state.value}, Got: {current_state.value}")
        logger.info("🔄 Retrying state detection after 1s...")
        await page.wait_for_timeout(1000)
        
        current_state = await detect_state(page)
        
        if current_state == expected_state:
            logger.info(f"✅ State validation PASSED (retry): {current_state.value}")
            return True
    
    # STRICT FAILURE - No drifting allowed
    error_msg = (
        f"❌ STATE TRANSITION FAILED\n"
        f"   Expected: {expected_state.value}\n"
        f"   Current:  {current_state.value}\n"
        f"   URL:      {page.url}\n"
        f"   Action:   STOPPED (no drifting allowed)"
    )
    logger.error(error_msg)
    raise StateTransitionError(error_msg)


class StateTransitionError(Exception):
    """Raised when state transition validation fails"""
    pass


# State transition rules (for validation)
STATE_TRANSITIONS = {
    AppState.HOME: [AppState.CATEGORY, AppState.PRODUCT_LIST, AppState.HOME],
    AppState.CATEGORY: [AppState.PRODUCT_LIST, AppState.HOME],
    AppState.PRODUCT_LIST: [AppState.PRODUCT_DETAIL, AppState.PRODUCT_LIST, AppState.CATEGORY],
    AppState.PRODUCT_DETAIL: [AppState.CART, AppState.PRODUCT_DETAIL, AppState.PRODUCT_LIST],
    AppState.CART: [AppState.CHECKOUT, AppState.CART, AppState.PRODUCT_DETAIL],
    AppState.CHECKOUT: [AppState.PAYMENT, AppState.CHECKOUT, AppState.CART],
    AppState.PAYMENT: [AppState.ORDER_CONFIRMATION, AppState.PAYMENT, AppState.CHECKOUT],
    AppState.ORDER_CONFIRMATION: [AppState.ORDER_CONFIRMATION, AppState.HOME],
}


def is_valid_transition(from_state: AppState, to_state: AppState) -> bool:
    """Check if state transition is valid"""
    valid_transitions = STATE_TRANSITIONS.get(from_state, [])
    return to_state in valid_transitions
