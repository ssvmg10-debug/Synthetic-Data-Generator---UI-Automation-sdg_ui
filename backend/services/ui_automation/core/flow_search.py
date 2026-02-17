"""
SearchFlow Executor
Handles all search-related intents with proper modal and scope handling
"""
import logging
from playwright.async_api import Page, Locator, TimeoutError as PlaywrightTimeout
from typing import Optional
from services.ui_automation.core.intent_models import Intent, IntentType
from services.ui_automation.core.state_validation import StateValidator

logger = logging.getLogger(__name__)


class SearchFlowExecutor:
    """
    Specialized executor for search flows.
    
    Fixes common issues:
    - Modal scope handling
    - Search button disambiguation
    - Result loading validation
    """
    
    def __init__(self):
        self.state_validator = StateValidator()
    
    async def execute_search(self, page: Page, intent: Intent) -> bool:
        """
        Execute SEARCH_PRODUCT intent.
        
        Steps:
        1. Detect if search is in modal or main page
        2. Click appropriate search trigger
        3. Wait for search input
        4. Enter query
        5. Submit search
        6. Validate results loaded
        
        Args:
            page: Playwright page
            intent: Search intent with query
        
        Returns:
            True if search succeeded
        """
        query = intent.query
        if not query:
            logger.error("Search intent missing query")
            return False
        
        logger.info(f"🔍 Executing search flow: '{query}'")
        
        try:
            # Step 1: Check for modal-based search
            modal_opened = await self._open_search_modal(page)
            
            # Step 2: Get search container (modal or page)
            container = await self._get_search_container(page)
            
            # Step 3: Find and fill search input
            search_input = await self._find_search_input(container)
            if not search_input:
                logger.error("Could not find search input")
                return False
            
            await search_input.fill(query)
            logger.info(f"  ✅ Entered query: '{query}'")
            
            # Step 4: Submit search
            await page.keyboard.press("Enter")
            logger.info("  ✅ Submitted search")
            
            # Step 5: Validate results loaded
            results_loaded = await self.state_validator.wait_for_search_results(page)
            if not results_loaded:
                logger.error("Search results did not load")
                return False
            
            logger.info(f"✅ Search flow complete for: '{query}'")
            return True
            
        except Exception as e:
            logger.error(f"Search flow failed: {e}")
            return False
    
    async def _open_search_modal(self, page: Page) -> bool:
        """
        Attempt to open search modal if it exists.
        
        Returns:
            True if modal was opened, False if no modal needed
        """
        try:
            # Look for search icon/button that opens modal
            search_triggers = [
                "button[aria-label*='Search']",
                "button[aria-label*='search']",
                "[data-testid='search-button']",
                ".search-icon",
                "button:has-text('🔍')",
            ]
            
            for selector in search_triggers:
                trigger = await page.query_selector(selector)
                if trigger:
                    # Check if it opens a modal
                    await trigger.click()
                    logger.info("  ✅ Clicked search trigger")
                    
                    # Wait for modal to appear
                    try:
                        await page.wait_for_selector(
                            "[role='dialog'], .modal, .search-modal",
                            timeout=2000,
                            state="visible"
                        )
                        logger.info("  ✅ Search modal opened")
                        return True
                    except PlaywrightTimeout:
                        # Not a modal - search input might already be visible
                        pass
                    
                    break
            
            return False
            
        except Exception as e:
            logger.debug(f"No search modal found: {e}")
            return False
    
    async def _get_search_container(self, page: Page) -> Locator:
        """
        Get the container to search within (modal or page).
        
        Returns:
            Modal locator if open, otherwise page locator
        """
        # Check if modal is open
        modal = await page.query_selector("[role='dialog']:visible, .modal:visible")
        if modal:
            logger.info("  ℹ️  Searching within modal")
            return page.locator("[role='dialog']:visible, .modal:visible").first
        
        logger.info("  ℹ️  Searching within page")
        return page.locator("body")
    
    async def _find_search_input(self, container: Locator) -> Optional[Locator]:
        """
        Find search input within container.
        
        Args:
            container: Locator to search within
        
        Returns:
            Search input locator or None
        """
        # Try multiple selectors
        selectors = [
            "input[type='search']",
            "input[placeholder*='Search']",
            "input[placeholder*='search']",
            "input[name='search']",
            "input[name='q']",
            "input[aria-label*='Search']",
            "input[aria-label*='search']",
            "[data-testid='search-input']",
            ".search-input",
        ]
        
        for selector in selectors:
            try:
                input_elem = container.locator(selector).first
                if await input_elem.count() > 0:
                    # Verify it's visible and enabled
                    if await input_elem.is_visible() and await input_elem.is_enabled():
                        logger.info(f"  ✅ Found search input: {selector}")
                        return input_elem
            except:
                continue
        
        # Fallback: Any visible text input
        try:
            inputs = container.locator("input[type='text']:visible, input:not([type]):visible")
            count = await inputs.count()
            if count > 0:
                logger.info(f"  ⚠️  Using fallback text input")
                return inputs.first
        except:
            pass
        
        return None
    
    async def execute_filter(self, page: Page, intent: Intent) -> bool:
        """
        Execute FILTER_RESULTS intent.
        
        Args:
            page: Playwright page
            intent: Filter intent
        
        Returns:
            True if filter applied
        """
        logger.info(f"🔍 Executing filter: {intent.option}")
        
        try:
            # Look for filter checkboxes or dropdowns
            filter_text = intent.option or intent.value
            if not filter_text:
                logger.error("Filter intent missing option/value")
                return False
            
            # Try checkbox
            checkbox = await page.query_selector(f"input[type='checkbox'] + label:has-text('{filter_text}')")
            if checkbox:
                await checkbox.click()
                logger.info(f"  ✅ Applied filter: {filter_text}")
                return True
            
            # Try dropdown
            select = await page.query_selector("select.filter, select[name*='filter']")
            if select:
                await page.select_option(select, label=filter_text)
                logger.info(f"  ✅ Selected filter: {filter_text}")
                return True
            
            logger.warning(f"Could not find filter: {filter_text}")
            return False
            
        except Exception as e:
            logger.error(f"Filter execution failed: {e}")
            return False
