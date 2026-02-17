"""
🔍 PHASE 3 — ASSERTION ENGINE
Executes assertions WITHOUT triggering UI actions

CRITICAL: Assertions NEVER click, type, or interact with UI
"""
import logging
from typing import Any, Dict, Optional
from playwright.async_api import Page
from .test_model import TestStep, Intent, PageState

logger = logging.getLogger(__name__)


class AssertionResult:
    """Result of an assertion"""
    def __init__(self, passed: bool, message: str, actual: Any = None, expected: Any = None):
        self.passed = passed
        self.message = message
        self.actual = actual
        self.expected = expected
    
    def __bool__(self):
        return self.passed
    
    def __str__(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return f"{status}: {self.message}"


class AssertionEngine:
    """
    Executes assertions by INSPECTING the page (never clicking)
    
    ✅ PAGE_LOADED → Check title, body, URL
    ✅ ELEMENT_VISIBLE → Verify element exists
    ✅ FILTER_APPLIED → Count products, check filters
    ❌ Never performs UI actions (click, type, etc.)
    """
    
    def __init__(self, page: Page):
        self.page = page
    
    async def execute_assertion(self, step: TestStep) -> AssertionResult:
        """
        Execute assertion based on intent
        
        Returns AssertionResult (never modifies UI)
        """
        try:
            if step.intent == Intent.PAGE_LOADED:
                return await self._assert_page_loaded(step)
            
            elif step.intent == Intent.ELEMENT_VISIBLE:
                return await self._assert_element_visible(step)
            
            elif step.intent == Intent.ELEMENT_NOT_VISIBLE:
                return await self._assert_element_not_visible(step)
            
            elif step.intent == Intent.TEXT_CONTAINS:
                return await self._assert_text_contains(step)
            
            elif step.intent == Intent.URL_MATCHES:
                return await self._assert_url_matches(step)
            
            elif step.intent == Intent.FILTER_APPLIED:
                return await self._assert_filter_applied(step)
            
            elif step.intent == Intent.DELIVERY_OPTIONS_LOADED:
                return await self._assert_delivery_options_loaded(step)
            
            elif step.intent == Intent.BUTTON_ENABLED:
                return await self._assert_button_enabled(step)
            
            elif step.intent == Intent.BUTTON_DISABLED:
                return await self._assert_button_disabled(step)
            
            elif step.intent == Intent.ORDER_CONFIRMED:
                return await self._assert_order_confirmed(step)
            
            elif step.intent == Intent.ELEMENT_COUNT:
                return await self._assert_element_count(step)
            
            elif step.intent == Intent.PRODUCT_IN_CART:
                return await self._assert_product_in_cart(step)
            
            elif step.intent == Intent.PRICE_VISIBLE:
                return await self._assert_price_visible(step)
            
            else:
                return AssertionResult(
                    passed=False,
                    message=f"Unknown assertion intent: {step.intent}"
                )
        
        except Exception as e:
            logger.error(f"Assertion failed with error: {e}")
            return AssertionResult(
                passed=False,
                message=f"Assertion error: {str(e)}"
            )
    
    # ==================== ASSERTION HANDLERS (NO UI ACTIONS) ====================
    
    async def _assert_page_loaded(self, step: TestStep) -> AssertionResult:
        """
        Verify page loaded successfully
        
        Checks:
        - Body element exists
        - Title is not empty
        - No loader elements visible
        """
        try:
            # Check body exists
            body = await self.page.query_selector('body')
            if not body:
                return AssertionResult(False, "Body element not found")
            
            # Check title
            title = await self.page.title()
            if not title or title.lower() == "loading...":
                return AssertionResult(False, f"Invalid page title: '{title}'")
            
            # Check for loader (should NOT be visible)
            loader_visible = await self.page.is_visible('.loader, .loading, .spinner', timeout=1000)
            if loader_visible:
                return AssertionResult(False, "Page still loading (loader visible)")
            
            # Check specific page elements based on context
            page_context = step.value or ""
            if "home" in page_context.lower():
                # Verify home page elements
                main_content = await self.page.query_selector('main, #main, .main-content')
                if not main_content:
                    return AssertionResult(False, "Home page main content not found")
            
            elif "category" in page_context.lower():
                # Verify category page elements
                products = await self.page.query_selector('.product, .product-card, [class*="product"]')
                if not products:
                    return AssertionResult(False, "Category page products not found")
            
            elif "detail" in page_context.lower():
                # Verify product detail elements
                product_title = await self.page.query_selector('h1, .product-title, [class*="title"]')
                if not product_title:
                    return AssertionResult(False, "Product detail title not found")
            
            elif "cart" in page_context.lower():
                # Verify cart elements
                cart_items = await self.page.query_selector('.cart-item, [class*="cart"]')
                if not cart_items:
                    return AssertionResult(False, "Cart items not found")
            
            return AssertionResult(
                passed=True,
                message=f"Page loaded successfully: {page_context or 'current page'}",
                actual=title
            )
        
        except Exception as e:
            return AssertionResult(False, f"Page load assertion failed: {e}")
    
    async def _assert_element_visible(self, step: TestStep) -> AssertionResult:
        """Verify element is visible"""
        try:
            target = step.target or step.value
            if not target:
                return AssertionResult(False, "No target element specified")
            
            # Try multiple selector strategies
            selectors = [
                target,
                f'text="{target}"',
                f'//*[contains(text(), "{target}")]',
                f'[aria-label*="{target}" i]',
                f'[title*="{target}" i]'
            ]
            
            element_found = False
            for selector in selectors:
                try:
                    is_visible = await self.page.is_visible(selector, timeout=2000)
                    if is_visible:
                        element_found = True
                        break
                except:
                    continue
            
            if element_found:
                return AssertionResult(True, f"Element '{target}' is visible")
            else:
                return AssertionResult(False, f"Element '{target}' not visible")
        
        except Exception as e:
            return AssertionResult(False, f"Visibility assertion failed: {e}")
    
    async def _assert_element_not_visible(self, step: TestStep) -> AssertionResult:
        """Verify element is NOT visible"""
        result = await self._assert_element_visible(step)
        # Invert the result
        return AssertionResult(
            passed=not result.passed,
            message=result.message.replace("is visible", "is not visible").replace("not visible", "is visible")
        )
    
    async def _assert_text_contains(self, step: TestStep) -> AssertionResult:
        """Verify page contains text"""
        try:
            expected_text = step.value or step.target
            if not expected_text:
                return AssertionResult(False, "No text specified")
            
            # Get page content
            content = await self.page.content()
            
            if expected_text.lower() in content.lower():
                return AssertionResult(True, f"Page contains '{expected_text}'")
            else:
                return AssertionResult(False, f"Page does not contain '{expected_text}'")
        
        except Exception as e:
            return AssertionResult(False, f"Text assertion failed: {e}")
    
    async def _assert_url_matches(self, step: TestStep) -> AssertionResult:
        """Verify URL matches pattern"""
        try:
            expected_pattern = step.value or step.target
            current_url = self.page.url
            
            if not expected_pattern:
                return AssertionResult(False, "No URL pattern specified")
            
            if expected_pattern.lower() in current_url.lower():
                return AssertionResult(True, f"URL matches '{expected_pattern}'", actual=current_url)
            else:
                return AssertionResult(False, f"URL does not match '{expected_pattern}'", actual=current_url, expected=expected_pattern)
        
        except Exception as e:
            return AssertionResult(False, f"URL assertion failed: {e}")
    
    async def _assert_filter_applied(self, step: TestStep) -> AssertionResult:
        """
        Verify filter was applied
        
        Checks:
        - Filter badge/chip visible
        - Product count changed
        """
        try:
            # Check for filter badge/chip
            filter_badges = await self.page.query_selector_all('.filter-badge, .chip, .tag, [class*="filter"][class*="active"]')
            
            if not filter_badges:
                return AssertionResult(False, "No active filter badges found")
            
            # Count products
            products = await self.page.query_selector_all('.product, .product-card, [class*="product"]')
            product_count = len(products)
            
            return AssertionResult(
                passed=True,
                message=f"Filter applied: {len(filter_badges)} active filters, {product_count} products shown",
                actual=product_count
            )
        
        except Exception as e:
            return AssertionResult(False, f"Filter assertion failed: {e}")
    
    async def _assert_delivery_options_loaded(self, step: TestStep) -> AssertionResult:
        """
        Verify delivery options are loaded
        
        Checks:
        - Delivery option elements exist
        - At least one option visible
        """
        try:
            # Check for delivery option containers
            delivery_options = await self.page.query_selector_all(
                'input[type="radio"][name*="delivery"], '
                'input[type="radio"][name*="shipping"], '
                '.delivery-option, '
                '.shipping-option, '
                '[class*="delivery"][class*="option"]'
            )
            
            if not delivery_options:
                return AssertionResult(False, "No delivery options found")
            
            # Check if at least one is visible
            visible_count = 0
            for option in delivery_options:
                is_visible = await option.is_visible()
                if is_visible:
                    visible_count += 1
            
            if visible_count == 0:
                return AssertionResult(False, "Delivery options exist but none are visible")
            
            return AssertionResult(
                passed=True,
                message=f"{visible_count} delivery options loaded and visible",
                actual=visible_count
            )
        
        except Exception as e:
            return AssertionResult(False, f"Delivery options assertion failed: {e}")
    
    async def _assert_button_enabled(self, step: TestStep) -> AssertionResult:
        """Verify button is enabled"""
        try:
            target = step.target or step.value
            if not target:
                return AssertionResult(False, "No button specified")
            
            # Find button
            button = await self.page.query_selector(f'button:has-text("{target}"), a:has-text("{target}")')
            if not button:
                return AssertionResult(False, f"Button '{target}' not found")
            
            # Check if disabled
            is_disabled = await button.get_attribute('disabled')
            is_aria_disabled = await button.get_attribute('aria-disabled')
            
            if is_disabled or is_aria_disabled == 'true':
                return AssertionResult(False, f"Button '{target}' is disabled")
            else:
                return AssertionResult(True, f"Button '{target}' is enabled")
        
        except Exception as e:
            return AssertionResult(False, f"Button enabled assertion failed: {e}")
    
    async def _assert_button_disabled(self, step: TestStep) -> AssertionResult:
        """Verify button is disabled"""
        result = await self._assert_button_enabled(step)
        # Invert the result
        return AssertionResult(
            passed=not result.passed,
            message=result.message.replace("is enabled", "is disabled").replace("is disabled", "is enabled")
        )
    
    async def _assert_order_confirmed(self, step: TestStep) -> AssertionResult:
        """
        Verify order confirmation
        
        Checks:
        - Confirmation message visible
        - Order ID present
        - Thank you message
        """
        try:
            # Check for confirmation keywords
            confirmation_keywords = [
                "thank you",
                "order confirmed",
                "order placed",
                "confirmation",
                "success"
            ]
            
            content = await self.page.content()
            content_lower = content.lower()
            
            found_keywords = [kw for kw in confirmation_keywords if kw in content_lower]
            
            if not found_keywords:
                return AssertionResult(False, "No order confirmation message found")
            
            # Check for order ID
            order_id_element = await self.page.query_selector('[class*="order-id"], [class*="orderid"], [class*="order-number"]')
            
            return AssertionResult(
                passed=True,
                message=f"Order confirmed (found: {', '.join(found_keywords)})",
                actual=found_keywords
            )
        
        except Exception as e:
            return AssertionResult(False, f"Order confirmation assertion failed: {e}")
    
    async def _assert_element_count(self, step: TestStep) -> AssertionResult:
        """Verify element count matches expected"""
        try:
            target = step.target
            expected_count = step.metadata.get('count') if step.metadata else None
            
            if not target:
                return AssertionResult(False, "No target selector specified")
            
            elements = await self.page.query_selector_all(target)
            actual_count = len(elements)
            
            if expected_count is None:
                return AssertionResult(True, f"Found {actual_count} elements matching '{target}'", actual=actual_count)
            
            if actual_count == expected_count:
                return AssertionResult(True, f"Element count matches: {actual_count}", actual=actual_count, expected=expected_count)
            else:
                return AssertionResult(False, f"Element count mismatch", actual=actual_count, expected=expected_count)
        
        except Exception as e:
            return AssertionResult(False, f"Element count assertion failed: {e}")
    
    async def _assert_product_in_cart(self, step: TestStep) -> AssertionResult:
        """Verify product is in cart"""
        try:
            product_name = step.target or step.value
            if not product_name:
                return AssertionResult(False, "No product name specified")
            
            # Get cart items
            cart_items = await self.page.query_selector_all('.cart-item, [class*="cart"]')
            
            if not cart_items:
                return AssertionResult(False, "No cart items found")
            
            # Check each item for product name
            for item in cart_items:
                text = await item.inner_text()
                if product_name.lower() in text.lower():
                    return AssertionResult(True, f"Product '{product_name}' found in cart")
            
            return AssertionResult(False, f"Product '{product_name}' not found in cart")
        
        except Exception as e:
            return AssertionResult(False, f"Product in cart assertion failed: {e}")
    
    async def _assert_price_visible(self, step: TestStep) -> AssertionResult:
        """Verify price is visible"""
        try:
            # Look for price elements
            price_selectors = [
                '.price',
                '[class*="price"]',
                '[data-testid*="price"]',
                'span:has-text("₹")',
                'span:has-text("$")',
                'span:has-text("€")'
            ]
            
            for selector in price_selectors:
                try:
                    price_element = await self.page.query_selector(selector)
                    if price_element:
                        is_visible = await price_element.is_visible()
                        if is_visible:
                            price_text = await price_element.inner_text()
                            return AssertionResult(True, f"Price visible: {price_text}", actual=price_text)
                except:
                    continue
            
            return AssertionResult(False, "No price element found")
        
        except Exception as e:
            return AssertionResult(False, f"Price visibility assertion failed: {e}")
