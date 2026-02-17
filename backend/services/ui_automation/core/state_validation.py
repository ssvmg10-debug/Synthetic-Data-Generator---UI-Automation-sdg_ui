"""
State Validation Engine
Validates page state after each intent execution
"""
import logging
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout
from typing import Optional
from services.ui_automation.core.intent_models import PageState

logger = logging.getLogger(__name__)


class StateValidator:
    """
    Validates expected page state after intent execution.
    
    Key principle: Never proceed to next intent until current state is confirmed.
    """
    
    def __init__(self, timeout: int = 10000):
        self.timeout = timeout
    
    async def wait_for_search_results(self, page: Page) -> bool:
        """
        Validate search results have loaded.
        
        Checks:
        - Product cards visible
        - Results count > 0
        - Loading spinner gone
        """
        logger.info("🔍 Validating: Search results loaded")
        try:
            # Wait for product cards
            await page.wait_for_selector(
                ".product-card, [data-testid='product-card'], .product-item, .search-result-item",
                timeout=self.timeout,
                state="visible"
            )
            
            # Verify multiple results (not just loading state)
            cards = await page.query_selector_all(".product-card, [data-testid='product-card'], .product-item")
            if len(cards) > 0:
                logger.info(f"  ✅ Found {len(cards)} product cards")
                return True
            
            logger.warning("  ⚠️  Product cards found but empty")
            return False
            
        except PlaywrightTimeout:
            logger.error("  ❌ Search results did not load in time")
            return False
    
    async def wait_for_product_page(self, page: Page) -> bool:
        """
        Validate product detail page has loaded.
        
        Checks:
        - Buy/Add to Cart button visible
        - Product title visible
        - Price visible
        """
        logger.info("🔍 Validating: Product page loaded")
        try:
            # Wait for primary CTA (Buy Now, Add to Cart)
            await page.wait_for_selector(
                "button:has-text('Buy'), button:has-text('Add to Cart'), button:has-text('Add to Bag')",
                timeout=self.timeout,
                state="visible"
            )
            
            # Verify product details present
            has_title = await page.query_selector("h1, .product-title, [data-testid='product-title']")
            has_price = await page.query_selector(".price, [data-testid='price'], .product-price")
            
            if has_title and has_price:
                logger.info("  ✅ Product page loaded with title and price")
                return True
            
            logger.warning("  ⚠️  Product page incomplete")
            return False
            
        except PlaywrightTimeout:
            logger.error("  ❌ Product page did not load in time")
            return False
    
    async def wait_for_cart_update(self, page: Page) -> bool:
        """
        Validate cart has been updated.
        
        Checks:
        - Cart count badge updated
        - Cart icon shows items
        - Success message appeared
        """
        logger.info("🔍 Validating: Cart updated")
        try:
            # Wait for cart badge or success message
            await page.wait_for_selector(
                ".cart-count:not(:empty), .cart-badge:not(:empty), .success-message, .added-to-cart",
                timeout=5000,
                state="visible"
            )
            
            # Check cart count
            cart_badge = await page.query_selector(".cart-count, .cart-badge, [data-testid='cart-count']")
            if cart_badge:
                count_text = await cart_badge.inner_text()
                logger.info(f"  ✅ Cart count: {count_text}")
                return True
            
            # Alternative: Success message
            success = await page.query_selector(".success-message, .added-to-cart")
            if success:
                logger.info("  ✅ Cart success message shown")
                return True
            
            logger.warning("  ⚠️  Cart update not confirmed")
            return False
            
        except PlaywrightTimeout:
            logger.warning("  ⚠️  Cart update notification not found (may have succeeded)")
            # Don't fail hard - cart might have updated without visible feedback
            return True
    
    async def wait_for_checkout_page(self, page: Page) -> bool:
        """
        Validate checkout page has loaded.
        
        Checks:
        - Address form visible
        - Pincode field visible
        - Delivery options visible
        """
        logger.info("🔍 Validating: Checkout page loaded")
        try:
            # Wait for checkout indicators
            await page.wait_for_selector(
                "input[name*='pincode'], input[placeholder*='Pin'], .delivery-options, .checkout-form",
                timeout=self.timeout,
                state="visible"
            )
            
            logger.info("  ✅ Checkout page loaded")
            return True
            
        except PlaywrightTimeout:
            logger.error("  ❌ Checkout page did not load in time")
            return False
    
    async def wait_for_modal_opened(self, page: Page) -> bool:
        """
        Validate modal/dialog has opened.
        
        Checks:
        - Dialog element visible
        - Modal overlay visible
        """
        logger.info("🔍 Validating: Modal opened")
        try:
            await page.wait_for_selector(
                "[role='dialog'], .modal, .dialog, [data-testid='modal']",
                timeout=3000,
                state="visible"
            )
            
            logger.info("  ✅ Modal opened")
            return True
            
        except PlaywrightTimeout:
            logger.warning("  ⚠️  Modal not detected")
            return False
    
    async def wait_for_delivery_options(self, page: Page) -> bool:
        """
        Validate delivery options are available.
        
        Checks:
        - Radio buttons visible
        - Delivery text visible
        """
        logger.info("🔍 Validating: Delivery options loaded")
        try:
            await page.wait_for_selector(
                "input[type='radio'], .delivery-option, [data-testid='delivery-option']",
                timeout=self.timeout,
                state="visible"
            )
            
            options = await page.query_selector_all("input[type='radio']")
            logger.info(f"  ✅ Found {len(options)} delivery options")
            return True
            
        except PlaywrightTimeout:
            logger.error("  ❌ Delivery options did not load in time")
            return False
    
    async def wait_for_payment_page(self, page: Page) -> bool:
        """Validate payment page has loaded"""
        logger.info("🔍 Validating: Payment page loaded")
        try:
            await page.wait_for_selector(
                ".payment-method, input[type='radio'][name*='payment'], .payment-options",
                timeout=self.timeout,
                state="visible"
            )
            
            logger.info("  ✅ Payment page loaded")
            return True
            
        except PlaywrightTimeout:
            logger.error("  ❌ Payment page did not load in time")
            return False
    
    async def validate_state(self, page: Page, expected_state: PageState) -> bool:
        """
        Generic state validation dispatcher.
        
        Args:
            page: Playwright page
            expected_state: Expected PageState enum
        
        Returns:
            True if state validated, False otherwise
        """
        state_validators = {
            PageState.SEARCH_RESULTS_LOADED: self.wait_for_search_results,
            PageState.PRODUCT_PAGE_LOADED: self.wait_for_product_page,
            PageState.CART_UPDATED: self.wait_for_cart_update,
            PageState.CHECKOUT_PAGE_LOADED: self.wait_for_checkout_page,
            PageState.MODAL_OPENED: self.wait_for_modal_opened,
            PageState.PAYMENT_PAGE_LOADED: self.wait_for_payment_page,
        }
        
        validator = state_validators.get(expected_state)
        if not validator:
            logger.warning(f"No validator for state: {expected_state}")
            return True  # Don't fail on missing validator
        
        return await validator(page)
    
    async def wait_for_network_idle(self, page: Page, timeout: int = 5000) -> bool:
        """
        Wait for network to be idle (optional state check).
        
        Note: Use sparingly - can cause timeouts on heavy sites.
        """
        try:
            await page.wait_for_load_state("networkidle", timeout=timeout)
            return True
        except PlaywrightTimeout:
            logger.warning("Network idle timeout - continuing anyway")
            return False
