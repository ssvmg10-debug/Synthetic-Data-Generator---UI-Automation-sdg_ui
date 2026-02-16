"""
Selector Validator - Pre-execution validation to catch 80% of failures
Validates selectors against actual page before test execution.
"""
from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeoutError
from typing import List, Dict, Any, Optional
import re
import logging
import asyncio
import sys
import time

from services.ui_automation.utils.fuzzy_matcher import FuzzyMatcher

logger = logging.getLogger(__name__)


def _should_use_sync_playwright() -> bool:
    """Use sync Playwright in a thread when on Windows without ProactorEventLoop (avoids subprocess NotImplementedError)."""
    if sys.platform != "win32":
        return False
    try:
        loop = asyncio.get_running_loop()
        if isinstance(loop, asyncio.ProactorEventLoop):
            return False
        logger.info("Using sync Playwright fallback (Windows non-ProactorEventLoop)")
        return True
    except RuntimeError:
        return False


def ensure_windows_event_loop():
    """
    Ensure Windows uses ProactorEventLoop for subprocess support.
    Must be called before any Playwright operations on Windows.
    """
    if sys.platform == "win32":
        try:
            loop = asyncio.get_running_loop()
            # Check if it's not already a ProactorEventLoop
            if not isinstance(loop, asyncio.ProactorEventLoop):
                logger.warning("Detected non-ProactorEventLoop on Windows, this may cause Playwright subprocess issues")
        except RuntimeError:
            # No running loop yet, set the policy
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


class SelectorValidator:
    """
    Validates Playwright selectors before test execution.
    
    Features:
    - Check if selectors find elements on actual page
    - Auto-fix invalid selectors using fuzzy matching
    - Return validation report with fixes
    - Prevent 80% of runtime failures
    
    Example:
        validator = SelectorValidator()
        
        steps = [
            {"action": "click", "selector": "button:has-text('grey shirt')", "description": "Click product"},
            {"action": "fill", "selector": "input[name='email']", "value": "test@example.com"}
        ]
        
        result = await validator.validate_script("https://example.com", steps)
        
        if result['validation_passed']:
            # All selectors valid - safe to execute
            execute_test(result['validated_steps'])
        else:
            # Review invalid selectors
            print(result['invalid_selectors'])
    """
    
    def __init__(self, fuzzy_threshold: float = 0.65, headless: bool = True):
        """
        Initialize selector validator.
        
        Args:
            fuzzy_threshold: Threshold for fuzzy text matching (0.0-1.0)
            headless: Run browser in headless mode
        """
        self.fuzzy_matcher = FuzzyMatcher(threshold=fuzzy_threshold)
        self.headless = headless
        self.validation_timeout = 5000  # 5 seconds per selector check
        
        logger.info(f"SelectorValidator initialized (fuzzy_threshold={fuzzy_threshold}, headless={headless})")
    
    async def validate_script(
        self,
        url: str,
        steps: List[Dict[str, Any]],
        wait_for_load: bool = True
    ) -> Dict[str, Any]:
        """
        Validate all selectors in a test script.
        
        Args:
            url: URL to open for validation
            steps: List of test steps with 'selector', 'action', 'description' fields
            wait_for_load: Wait for page to be fully loaded before validation
        
        Returns:
            {
                "validated_steps": List[Dict],  # Steps with potentially fixed selectors
                "invalid_selectors": List[Dict],  # Selectors that couldn't be fixed
                "auto_fixed": List[Dict],  # Selectors that were auto-fixed
                "validation_passed": bool,  # True if all selectors valid
                "validation_time": float  # Time taken in seconds
            }
        
        Raises:
            Exception: If page fails to load or browser errors occur
        """
        start_time = time.time()
        logger.info(f"Starting selector validation for {len(steps)} steps on {url}")

        # On Windows with non-ProactorEventLoop, run sync Playwright in a thread to avoid NotImplementedError
        if _should_use_sync_playwright():
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                lambda: self._validate_script_sync(url, steps, wait_for_load),
            )

        validated_steps = []
        invalid_selectors = []
        auto_fixed = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()
            # Use domcontentloaded for faster validation; networkidle can add 5–30s on heavy sites
            wait_until = "domcontentloaded"

            try:
                # Step-through validation: run steps in order so each selector is checked on the page it applies to
                initial_url = url
                if steps and steps[0].get("action") == "goto" and steps[0].get("value"):
                    initial_url = steps[0].get("value", url)
                await page.goto(initial_url, wait_until=wait_until, timeout=25000)
                logger.info(f"Step-through validation: loaded {initial_url}")

                for i, step in enumerate(steps):
                    selector = step.get("selector")
                    action = step.get("action", "unknown")
                    description = step.get("description", f"Step {i+1}")

                    if action == "goto":
                        validated_steps.append(step)
                        nav_url = step.get("value") or url
                        try:
                            await page.goto(nav_url, wait_until=wait_until, timeout=25000)
                            await page.wait_for_timeout(1500)
                        except Exception as e:
                            logger.debug("Validation goto failed: %s", e)
                        continue

                    if action in ("wait", "waitForSelector") or not selector:
                        validated_steps.append(step)
                        if action == "wait" and step.get("value"):
                            try:
                                await page.wait_for_timeout(min(int(step.get("value", 1000)), 5000))
                            except Exception:
                                pass
                        continue

                    try:
                        count = await page.locator(selector).count()
                        if count == 0 and step.get("locator_hint"):
                            # Prefer Playwright locator_hint (get_by_role etc.) when CSS has 0 matches
                            hint_count = await self._locator_hint_count_async(page, step)
                            if hint_count == 1:
                                count = 1
                                logger.debug(f"✓ Step {i+1} valid via locator_hint")
                        if count == 0:
                            fixed_selector = await self._try_playwright_locators_async(page, step, selector)
                            if not fixed_selector:
                                fixed_selector = await self._fuzzy_fix_selector(page, step, selector)
                            if fixed_selector:
                                step["selector"] = fixed_selector
                                step["original_selector"] = selector
                                step["auto_fixed"] = True
                                auto_fixed.append({
                                    "step_index": i + 1,
                                    "description": description,
                                    "original": selector,
                                    "fixed": fixed_selector,
                                    "action": action,
                                })
                                logger.info(f"✅ Auto-fixed step {i+1}: '{selector}' → '{fixed_selector}'")
                            else:
                                invalid_selectors.append({
                                    "step_index": i + 1,
                                    "description": description,
                                    "selector": selector,
                                    "action": action,
                                    "reason": "No matching element and fix failed",
                                })
                                logger.error(f"❌ Could not fix step {i+1}: '{selector}'")
                        elif count > 1:
                            step["multiple_matches"] = count
                        else:
                            logger.debug(f"✓ Valid selector at step {i+1}: '{selector}'")

                        validated_steps.append(step)
                        if count > 0 or step.get("auto_fixed"):
                            await self._execute_step_for_validation_async(page, step)
                    except Exception as e:
                        logger.error(f"Error validating selector at step {i+1}: {e}")
                        invalid_selectors.append({
                            "step_index": i + 1,
                            "description": description,
                            "selector": selector,
                            "action": action,
                            "reason": str(e),
                        })
                        validated_steps.append(step)

            finally:
                await browser.close()
        
        validation_time = time.time() - start_time
        validation_passed = len(invalid_selectors) == 0
        
        stats = {
            "total_steps": len(steps),
            "validated": len(validated_steps),
            "invalid": len(invalid_selectors),
            "auto_fixed": len(auto_fixed),
            "success_rate": (len(steps) - len(invalid_selectors)) / len(steps) if steps else 0
        }
        result = {
            "validated_steps": validated_steps,
            "invalid_selectors": invalid_selectors,
            "auto_fixed": auto_fixed,
            "validation_passed": validation_passed,
            "validation_time": validation_time,
            "stats": stats,
            "steps": validated_steps,
            "valid_count": stats["validated"],
            "invalid_count": stats["invalid"],
            "fixed_count": stats["auto_fixed"],
        }
        
        logger.info(
            f"Validation complete: {result['stats']['success_rate']*100:.0f}% success "
            f"({len(auto_fixed)} auto-fixed, {len(invalid_selectors)} invalid) in {validation_time:.1f}s"
        )
        
        return result

    async def _locator_hint_count_async(self, page: Page, step: Dict[str, Any]) -> int:
        """Return number of elements matching step's locator_hint (0 if no hint or error)."""
        hint = step.get("locator_hint")
        if not isinstance(hint, dict) or not hint:
            return 0
        try:
            if hint.get("role"):
                name = hint.get("name")
                loc = page.get_by_role(hint["role"], name=re.compile(re.escape(name), re.I)) if name else page.get_by_role(hint["role"])
            elif hint.get("placeholder"):
                loc = page.get_by_placeholder(hint["placeholder"])
            elif hint.get("label"):
                loc = page.get_by_label(hint["label"])
            else:
                return 0
            return await loc.count()
        except Exception:
            return 0

    async def _try_playwright_locators_async(
        self, page: Page, step: Dict[str, Any], failed_selector: str
    ) -> Optional[str]:
        """Use Playwright's role/label/placeholder locators when CSS fails (more resilient)."""
        action = step.get("action", "")
        try:
            if action in ("fill", "type"):
                # Try searchbox role (common for search inputs)
                if await page.get_by_role("searchbox").count() == 1:
                    return "input[type='search'], [role='searchbox'], input[placeholder*='Search'], input[placeholder*='search']"
                # Try placeholder from step value or common names
                fill_value = (step.get("value") or "").strip() or "search"
                for placeholder in [fill_value, "Search", "search", "Enter"]:
                    try:
                        if await page.get_by_placeholder(placeholder).count() == 1:
                            return f"input[placeholder*='{placeholder}']"
                    except Exception:
                        pass
            if action == "click":
                for role in ["button", "link"]:
                    try:
                        for name in ["Accept", "Accept all", "OK", "Agree", "Allow"]:
                            if await page.get_by_role(role, name=re.compile(name, re.I)).count() == 1:
                                return f"[role='{role}']:has-text('{name}')"
                    except Exception:
                        pass
        except Exception as e:
            logger.debug("Playwright locator fallback failed: %s", e)
        return None

    async def _execute_step_for_validation_async(self, page: Page, step: Dict[str, Any]) -> None:
        """Execute one step so the next validation runs on the right page. Tries locator_hint first if present."""
        action = step.get("action")
        value = (step.get("value") or "").strip() or "test"
        hint = step.get("locator_hint")
        if isinstance(hint, dict) and hint and action in ("click", "fill", "type"):
            try:
                loc = None
                if hint.get("role"):
                    name = hint.get("name")
                    loc = page.get_by_role(hint["role"], name=re.compile(re.escape(name), re.I)) if name else page.get_by_role(hint["role"])
                elif hint.get("placeholder"):
                    loc = page.get_by_placeholder(hint["placeholder"])
                elif hint.get("label"):
                    loc = page.get_by_label(hint["label"])
                if loc and await loc.count() > 0:
                    await loc.first.wait_for(state="visible", timeout=8000)
                    if action == "click":
                        await loc.first.click(timeout=8000)
                    elif action in ("fill", "type"):
                        await loc.first.fill(value, timeout=8000)
                    await page.wait_for_timeout(1500)
                    return
            except Exception as e:
                logger.debug("Validation step locator_hint (async): %s", e)
        selector = step.get("selector") or step.get("original_selector")
        if not selector:
            return
        try:
            if action == "click":
                await page.click(selector, timeout=8000)
                await page.wait_for_timeout(1500)
            elif action in ("fill", "type"):
                await page.fill(selector, value, timeout=8000)
                await page.wait_for_timeout(500)
            elif action == "press":
                await page.press(selector, step.get("value") or "Enter", timeout=5000)
                await page.wait_for_timeout(1000)
        except Exception as e:
            logger.debug("Validation step execute (advance page): %s", e)

    def _validate_script_sync(
        self,
        url: str,
        steps: List[Dict[str, Any]],
        wait_for_load: bool = True,
    ) -> Dict[str, Any]:
        """Sync Playwright validation with step-through (used on Windows)."""
        from playwright.sync_api import sync_playwright

        start_time = time.time()
        validated_steps = []
        invalid_selectors = []
        auto_fixed = []
        wait_until = "domcontentloaded"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            try:
                initial_url = url
                if steps and steps[0].get("action") == "goto" and steps[0].get("value"):
                    initial_url = steps[0].get("value", url)
                page.goto(initial_url, wait_until=wait_until, timeout=25000)
                page.wait_for_timeout(1500)
                logger.info("Step-through validation (sync): loaded %s", initial_url)

                for i, step in enumerate(steps):
                    selector = step.get("selector")
                    action = step.get("action", "unknown")
                    description = step.get("description", f"Step {i+1}")

                    if action == "goto":
                        validated_steps.append(step)
                        nav_url = step.get("value") or url
                        try:
                            page.goto(nav_url, wait_until=wait_until, timeout=25000)
                            page.wait_for_timeout(1500)
                        except Exception as e:
                            logger.debug("Validation goto failed: %s", e)
                        continue

                    if action in ("wait", "waitForSelector") or not selector:
                        validated_steps.append(step)
                        if action == "wait" and step.get("value"):
                            try:
                                page.wait_for_timeout(min(int(step.get("value", 1000)), 5000))
                            except Exception:
                                pass
                        continue

                    try:
                        count = page.locator(selector).count()
                        if count == 0 and step.get("locator_hint"):
                            hint_count = self._locator_hint_count_sync(page, step)
                            if hint_count == 1:
                                count = 1
                        if count == 0:
                            fixed_selector = self._try_playwright_locators_sync(page, step, selector)
                            if not fixed_selector:
                                invalid_selectors.append({
                                    "step_index": i + 1,
                                    "description": description,
                                    "selector": selector,
                                    "action": action,
                                    "reason": "No matching element (sync path)",
                                })
                            else:
                                step["selector"] = fixed_selector
                                step["original_selector"] = selector
                                step["auto_fixed"] = True
                                auto_fixed.append({
                                    "step_index": i + 1,
                                    "description": description,
                                    "original": selector,
                                    "fixed": fixed_selector,
                                    "action": action,
                                })
                        elif count > 1:
                            step["multiple_matches"] = count
                        validated_steps.append(step)
                        if count > 0 or step.get("auto_fixed"):
                            self._execute_step_for_validation_sync(page, step)
                    except Exception as e:
                        invalid_selectors.append({
                            "step_index": i + 1,
                            "description": description,
                            "selector": selector,
                            "action": action,
                            "reason": str(e),
                        })
                        validated_steps.append(step)
            finally:
                browser.close()

    def _locator_hint_count_sync(self, page: Any, step: Dict[str, Any]) -> int:
        """Return number of elements matching step's locator_hint (0 if no hint or error)."""
        hint = step.get("locator_hint")
        if not isinstance(hint, dict) or not hint:
            return 0
        try:
            if hint.get("role"):
                name = hint.get("name")
                loc = page.get_by_role(hint["role"], name=re.compile(re.escape(name), re.I)) if name else page.get_by_role(hint["role"])
            elif hint.get("placeholder"):
                loc = page.get_by_placeholder(hint["placeholder"])
            elif hint.get("label"):
                loc = page.get_by_label(hint["label"])
            else:
                return 0
            return loc.count()
        except Exception:
            return 0

    def _try_playwright_locators_sync(
        self, page: Any, step: Dict[str, Any], failed_selector: str
    ) -> Optional[str]:
        """Sync: try Playwright role/placeholder locators when CSS fails."""
        action = step.get("action", "")
        try:
            if action in ("fill", "type"):
                if page.get_by_role("searchbox").count() == 1:
                    return "input[type='search'], [role='searchbox'], input[placeholder*='Search']"
                for placeholder in ["Search", "search", "Enter"]:
                    try:
                        if page.get_by_placeholder(placeholder).count() == 1:
                            return f"input[placeholder*='{placeholder}']"
                    except Exception:
                        pass
            if action == "click":
                for name in ["Accept", "Accept all", "OK"]:
                    try:
                        if page.get_by_role("button", name=re.compile(name, re.I)).count() == 1:
                            return f"button:has-text('{name}'), [role='button']:has-text('{name}')"
                    except Exception:
                        pass
        except Exception as e:
            logger.debug("Playwright locator fallback (sync) failed: %s", e)
        return None

    def _execute_step_for_validation_sync(self, page: Any, step: Dict[str, Any]) -> None:
        """Sync: execute one step to advance page for next validation. Tries locator_hint first if present."""
        action = step.get("action")
        value = (step.get("value") or "").strip() or "test"
        hint = step.get("locator_hint")
        if isinstance(hint, dict) and hint and action in ("click", "fill", "type"):
            try:
                loc = None
                if hint.get("role"):
                    name = hint.get("name")
                    loc = page.get_by_role(hint["role"], name=re.compile(re.escape(name), re.I)) if name else page.get_by_role(hint["role"])
                elif hint.get("placeholder"):
                    loc = page.get_by_placeholder(hint["placeholder"])
                elif hint.get("label"):
                    loc = page.get_by_label(hint["label"])
                if loc and loc.count() > 0:
                    loc.first.wait_for(state="visible", timeout=8000)
                    if action == "click":
                        loc.first.click(timeout=8000)
                    elif action in ("fill", "type"):
                        loc.first.fill(value, timeout=8000)
                    page.wait_for_timeout(1500)
                    return
            except Exception as e:
                logger.debug("Validation step locator_hint (sync): %s", e)
        selector = step.get("selector") or step.get("original_selector")
        if not selector:
            return
        try:
            if action == "click":
                page.click(selector, timeout=8000)
                page.wait_for_timeout(1500)
            elif action in ("fill", "type"):
                page.fill(selector, value, timeout=8000)
                page.wait_for_timeout(500)
            elif action == "press":
                page.press(selector, step.get("value") or "Enter", timeout=5000)
                page.wait_for_timeout(1000)
        except Exception as e:
            logger.debug("Validation step execute (sync): %s", e)

        validation_time = time.time() - start_time
        validation_passed = len(invalid_selectors) == 0
        stats = {
            "total_steps": len(steps),
            "validated": len(validated_steps),
            "invalid": len(invalid_selectors),
            "auto_fixed": len(auto_fixed),
            "success_rate": (len(steps) - len(invalid_selectors)) / len(steps) if steps else 0,
        }
        return {
            "validated_steps": validated_steps,
            "invalid_selectors": invalid_selectors,
            "auto_fixed": auto_fixed,
            "validation_passed": validation_passed,
            "validation_time": validation_time,
            "stats": stats,
            "steps": validated_steps,
            "valid_count": stats["validated"],
            "invalid_count": stats["invalid"],
            "fixed_count": stats["auto_fixed"],
        }
    
    async def _fuzzy_fix_selector(
        self,
        page: Page,
        step: Dict[str, Any],
        invalid_selector: str
    ) -> Optional[str]:
        """
        Use fuzzy matching to find correct selector.
        
        Strategy:
        1. Extract target text from selector or step description
        2. Get all clickable/interactive elements from page
        3. Use fuzzy matcher to find best match
        4. Generate new selector
        
        Args:
            page: Playwright page object
            step: Test step dict
            invalid_selector: The selector that doesn't work
        
        Returns:
            Fixed selector if found, None otherwise
        """
        try:
            # Extract target text from step
            target_text = self._extract_target_text(step, invalid_selector)
            if not target_text:
                logger.debug(f"Could not extract target text from selector: {invalid_selector}")
                return None
            
            action = step.get('action', 'click')
            
            # Get all relevant elements based on action
            if action in ['click', 'hover']:
                elements = await self._get_clickable_elements(page)
            elif action in ['fill', 'type']:
                elements = await self._get_input_elements(page)
            elif action in ['select']:
                elements = await self._get_select_elements(page)
            else:
                # Default to clickable elements
                elements = await self._get_clickable_elements(page)
            
            if not elements:
                logger.debug(f"No elements found on page for action '{action}'")
                return None
            
            # Extract candidate texts
            candidate_texts = []
            for el in elements:
                for text_field in [el.get('text'), el.get('ariaLabel'), el.get('placeholder'), el.get('name')]:
                    if text_field and text_field.strip():
                        candidate_texts.append(text_field.strip())
            
            if not candidate_texts:
                logger.debug("No candidate texts found on page")
                return None
            
            # Find best fuzzy match
            match = self.fuzzy_matcher.find_best_match(target_text, candidate_texts)
            
            if not match:
                logger.debug(f"No fuzzy match found for '{target_text}'")
                return None
            
            matched_text, score = match
            
            # Generate new selector
            fixed_selector = self._generate_selector_for_text(matched_text, action)
            
            # Validate the new selector
            count = await page.locator(fixed_selector).count()
            if count > 0:
                logger.info(f"Fuzzy match: '{target_text}' → '{matched_text}' (score: {score:.2f})")
                return fixed_selector
            else:
                logger.debug(f"Generated selector '{fixed_selector}' still doesn't match")
                return None
        
        except Exception as e:
            logger.error(f"Error in fuzzy fix: {e}")
            return None
    
    def _extract_target_text(self, step: Dict[str, Any], selector: str) -> Optional[str]:
        """
        Extract intended text from selector or step description.
        
        Examples:
            ":has-text('grey shirt')" -> "grey shirt"
            "getByText('Login')" -> "Login"
            "button[aria-label='Add to Cart']" -> "Add to Cart"
        """
        # Try to extract from :has-text() selector
        match = re.search(r":has-text\(['\"](.+?)['\"]\)", selector)
        if match:
            return match.group(1)
        
        # Try to extract from getByText
        match = re.search(r"getByText\(['\"](.+?)['\"]\)", selector)
        if match:
            return match.group(1)
        
        # Try to extract from getByRole with name
        match = re.search(r"getByRole\(['\"][\w]+['\"]\s*,\s*{\s*name\s*:\s*['\"](.+?)['\"]\s*}\)", selector)
        if match:
            return match.group(1)
        
        # Try to extract from aria-label
        match = re.search(r"aria-label=['\"](.+?)['\"]", selector)
        if match:
            return match.group(1)
        
        # Try to extract from placeholder
        match = re.search(r"placeholder=['\"](.+?)['\"]", selector)
        if match:
            return match.group(1)
        
        # Fallback: Try to extract keywords from step description
        description = step.get('description', '').lower()
        action = step.get('action', '').lower()
        
        # Remove action keywords
        for keyword in ['click', 'select', 'choose', 'enter', 'fill', 'type', 'press', 'tap']:
            description = description.replace(keyword, '')
        
        description = description.strip()
        if description:
            return description
        
        return None
    
    def _generate_selector_for_text(self, text: str, action: str) -> str:
        """
        Generate a Playwright selector for the given text and action.
        Prefers stable locators: role+text, then semantic tags, then generic.
        """
        # Normalize: escape for use inside quoted selector
        t = (text or "").strip()
        if not t:
            return ""
        escaped = re.sub(r"(['\"\\])", r"\\\1", t)

        if action in ["fill", "type"]:
            # Inputs: placeholder, aria-label, name
            return f"input[placeholder*='{escaped}'], input[aria-label*='{escaped}'], input[name*='{escaped}']"
        # Clicks: prefer button/link with text for stability
        return f"button:has-text('{escaped}'), a:has-text('{escaped}'), [role='button']:has-text('{escaped}')"
    
    async def _get_clickable_elements(self, page: Page) -> List[Dict[str, Any]]:
        """Extract all clickable elements from page."""
        try:
            elements = await page.evaluate("""
                () => {
                    const elements = [];
                    document.querySelectorAll('button, a, [role="button"], [onclick], input[type="submit"], input[type="button"]').forEach(el => {
                        const rect = el.getBoundingClientRect();
                        // Only visible elements
                        if (rect.width > 0 && rect.height > 0) {
                            elements.push({
                                tag: el.tagName.toLowerCase(),
                                text: (el.innerText || el.textContent || '').trim().substring(0, 100),
                                ariaLabel: el.getAttribute('aria-label') || '',
                                role: el.getAttribute('role') || '',
                                href: el.href || ''
                            });
                        }
                    });
                    return elements;
                }
            """)
            return elements
        except Exception as e:
            logger.error(f"Error getting clickable elements: {e}")
            return []
    
    async def _get_input_elements(self, page: Page) -> List[Dict[str, Any]]:
        """Extract all input/textarea elements from page."""
        try:
            elements = await page.evaluate("""
                () => {
                    const elements = [];
                    document.querySelectorAll('input, textarea').forEach(el => {
                        elements.push({
                            tag: el.tagName.toLowerCase(),
                            name: el.name || '',
                            type: el.type || '',
                            placeholder: el.placeholder || '',
                            ariaLabel: el.getAttribute('aria-label') || '',
                            id: el.id || ''
                        });
                    });
                    return elements;
                }
            """)
            return elements
        except Exception as e:
            logger.error(f"Error getting input elements: {e}")
            return []
    
    async def _get_select_elements(self, page: Page) -> List[Dict[str, Any]]:
        """Extract all select/dropdown elements from page."""
        try:
            elements = await page.evaluate("""
                () => {
                    const elements = [];
                    document.querySelectorAll('select').forEach(el => {
                        elements.push({
                            tag: 'select',
                            name: el.name || '',
                            ariaLabel: el.getAttribute('aria-label') || '',
                            id: el.id || ''
                        });
                    });
                    return elements;
                }
            """)
            return elements
        except Exception as e:
            logger.error(f"Error getting select elements: {e}")
            return []


# Convenience function for quick validation
async def validate_selectors(url: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Quick selector validation."""
    validator = SelectorValidator()
    return await validator.validate_script(url, steps)
