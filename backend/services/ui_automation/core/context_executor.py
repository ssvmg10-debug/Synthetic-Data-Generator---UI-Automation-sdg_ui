"""
Context-Aware Executor - Executes actions based on page context and intent.

This is Layer 3 of the state-driven automation architecture.
Provides intelligent, scoped execution based on page understanding.
"""
import logging
from typing import Dict, Any, Optional
from playwright.async_api import Page

from .page_intelligence import PageIntelligenceEngine, PageType
from .intent_normalizer import IntentNormalizer, NormalizedIntent, ActionIntent
from .product_matcher import ProductSimilarityEngine, ProductMatch
from .element_resolver import smart_click, smart_type

logger = logging.getLogger(__name__)


class ContextAwareExecutor:
    """
    Executes actions with full context awareness.
    
    Key capabilities:
    - Understands current page type
    - Scopes element search to relevant containers
    - Uses semantic matching for products
    - Validates state transitions
    """
    
    def __init__(self, page: Page):
        self.page = page
        self.intelligence = PageIntelligenceEngine(page)
        self.normalizer = IntentNormalizer()
        self.product_matcher = ProductSimilarityEngine()
        self.execution_history = []
    
    async def execute_intent(
        self,
        intent: NormalizedIntent,
        validate_transition: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a normalized intent with full context awareness.
        
        Args:
            intent: Normalized intent to execute
            validate_transition: Whether to validate state transition after
        
        Returns:
            Execution result with success, message, state
        """
        logger.info(f"🎯 Executing: {intent}")
        
        # Detect current page state BEFORE action
        current_state = await self.intelligence.detect_page_type()
        
        result = {
            "success": False,
            "message": "",
            "intent": intent,
            "pre_state": current_state.page_type.value,
            "post_state": None
        }
        
        try:
            # Route to appropriate handler based on intent
            if intent.action == ActionIntent.NAVIGATE:
                success = await self._execute_navigate(intent)
            
            elif intent.action == ActionIntent.SEARCH_PRODUCT:
                success = await self._execute_search(intent, current_state)
            
            elif intent.action in [ActionIntent.SELECT_PRODUCT, ActionIntent.BUY_PRODUCT, ActionIntent.ADD_TO_CART]:
                success = await self._execute_product_action(intent, current_state)
            
            elif intent.action == ActionIntent.VERIFY_DELIVERY:
                success = await self._execute_verify_delivery(intent, current_state)
            
            elif intent.action == ActionIntent.SELECT_DELIVERY_METHOD:
                success = await self._execute_select_delivery(intent, current_state)
            
            elif intent.action == ActionIntent.CHECKOUT:
                success = await self._execute_checkout(intent, current_state)
            
            elif intent.action == ActionIntent.GUEST_CHECKOUT:
                success = await self._execute_guest_checkout(intent, current_state)
            
            elif intent.action == ActionIntent.CLICK_ELEMENT:
                success = await self._execute_click(intent, current_state)
            
            elif intent.action == ActionIntent.TYPE_TEXT:
                success = await self._execute_type(intent, current_state)
            
            elif intent.action == ActionIntent.WAIT:
                success = await self._execute_wait(intent)
            
            else:
                logger.warning(f"⚠️ Unhandled intent action: {intent.action}")
                success = await self._execute_fallback(intent, current_state)
            
            result["success"] = success
            
            # Validate state transition if requested
            if validate_transition and success:
                expected_type = self.normalizer.get_expected_page_transition(intent)
                if expected_type:
                    await self.intelligence.validate_state_transition(
                        PageType[expected_type] if expected_type else None
                    )
                else:
                    await self.intelligence.detect_page_type()
                
                result["post_state"] = self.intelligence.current_state.page_type.value
            
            if success:
                result["message"] = f"Successfully executed {intent.action.value}"
                logger.info(f"✅ {result['message']}")
            else:
                result["message"] = f"Failed to execute {intent.action.value}"
                logger.error(f"❌ {result['message']}")
        
        except Exception as e:
            result["success"] = False
            result["message"] = f"Exception during execution: {str(e)}"
            logger.error(f"❌ {result['message']}")
        
        self.execution_history.append(result)
        return result
    
    async def _execute_navigate(self, intent: NormalizedIntent) -> bool:
        """Execute navigation intent."""
        try:
            url = intent.target
            logger.info(f"🌐 Navigating to: {url}")
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return True
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return False
    
    async def _execute_search(
        self,
        intent: NormalizedIntent,
        state: Any
    ) -> bool:
        """Execute search intent - context aware."""
        search_term = intent.target
        
        # Check if modal is open (search overlay)
        if state.page_type == PageType.MODAL or state.snapshot["signals"].get("has_modal"):
            logger.info("🔍 Modal detected, scoping search to modal")
            container = self.page.locator('[role="dialog"]:visible').first
        else:
            container = self.page
        
        # Find search input
        search_selectors = [
            'input[type="search"]',
            'input[placeholder*="search" i]',
            'input[aria-label*="search" i]',
            'input[name*="search" i]',
            'input[class*="search" i]',
        ]
        
        for selector in search_selectors:
            try:
                input_elem = container.locator(selector).first
                if await input_elem.count() > 0 and await input_elem.is_visible():
                    logger.info(f"✅ Found search input: {selector}")
                    await input_elem.fill(search_term)
                    await input_elem.press("Enter")
                    await self.page.wait_for_load_state("domcontentloaded", timeout=5000)
                    return True
            except:
                continue
        
        logger.error("❌ Could not find search input")
        return False
    
    async def _execute_product_action(
        self,
        intent: NormalizedIntent,
        state: Any
    ) -> bool:
        """
        Execute product-related action with intelligent matching.
        
        This is the key improvement: instead of text matching,
        we find the product card and scope actions to it.
        """
        product_name = intent.target
        action_type = intent.action
        
        logger.info(f"🛍️ Product action: {action_type.value} for '{product_name}'")
        
        # Determine appropriate container selector based on page type
        if state.page_type == PageType.PRODUCT_LISTING:
            container_selectors = [
                '[class*="product-card"]',
                '[class*="product-item"]',
                '[data-product-id]',
                'article[class*="product"]',
                '.product',
            ]
        elif state.page_type == PageType.SEARCH_RESULTS:
            container_selectors = [
                '[class*="search-result"]',
                '[class*="product-card"]',
                '[class*="result-item"]',
            ]
        elif state.page_type == PageType.PRODUCT_DETAIL:
            # On product detail page, no need to find product card
            return await self._execute_product_detail_action(intent)
        else:
            container_selectors = [
                '[class*="product"]',
            ]
        
        # Try each container selector
        for selector in container_selectors:
            try:
                match = await self.product_matcher.find_best_product_match(
                    self.page,
                    product_name,
                    selector
                )
                
                if match:
                    logger.info(f"✅ Found matching product: {match.product_name}")
                    
                    # Execute action on the matched product container
                    return await self._execute_action_on_product(match, action_type)
                
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
                continue
        
        logger.error(f"❌ Could not find product matching: {product_name}")
        return False
    
    async def _execute_action_on_product(
        self,
        product_match: ProductMatch,
        action_type: ActionIntent
    ) -> bool:
        """Execute specific action on matched product container."""
        container = product_match.element_handle
        
        # Define button selectors based on action
        if action_type in [ActionIntent.BUY_PRODUCT, ActionIntent.ADD_TO_CART]:
            button_selectors = [
                'button:has-text("Buy Now")',
                'button:has-text("Add to Cart")',
                'button:has-text("Add to Basket")',
                'a:has-text("Buy Now")',
                '[class*="buy"]',
                '[class*="add-to-cart"]',
            ]
        elif action_type == ActionIntent.SELECT_PRODUCT:
            button_selectors = [
                'a[href*="product"]',
                'button',
                'h1', 'h2', 'h3',  # Click on title
            ]
        else:
            button_selectors = ['button', 'a']
        
        # Try to click within the scoped container
        for selector in button_selectors:
            try:
                button = container.locator(selector).first
                if await button.count() > 0:
                    logger.info(f"🎯 Clicking: {selector} within product container")
                    await button.click()
                    await self.page.wait_for_load_state("domcontentloaded", timeout=5000)
                    return True
            except Exception as e:
                logger.debug(f"Could not click {selector}: {e}")
                continue
        
        # Fallback: click the container itself
        try:
            logger.info("🎯 Clicking product container itself")
            await container.click()
            await self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            return True
        except Exception as e:
            logger.error(f"Could not click product container: {e}")
            return False
    
    async def _execute_product_detail_action(self, intent: NormalizedIntent) -> bool:
        """Execute action on product detail page."""
        button_texts = ["Buy Now", "Add to Cart", "Add to Basket", "Purchase"]
        
        for text in button_texts:
            try:
                button = self.page.locator(f'button:has-text("{text}"), a:has-text("{text}")').first
                if await button.count() > 0:
                    logger.info(f"✅ Found button: {text}")
                    await button.click()
                    await self.page.wait_for_load_state("domcontentloaded", timeout=5000)
                    return True
            except:
                continue
        
        return False
    
    async def _execute_verify_delivery(
        self,
        intent: NormalizedIntent,
        state: Any
    ) -> bool:
        """Execute delivery verification (pincode entry)."""
        pincode = intent.value
        
        # Find pincode input
        selectors = [
            'input[name*="pincode" i]',
            'input[placeholder*="pincode" i]',
            'input[name*="zip" i]',
            'input[name*="postal" i]',
            'input[type="text"][class*="pin"]',
        ]
        
        for selector in selectors:
            try:
                input_elem = self.page.locator(selector).first
                if await input_elem.count() > 0 and await input_elem.is_visible():
                    logger.info(f"✅ Found pincode input: {selector}")
                    await input_elem.fill(pincode)
                    
                    # Find and click check button
                    check_buttons = [
                        'button:has-text("Check")',
                        'button:has-text("Verify")',
                        'button:near(:text("pincode"))',
                    ]
                    
                    for btn_selector in check_buttons:
                        try:
                            btn = self.page.locator(btn_selector).first
                            if await btn.count() > 0:
                                await btn.click()
                                await self.page.wait_for_timeout(2000)
                                return True
                        except:
                            continue
                    
                    # Fallback: just press Enter
                    await input_elem.press("Enter")
                    await self.page.wait_for_timeout(2000)
                    return True
            except:
                continue
        
        return False
    
    async def _execute_select_delivery(
        self,
        intent: NormalizedIntent,
        state: Any
    ) -> bool:
        """Select delivery method (e.g., free delivery)."""
        # Look for radio buttons or options related to delivery
        selectors = [
            'input[type="radio"][value*="free" i]',
            'label:has-text("Free Delivery")',
            '[class*="delivery-option"]:has-text("Free")',
        ]
        
        for selector in selectors:
            try:
                elem = self.page.locator(selector).first
                if await elem.count() > 0:
                    logger.info(f"✅ Found delivery option: {selector}")
                    await elem.click()
                    return True
            except:
                continue
        
        logger.warning("⚠️ Could not find specific delivery option, may auto-select")
        return True  # Soft fail - may not be required
    
    async def _execute_checkout(
        self,
        intent: NormalizedIntent,
        state: Any
    ) -> bool:
        """Execute checkout action."""
        button_texts = ["Checkout", "Proceed to Checkout", "Continue to Checkout"]
        
        for text in button_texts:
            try:
                button = self.page.locator(f'button:has-text("{text}"), a:has-text("{text}")').first
                if await button.count() > 0:
                    logger.info(f"✅ Found checkout button: {text}")
                    await button.click()
                    await self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                    return True
            except:
                continue
        
        return False
    
    async def _execute_guest_checkout(
        self,
        intent: NormalizedIntent,
        state: Any
    ) -> bool:
        """Execute guest checkout."""
        button_texts = ["Continue as Guest", "Guest Checkout", "Checkout as Guest"]
        
        for text in button_texts:
            try:
                button = self.page.locator(f'button:has-text("{text}"), a:has-text("{text}")').first
                if await button.count() > 0:
                    logger.info(f"✅ Found guest checkout: {text}")
                    await button.click()
                    await self.page.wait_for_load_state("domcontentloaded", timeout=10000)
                    return True
            except:
                continue
        
        return False
    
    async def _execute_click(
        self,
        intent: NormalizedIntent,
        state: Any
    ) -> bool:
        """Fallback click using smart_click."""
        try:
            result = await smart_click(self.page, intent.target)
            return result.get("success", False)
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return False
    
    async def _execute_type(
        self,
        intent: NormalizedIntent,
        state: Any
    ) -> bool:
        """Fallback type using smart_type."""
        try:
            result = await smart_type(self.page, intent.target, intent.value)
            return result.get("success", False)
        except Exception as e:
            logger.error(f"Type failed: {e}")
            return False
    
    async def _execute_wait(self, intent: NormalizedIntent) -> bool:
        """Execute wait."""
        wait_time = int(intent.value or "2") * 1000
        await self.page.wait_for_timeout(wait_time)
        return True
    
    async def _execute_fallback(
        self,
        intent: NormalizedIntent,
        state: Any
    ) -> bool:
        """Fallback execution."""
        logger.warning(f"⚠️ Using fallback for: {intent.action}")
        
        if intent.target:
            return await self._execute_click(intent, state)
        
        return False
