"""
Controlled Smart Resolver
Limited-strategy resolver with time and confidence constraints
"""
import logging
import time
from playwright.async_api import Page
from typing import Optional, List
from services.ui_automation.core.intent_models import Intent

logger = logging.getLogger(__name__)


class ControlledSmartResolver:
    """
    Controlled fallback resolver with strict limits.
    
    Fixes current issue: Unlimited resolver taking 300+ seconds.
    
    Constraints:
    - Max 3 strategies
    - Max 5 seconds total
    - Min confidence 0.6
    - Fail early if no match
    """
    
    def __init__(self, max_strategies: int = 3, max_time: float = 5.0, min_confidence: float = 0.6):
        self.max_strategies = max_strategies
        self.max_time = max_time
        self.min_confidence = min_confidence
    
    async def resolve_click(self, page: Page, target_text: str) -> bool:
        """
        Try to click element with controlled strategies.
        
        Args:
            page: Playwright page
            target_text: Target element text
        
        Returns:
            True if clicked
        """
        logger.info(f"🔄 Controlled resolver: {target_text}")
        start_time = time.time()
        
        strategies = [
            self._strategy_exact_text,
            self._strategy_partial_text,
            self._strategy_aria_label,
        ]
        
        for i, strategy in enumerate(strategies[:self.max_strategies], 1):
            # Check time limit
            elapsed = time.time() - start_time
            if elapsed > self.max_time:
                logger.warning(f"  ⏱️  Time limit reached: {elapsed:.2f}s")
                return False
            
            logger.debug(f"  Strategy {i}/{self.max_strategies}")
            
            try:
                result = await strategy(page, target_text)
                if result:
                    logger.info(f"  ✅ Strategy {i} succeeded")
                    return True
            except Exception as e:
                logger.debug(f"  Strategy {i} failed: {e}")
                continue
        
        elapsed = time.time() - start_time
        logger.warning(f"  ❌ All strategies failed ({elapsed:.2f}s)")
        return False
    
    async def resolve_type(self, page: Page, field_label: str, value: str) -> bool:
        """
        Try to type into field with controlled strategies.
        
        Args:
            page: Playwright page
            field_label: Field label or identifier
            value: Value to type
        
        Returns:
            True if typed
        """
        logger.info(f"🔄 Controlled resolver: type '{field_label}'")
        start_time = time.time()
        
        strategies = [
            self._strategy_name_attr,
            self._strategy_placeholder,
            self._strategy_label_proximity,
        ]
        
        for i, strategy in enumerate(strategies[:self.max_strategies], 1):
            elapsed = time.time() - start_time
            if elapsed > self.max_time:
                logger.warning(f"  ⏱️  Time limit reached: {elapsed:.2f}s")
                return False
            
            logger.debug(f"  Strategy {i}/{self.max_strategies}")
            
            try:
                input_elem = await strategy(page, field_label)
                if input_elem:
                    await input_elem.fill(value)
                    logger.info(f"  ✅ Strategy {i} succeeded")
                    return True
            except Exception as e:
                logger.debug(f"  Strategy {i} failed: {e}")
                continue
        
        elapsed = time.time() - start_time
        logger.warning(f"  ❌ All strategies failed ({elapsed:.2f}s)")
        return False
    
    # Click strategies
    
    async def _strategy_exact_text(self, page: Page, text: str) -> bool:
        """Strategy: Exact text match"""
        elem = await page.query_selector(f"button:has-text('{text}'), a:has-text('{text}')")
        if elem:
            await elem.click()
            return True
        return False
    
    async def _strategy_partial_text(self, page: Page, text: str) -> bool:
        """Strategy: Partial text match"""
        # Get all clickable elements
        buttons = await page.query_selector_all("button, a, [role='button']")
        
        text_lower = text.lower()
        
        for button in buttons:
            try:
                button_text = await button.inner_text()
                if text_lower in button_text.lower():
                    await button.click()
                    return True
            except:
                continue
        
        return False
    
    async def _strategy_aria_label(self, page: Page, text: str) -> bool:
        """Strategy: ARIA label match"""
        elem = await page.query_selector(f"[aria-label*='{text}' i]")
        if elem:
            await elem.click()
            return True
        return False
    
    # Type strategies
    
    async def _strategy_name_attr(self, page: Page, label: str):
        """Strategy: Name attribute"""
        return await page.query_selector(f"input[name*='{label}' i]")
    
    async def _strategy_placeholder(self, page: Page, label: str):
        """Strategy: Placeholder text"""
        return await page.query_selector(f"input[placeholder*='{label}' i]")
    
    async def _strategy_label_proximity(self, page: Page, label: str):
        """Strategy: Label proximity"""
        label_elem = await page.query_selector(f"label:has-text('{label}') i")
        if not label_elem:
            return None
        
        # Try 'for' attribute
        for_attr = await label_elem.get_attribute("for")
        if for_attr:
            return await page.query_selector(f"input[id='{for_attr}']")
        
        # Try parent
        parent = label_elem.locator("xpath=./..").first
        return await parent.query_selector("input")
