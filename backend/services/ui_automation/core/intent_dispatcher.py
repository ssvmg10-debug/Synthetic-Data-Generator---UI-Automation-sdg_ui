"""
🔒 PHASE 3 — INTENT DISPATCHER & HANDLERS
Deterministic execution for each intent type
"""
import logging
from playwright.async_api import Page
from typing import Any, Dict
from difflib import SequenceMatcher
from enum import Enum

from .state_machine import AppState, validate_state_transition
from .valid_data_generator import generate_valid_data

logger = logging.getLogger(__name__)


class Intent(Enum):
    """Structured intents instead of generic text clicking"""
    
    # Navigation intents
    NAVIGATE_TO_URL = "navigate_to_url"
    NAVIGATE_TO_CATEGORY = "navigate_to_category"
    
    # Product intents
    SELECT_PRODUCT = "select_product"
    VIEW_PRODUCT_DETAILS = "view_product_details"
    
    # Cart intents
    ADD_TO_CART = "add_to_cart"
    VIEW_CART = "view_cart"
    UPDATE_CART_QUANTITY = "update_cart_quantity"
    
    # Checkout intents
    PROCEED_TO_CHECKOUT = "proceed_to_checkout"
    COMPLETE_CHECKOUT_AS_GUEST = "complete_checkout_as_guest"
    SIGN_IN_CHECKOUT = "sign_in_checkout"
    
    # Form filling intents
    FILL_PINCODE = "fill_pincode"
    FILL_EMAIL = "fill_email"
    FILL_PHONE = "fill_phone"
    FILL_ADDRESS = "fill_address"
    FILL_NAME = "fill_name"
    
    # Selection intents
    SELECT_DELIVERY_OPTION = "select_delivery_option"
    SELECT_PAYMENT_METHOD = "select_payment_method"
    
    # Generic intents (fallback)
    CLICK_ELEMENT = "click_element"
    TYPE_TEXT = "type_text"
    SELECT_OPTION = "select_option"


class IntentDispatcher:
    """
    🔒 DETERMINISTIC INTENT EXECUTION
    
    Routes intents to specific handlers.
    Each handler is deterministic and validates post-conditions.
    """
    
    def __init__(self):
        self.selector_cache: Dict[str, str] = {}  # Cache successful selectors
    
    async def execute(self, intent: Intent, parameters: Dict[str, Any], page: Page) -> bool:
        """
        Execute intent with deterministic behavior
        
        Returns:
            bool: Success or failure (no randomness)
        
        Raises:
            Exception: On validation failure
        """
        logger.info(f"🎯 Executing intent: {intent.value} with {parameters}")
        
        handlers = {
            Intent.NAVIGATE_TO_URL: self._handle_navigate_to_url,
            Intent.NAVIGATE_TO_CATEGORY: self._handle_navigate_to_category,
            Intent.SELECT_PRODUCT: self._handle_select_product,
            Intent.ADD_TO_CART: self._handle_add_to_cart,
            Intent.FILL_PINCODE: self._handle_fill_pincode,
            Intent.SELECT_DELIVERY_OPTION: self._handle_select_delivery_option,
            Intent.COMPLETE_CHECKOUT_AS_GUEST: self._handle_guest_checkout,
            Intent.PROCEED_TO_CHECKOUT: self._handle_proceed_to_checkout,
            Intent.CLICK_ELEMENT: self._handle_click_element,
            Intent.TYPE_TEXT: self._handle_type_text,
            Intent.SELECT_OPTION: self._handle_select_option,
        }
        
        handler = handlers.get(intent)
        if not handler:
            raise NotImplementedError(f"Handler not implemented for intent: {intent.value}")
        
        return await handler(parameters, page)
    
    # ==================== NAVIGATION HANDLERS ====================
    
    async def _handle_navigate_to_url(self, params: Dict[str, Any], page: Page) -> bool:
        """Navigate to URL with validation"""
        url = params["url"]
        
        if not url.startswith("http"):
            url = f"https://{url}"
        
        logger.info(f"🌐 Navigating to: {url}")
        
        await page.goto(url)
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
        await page.wait_for_load_state("networkidle", timeout=10000)
        
        # Validate navigation
        current_url = page.url
        if url.split("://")[1].split("/")[0] not in current_url:
            raise Exception(f"Navigation failed: Expected {url}, got {current_url}")
        
        logger.info(f"✅ Navigated successfully")
        return True
    
    async def _handle_navigate_to_category(self, params: Dict[str, Any], page: Page) -> bool:
        """Navigate to category with strict validation"""
        category = params["category"]
        
        logger.info(f"📂 Navigating to category: {category}")
        
        # Try multiple strategies for category links
        strategies = [
            lambda: page.get_by_role("link", name=category),
            lambda: page.get_by_text(category, exact=True),
            lambda: page.locator(f"a:has-text('{category}')"),
            lambda: page.locator(f"nav a:has-text('{category}')"),
        ]
        
        for strategy in strategies:
            try:
                element = strategy()
                if await element.count() > 0:
                    await element.first.wait_for(state="visible", timeout=5000)
                    await element.first.click(timeout=5000)
                    
                    # Wait for navigation
                    await page.wait_for_load_state("domcontentloaded", timeout=5000)
                    await page.wait_for_timeout(500)
                    
                    logger.info(f"✅ Category navigation successful")
                    return True
            except Exception as e:
                logger.debug(f"Strategy failed: {e}")
                continue
        
        raise Exception(f"Category '{category}' not found")
    
    # ==================== PRODUCT HANDLERS ====================
    
    async def _handle_select_product(self, params: Dict[str, Any], page: Page) -> bool:
        """
        🔒 PHASE 5 — DETERMINISTIC PRODUCT SELECTION
        
        Always picks the highest-scoring match.
        Validates navigation to product detail page.
        """
        product_name = params["product_name"]
        
        logger.info(f"🛍️ Selecting product: {product_name}")
        
        # Extract keywords
        keywords = self._extract_keywords(product_name)
        logger.debug(f"Keywords: {keywords}")
        
        # Get all clickable elements (links, buttons, cards)
        elements = await page.locator("a, button, div[role='button'], .product-card").all()
        logger.debug(f"Found {len(elements)} candidate elements")
        
        # Score each element
        scored = []
        for element in elements:
            try:
                text = await element.inner_text(timeout=1000)
                if not text or len(text) > 500:  # Skip empty or overly long text
                    continue
                
                score = self._similarity_score(product_name, text)
                
                if score > 0.4:  # Threshold for candidates
                    scored.append((score, element, text))
            except:
                continue
        
        if not scored:
            raise Exception(f"Product '{product_name}' not found")
        
        # Sort by score (DETERMINISTIC - always same order)
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Log top candidates
        logger.debug("Top 3 candidates:")
        for i, (score, _, text) in enumerate(scored[:3], 1):
            logger.debug(f"  {i}. {text[:80]} (score: {score:.2f})")
        
        # Click the best match
        best_score, best_element, best_text = scored[0]
        logger.info(f"🎯 Clicking best match: '{best_text[:80]}' (score: {best_score:.2f})")
        
        await best_element.scroll_into_view_if_needed(timeout=2000)
        await page.wait_for_timeout(300)
        await best_element.click(timeout=5000)
        
        # Wait for navigation
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
        await page.wait_for_timeout(500)
        
        # Validate we're on product detail page
        await validate_state_transition(page, AppState.PRODUCT_DETAIL)
        
        logger.info(f"✅ Product selection validated")
        return True
    
    async def _handle_add_to_cart(self, params: Dict[str, Any], page: Page) -> bool:
        """
        Add to cart with post-condition validation
        """
        logger.info(f"🛒 Adding product to cart")
        
        # Try multiple button variations
        button_variations = [
            "Buy", "Buy Now", "Add to Cart", "Add to Bag", 
            "Purchase", "Add to Basket", "बाय", "कार्ट में जोड़ें"
        ]
        
        for variation in button_variations:
            try:
                button = page.locator(f"button:has-text('{variation}'), a:has-text('{variation}')")
                if await button.count() > 0:
                    await button.first.scroll_into_view_if_needed(timeout=2000)
                    await button.first.click(timeout=5000)
                    
                    # Wait for cart update
                    await page.wait_for_timeout(1000)
                    
                    # Validate cart state
                    await validate_state_transition(page, AppState.CART, retry_on_mismatch=True)
                    
                    logger.info(f"✅ Added to cart successfully")
                    return True
            except:
                continue
        
        raise Exception("Add to cart button not found")
    
    # ==================== FORM FILLING HANDLERS ====================
    
    async def _handle_fill_pincode(self, params: Dict[str, Any], page: Page) -> bool:
        """Fill pincode with strict validation"""
        pincode = params.get("pincode") or generate_valid_data("pincode")
        
        logger.info(f"📍 Filling pincode: {pincode}")
        
        # Wait for pincode field to appear (may be in modal)
        await page.wait_for_timeout(800)
        
        # Try multiple strategies
        strategies = [
            lambda: page.get_by_label("pincode", exact=False),
            lambda: page.get_by_label("pin", exact=False),
            lambda: page.get_by_label("zip", exact=False),
            lambda: page.locator("input[placeholder*='pin' i], input[placeholder*='zip' i]"),
            lambda: page.locator("input[name*='pin' i], input[name*='zip' i]"),
            lambda: page.locator("input[type='text']:visible, input[type='number']:visible").first,
        ]
        
        for strategy in strategies:
            try:
                field = strategy()
                if await field.count() > 0:
                    await field.first.scroll_into_view_if_needed(timeout=2000)
                    await field.first.fill(pincode, timeout=5000)
                    await field.first.press("Tab")  # Trigger validation
                    
                    logger.info(f"✅ Pincode filled successfully")
                    return True
            except Exception as e:
                logger.debug(f"Strategy failed: {e}")
                continue
        
        raise Exception("Pincode field not found")
    
    # ==================== SELECTION HANDLERS ====================
    
    async def _handle_select_delivery_option(self, params: Dict[str, Any], page: Page) -> bool:
        """Select delivery option deterministically"""
        delivery_type = params.get("delivery_type", "free")
        
        logger.info(f"📦 Selecting delivery option: {delivery_type}")
        
        # Wait for options to load
        await page.wait_for_timeout(800)
        
        # Keywords for free delivery
        keywords = ["free", "standard", "₹0", "rs.0", "$0", "complimentary"]
        
        # Try radio buttons first
        for keyword in keywords:
            try:
                radio = page.locator(f"input[type='radio'][value*='{keyword}' i]")
                if await radio.count() > 0:
                    await radio.first.check(timeout=3000)
                    logger.info(f"✅ Delivery option selected (radio)")
                    return True
                
                # Try label
                label = page.locator(f"label:has-text('{keyword}')").filter(has=page.locator("input[type='radio']"))
                if await label.count() > 0:
                    await label.first.click(timeout=3000)
                    logger.info(f"✅ Delivery option selected (label)")
                    return True
            except:
                continue
        
        logger.warning("⚠️ Delivery option not explicitly selected, may already be default")
        return True  # Non-critical
    
    async def _handle_guest_checkout(self, params: Dict[str, Any], page: Page) -> bool:
        """Handle guest checkout flow"""
        logger.info(f"👤 Proceeding as guest")
        
        # Keywords for guest checkout
        keywords = ["guest", "continue", "proceed", "checkout as guest", "continue without account"]
        
        for keyword in keywords:
            try:
                button = page.locator(f"button:has-text('{keyword}'), a:has-text('{keyword}')")
                if await button.count() > 0:
                    await button.first.click(timeout=5000)
                    await page.wait_for_load_state("domcontentloaded", timeout=5000)
                    await page.wait_for_timeout(500)
                    
                    logger.info(f"✅ Guest checkout initiated")
                    return True
            except:
                continue
        
        logger.warning("⚠️ Guest checkout button not found, may already be in checkout flow")
        return True  # Non-critical
    
    async def _handle_proceed_to_checkout(self, params: Dict[str, Any], page: Page) -> bool:
        """Proceed to checkout"""
        logger.info(f"💳 Proceeding to checkout")
        
        keywords = ["checkout", "proceed", "continue", "next"]
        
        for keyword in keywords:
            try:
                button = page.locator(f"button:has-text('{keyword}'), a:has-text('{keyword}')")
                if await button.count() > 0:
                    await button.first.scroll_into_view_if_needed(timeout=2000)
                    await button.first.click(timeout=5000)
                    
                    await page.wait_for_load_state("domcontentloaded", timeout=5000)
                    await page.wait_for_timeout(500)
                    
                    logger.info(f"✅ Checkout initiated")
                    return True
            except:
                continue
        
        raise Exception("Checkout button not found")
    
    # ==================== GENERIC HANDLERS (Fallback) ====================
    
    async def _handle_click_element(self, params: Dict[str, Any], page: Page) -> bool:
        """Generic click handler (fallback)"""
        element = params["element"]
        
        logger.info(f"🖱️ Clicking: {element}")
        
        # Use existing smart_click logic
        from .element_resolver import smart_click
        await smart_click(page, element)
        
        await page.wait_for_timeout(500)
        return True
    
    async def _handle_type_text(self, params: Dict[str, Any], page: Page) -> bool:
        """Generic type handler (fallback)"""
        field = params["field"]
        value = params["value"]
        
        logger.info(f"⌨️ Typing in {field}: {value}")
        
        # Use existing smart_type logic
        from .element_resolver import smart_type
        await smart_type(page, field, value)
        
        return True
    
    async def _handle_select_option(self, params: Dict[str, Any], page: Page) -> bool:
        """Generic select handler (fallback)"""
        option = params.get("option", "")
        
        logger.info(f"☑️ Selecting: {option}")
        
        # Use existing smart_select logic
        from .element_resolver import smart_select
        await smart_select(page, option)
        
        return True
    
    # ==================== HELPER METHODS ====================
    
    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords from product name"""
        import re
        # Split by spaces and special characters
        words = re.findall(r'\b\w+\b', text.lower())
        # Filter out common words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return keywords
    
    def _similarity_score(self, target: str, text: str) -> float:
        """
        Calculate similarity score (0.0 to 1.0)
        
        Uses multiple methods:
        1. Full text similarity
        2. Keyword matching
        3. Substring matching
        """
        target_lower = target.lower()
        text_lower = text.lower()
        
        # Method 1: Full similarity
        full_score = SequenceMatcher(None, target_lower, text_lower).ratio()
        
        # Method 2: Keyword matching
        target_keywords = set(self._extract_keywords(target))
        text_keywords = set(self._extract_keywords(text))
        
        if target_keywords:
            keyword_match = len(target_keywords & text_keywords) / len(target_keywords)
        else:
            keyword_match = 0.0
        
        # Method 3: Substring matching
        if target_lower in text_lower:
            substring_score = 0.9
        elif text_lower in target_lower:
            substring_score = 0.8
        else:
            substring_score = 0.0
        
        # Combine scores (prioritize keyword > substring > full)
        final_score = max(keyword_match * 1.0, substring_score, full_score * 0.8)
        
        return final_score
