"""
CheckoutFlow Executor
Handles checkout process with intelligent form field detection and delivery option selection
"""
import logging
from playwright.async_api import Page, Locator, TimeoutError as PlaywrightTimeout
from typing import Optional, List
from services.ui_automation.core.intent_models import Intent, IntentType
from services.ui_automation.core.state_validation import StateValidator

logger = logging.getLogger(__name__)


class CheckoutFlowExecutor:
    """
    Specialized executor for checkout flows.
    
    Features:
    - Label proximity detection for form fields
    - Pincode field identification
    - Delivery option selection
    - Payment method selection
    """
    
    def __init__(self):
        self.state_validator = StateValidator()
    
    async def execute_proceed_to_checkout(self, page: Page, intent: Intent) -> bool:
        """
        Execute PROCEED_TO_CHECKOUT intent.
        
        Args:
            page: Playwright page
            intent: Checkout intent
        
        Returns:
            True if checkout page reached
        """
        logger.info("🛒 Proceeding to checkout")
        
        try:
            # Look for checkout button
            checkout_selectors = [
                "button:has-text('Checkout')",
                "button:has-text('Proceed')",
                "a:has-text('Checkout')",
                "[data-testid='checkout-button']",
                ".checkout-btn",
            ]
            
            for selector in checkout_selectors:
                button = await page.query_selector(selector)
                if button:
                    await button.click()
                    logger.info("  ✅ Clicked checkout button")
                    
                    # Wait for checkout page
                    await page.wait_for_load_state("domcontentloaded")
                    
                    # Validate checkout page loaded
                    loaded = await self.state_validator.wait_for_checkout_page(page)
                    if loaded:
                        logger.info("✅ Checkout page loaded")
                        return True
                    else:
                        logger.warning("Checkout page validation failed")
                        return False
            
            logger.error("Could not find checkout button")
            return False
            
        except Exception as e:
            logger.error(f"Proceed to checkout failed: {e}")
            return False
    
    async def execute_set_pincode(self, page: Page, intent: Intent) -> bool:
        """
        Execute SET_PINCODE intent.
        
        Uses label proximity and keyword matching to find pincode field.
        
        Args:
            page: Playwright page
            intent: Pincode intent with value
        
        Returns:
            True if pincode entered
        """
        pincode = intent.value
        if not pincode:
            logger.error("Pincode intent missing value")
            return False
        
        logger.info(f"📮 Setting pincode: {pincode}")
        
        try:
            # Step 1: Find pincode input
            pincode_input = await self._find_pincode_input(page)
            if not pincode_input:
                logger.error("Could not find pincode input")
                return False
            
            # Step 2: Clear and fill
            await pincode_input.clear()
            await pincode_input.fill(pincode)
            logger.info(f"  ✅ Entered pincode: {pincode}")
            
            # Step 3: Submit/check pincode (optional)
            check_button = await self._find_check_button(page)
            if check_button:
                await check_button.click()
                logger.info("  ✅ Clicked check button")
                
                # Wait for delivery options
                await page.wait_for_timeout(1000)
            
            logger.info(f"✅ Pincode set: {pincode}")
            return True
            
        except Exception as e:
            logger.error(f"Set pincode failed: {e}")
            return False
    
    async def execute_select_delivery_option(self, page: Page, intent: Intent) -> bool:
        """
        Execute SELECT_DELIVERY_OPTION intent.
        
        Args:
            page: Playwright page
            intent: Delivery option intent
        
        Returns:
            True if delivery option selected
        """
        option_text = intent.option or intent.value
        if not option_text:
            logger.error("Delivery option intent missing option/value")
            return False
        
        logger.info(f"📦 Selecting delivery option: '{option_text}'")
        
        try:
            # Wait for delivery options to be available
            await self.state_validator.wait_for_delivery_options(page)
            
            # Step 1: Find matching radio button
            radio_button = await self._find_delivery_option(page, option_text)
            if not radio_button:
                logger.error(f"Could not find delivery option: {option_text}")
                return False
            
            # Step 2: Select option
            await radio_button.check()
            logger.info(f"  ✅ Selected: {option_text}")
            
            logger.info(f"✅ Delivery option selected: {option_text}")
            return True
            
        except Exception as e:
            logger.error(f"Select delivery option failed: {e}")
            return False
    
    async def execute_select_payment_method(self, page: Page, intent: Intent) -> bool:
        """
        Execute SELECT_PAYMENT_METHOD intent.
        
        Args:
            page: Playwright page
            intent: Payment method intent
        
        Returns:
            True if payment method selected
        """
        payment_method = intent.option or intent.value
        if not payment_method:
            logger.error("Payment method intent missing option/value")
            return False
        
        logger.info(f"💳 Selecting payment method: '{payment_method}'")
        
        try:
            # Find payment option radio button
            radio = await page.query_selector(
                f"input[type='radio'][value*='{payment_method}'], "
                f"input[type='radio'] + label:has-text('{payment_method}')"
            )
            
            if radio:
                await radio.check()
                logger.info(f"  ✅ Selected: {payment_method}")
                return True
            
            # Fallback: Click on label
            label = await page.query_selector(f"label:has-text('{payment_method}')")
            if label:
                await label.click()
                logger.info(f"  ✅ Clicked: {payment_method}")
                return True
            
            logger.error(f"Could not find payment method: {payment_method}")
            return False
            
        except Exception as e:
            logger.error(f"Select payment method failed: {e}")
            return False
    
    async def _find_pincode_input(self, page: Page) -> Optional[Locator]:
        """
        Find pincode input using multiple strategies.
        
        Strategies:
        1. Direct attribute matching
        2. Placeholder matching
        3. Label proximity
        4. ARIA label
        
        Returns:
            Pincode input locator or None
        """
        # Strategy 1: Direct attributes
        direct_selectors = [
            "input[name*='pincode']",
            "input[name*='pin']",
            "input[name*='zip']",
            "input[name*='postal']",
            "input[id*='pincode']",
            "input[id*='pin']",
            "input[id*='zip']",
            "[data-testid*='pincode']",
            "[data-testid*='pin']",
        ]
        
        for selector in direct_selectors:
            input_elem = await page.query_selector(selector)
            if input_elem:
                logger.info(f"  ✅ Found pincode input: {selector}")
                return input_elem
        
        # Strategy 2: Placeholder matching
        placeholders = ["pincode", "pin", "zip", "postal"]
        for placeholder in placeholders:
            input_elem = await page.query_selector(f"input[placeholder*='{placeholder}' i]")
            if input_elem:
                logger.info(f"  ✅ Found pincode input by placeholder: {placeholder}")
                return input_elem
        
        # Strategy 3: ARIA label
        aria_labels = ["pincode", "pin code", "zip", "postal code"]
        for label in aria_labels:
            input_elem = await page.query_selector(f"input[aria-label*='{label}' i]")
            if input_elem:
                logger.info(f"  ✅ Found pincode input by ARIA label: {label}")
                return input_elem
        
        # Strategy 4: Label proximity (find label, then input)
        label_keywords = ["pincode", "pin code", "pin", "zip", "postal"]
        for keyword in label_keywords:
            # Try case-insensitive text matching
            try:
                label_elem = await page.query_selector(f"label:text-matches('{keyword}', 'i')")
                if not label_elem:
                    # Fallback to has-text
                    label_elem = await page.query_selector(f"label:has-text('{keyword}')")
                
                if label_elem:
                    # Get associated input
                    for_attr = await label_elem.get_attribute("for")
                    if for_attr:
                        input_elem = await page.query_selector(f"input[id='{for_attr}']")
                        if input_elem:
                            logger.info(f"  ✅ Found pincode input by label proximity: {keyword}")
                            return input_elem
                    
                    # Try finding input in parent container
                    try:
                        # Get parent and search for input
                        parent_js = await label_elem.evaluate_handle("el => el.parentElement")
                        if parent_js:
                            parent_elem = parent_js.as_element()
                            if parent_elem:
                                input_elem = await parent_elem.query_selector("input")
                                if input_elem:
                                    logger.info(f"  ✅ Found pincode input near label: {keyword}")
                                    return input_elem
                    except:
                        pass
            except:
                continue
        
        logger.warning("Could not find pincode input")
        return None
    
    async def _find_check_button(self, page: Page) -> Optional[Locator]:
        """Find 'Check' or 'Apply' button near pincode field"""
        selectors = [
            "button:has-text('Check')",
            "button:has-text('Apply')",
            "button:has-text('Verify')",
            "[data-testid*='check']",
        ]
        
        for selector in selectors:
            button = await page.query_selector(selector)
            if button:
                return button
        
        return None
    
    async def _find_delivery_option(self, page: Page, option_text: str) -> Optional[Locator]:
        """
        Find delivery option radio button by text matching.
        
        Args:
            page: Playwright page
            option_text: Delivery option text (e.g., "free delivery")
        
        Returns:
            Radio button locator or None
        """
        # Get all radio buttons
        radios = await page.query_selector_all("input[type='radio']")
        
        option_lower = option_text.lower()
        
        for radio in radios:
            try:
                # Get associated label or nearby text
                radio_id = await radio.get_attribute("id")
                
                # Check label
                if radio_id:
                    label = await page.query_selector(f"label[for='{radio_id}']")
                    if label:
                        label_text = await label.inner_text()
                        if any(word in label_text.lower() for word in option_lower.split()):
                            logger.info(f"  ✅ Found radio by label: {label_text}")
                            return radio
                
                # Check parent text
                parent = await radio.evaluate_handle("el => el.parentElement")
                if parent:
                    parent_text = await parent.as_element().inner_text()
                    if any(word in parent_text.lower() for word in option_lower.split()):
                        logger.info(f"  ✅ Found radio by parent text: {parent_text}")
                        return radio
                
            except:
                continue
        
        logger.warning(f"Could not find delivery option: {option_text}")
        return None
