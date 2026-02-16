"""
Enhanced Executor - Retry with alternatives, context-aware healing, fail-fast
Solves: Problem #3 (All-or-nothing execution - one failure = full restart)
"""
from typing import Dict, Any, List, Optional
from playwright.async_api import async_playwright, Page, Browser
from datetime import datetime
import json
import logging
import asyncio
import re
import sys
import os

# Fix for Windows: Set event loop policy before any async operations
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def _should_use_sync_playwright() -> bool:
    """Use sync Playwright in a thread when on Windows without ProactorEventLoop."""
    if sys.platform != "win32":
        return False
    try:
        loop = asyncio.get_running_loop()
        if isinstance(loop, asyncio.ProactorEventLoop):
            return False
        logger.info("Using sync Playwright fallback for execution (Windows non-ProactorEventLoop)")
        return True
    except RuntimeError:
        return False


from services.ui_automation.run_status import RunStatusTracker, ExecutionPhase, get_or_create_tracker
from services.ui_automation.agents.healer.agent import HealerAgent
from services.ui_automation.utils.selector_validator import SelectorValidator
from services.ui_automation.state_manager import SessionState
from services.ui_automation.page_intelligence import (
    extract_page_model_async,
    extract_page_model_sync,
    PageModel,
    PageType,
)

logger = logging.getLogger(__name__)

# Wait for element to appear before click/fill. Lower = fail faster (was 50000, caused ~3min runs on first failure)
WAIT_FOR_SELECTOR_MS = 18000

# Deterministic waits per step (production-grade: reduces race conditions on AEM/React)
# After goto: wait for network to settle then short settle
NETWORK_IDLE_TIMEOUT_MS = 10000
GOTO_SETTLE_MS = 500
# After click/submit: wait for DOM then small settle
AFTER_ACTION_DOM_TIMEOUT_MS = 8000
AFTER_ACTION_SETTLE_MS = 500

# State validation retries: how many times to retry a step if post-step validation fails
STATE_VALIDATION_RETRIES = 2

# Safety limits (avoid infinite loops / runaway runs)
MAX_TOTAL_STEPS = 100
GLOBAL_TIMEOUT_MS = 600000  # 10 minutes


def _try_locator_hint_sync(page: Any, step: Dict[str, Any]) -> bool:
    """Execute step using Playwright locator_hint (get_by_role / get_by_placeholder / get_by_label). Returns True if done."""
    hint = step.get("locator_hint")
    if not isinstance(hint, dict) or not hint:
        return False
    action = step.get("action")
    value = (step.get("value") or "").strip()
    try:
        loc = None
        if hint.get("role"):
            role = hint["role"]
            name = hint.get("name")
            if name:
                loc = page.get_by_role(role, name=re.compile(re.escape(name), re.I))
            else:
                loc = page.get_by_role(role)
        elif hint.get("placeholder"):
            loc = page.get_by_placeholder(hint["placeholder"])
        elif hint.get("label"):
            loc = page.get_by_label(hint["label"])
        if not loc:
            return False
        loc.first.wait_for(state="visible", timeout=WAIT_FOR_SELECTOR_MS)
        if action == "click":
            loc.first.click(timeout=15000)
            page.wait_for_timeout(1000)
            return True
        if action in ("fill", "type"):
            loc.first.fill(value or "", timeout=15000)
            page.wait_for_timeout(500)
            return True
    except Exception as e:
        logger.debug("[locator_hint] Sync hint failed: %s", e)
        return False
    return False


class ExecutionResult:
    """Result of test execution"""
    
    def __init__(
        self,
        success: bool,
        steps_executed: int,
        steps_failed: int,
        steps_healed: int,
        duration_ms: int,
        screenshots: List[str],
        error: Optional[str] = None
    ):
        self.success = success
        self.steps_executed = steps_executed
        self.steps_failed = steps_failed
        self.steps_healed = steps_healed
        self.duration_ms = duration_ms
        self.screenshots = screenshots
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "steps_executed": self.steps_executed,
            "steps_failed": self.steps_failed,
            "steps_healed": self.steps_healed,
            "duration_ms": self.duration_ms,
            "screenshots": self.screenshots,
            "error": self.error
        }


class EnhancedExecutor:
    """
    Enhanced test executor with intelligent retry and healing.
    
    Key improvements over basic executor:
    1. Step-level retry with alternatives (not full restart)
    2. Context-aware healing (uses page state for healing)
    3. Fail-fast on critical errors
    4. Screenshot capture per step
    5. Run status tracking for frontend
    6. Structured error reporting
    
    Execution flow:
    1. Validate all selectors upfront (SelectorValidator)
    2. Execute step-by-step
    3. On failure: Try alternatives → Heal → Skip/Fail
    4. Take screenshots at each step
    5. Track progress in RunStatusTracker
    
    Example:
        executor = EnhancedExecutor(run_id="run_12345")
        
        script = {
            "starting_url": "https://example.com",
            "steps": [
                {"action": "click", "selector": "button", "alternatives": ["#btn", ".submit"]},
                {"action": "fill", "selector": "input[name='user']", "value": "admin"}
            ]
        }
        
        result = await executor.execute(script)
        
        print(f"Success: {result.success}")
        print(f"Healed steps: {result.steps_healed}")
    """
    
    def __init__(
        self,
        run_id: str,
        headless: bool = True,
        screenshot_dir: Optional[str] = None,
        max_retries_per_step: int = 3,
        step_timeout_ms: int = 20000,
        enable_healing: bool = True,
        selector_registry: Optional[Any] = None,
    ):
        """
        Initialize enhanced executor.
        
        Args:
            run_id: Unique run identifier
            headless: Run browser in headless mode
            screenshot_dir: Directory for screenshots
            max_retries_per_step: Maximum retries per step before healing
            step_timeout_ms: Timeout for each step
            enable_healing: Enable self-healing on failures
            selector_registry: Optional SelectorRegistryService for get_primary + record_heal
        """
        self.run_id = run_id
        self.headless = headless
        self.screenshot_dir = screenshot_dir or f"screenshots/{run_id}"
        self.max_retries_per_step = max_retries_per_step
        self.step_timeout_ms = step_timeout_ms
        self.enable_healing = enable_healing
        self.selector_registry = selector_registry
        
        # Create screenshot directory
        os.makedirs(self.screenshot_dir, exist_ok=True)
        
        # Initialize components
        self.tracker = get_or_create_tracker(run_id)
        self.validator = SelectorValidator()
        self.healer = HealerAgent() if enable_healing else None
        
        # Execution state
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        
        logger.info(
            f"EnhancedExecutor initialized for run_id={run_id} "
            f"(retries={max_retries_per_step}, healing={enable_healing})"
        )
    
    async def execute(self, script: Dict[str, Any]) -> ExecutionResult:
        """
        Execute test script with intelligent retry and healing.
        
        Args:
            script: Test script with steps
        
        Returns:
            ExecutionResult with detailed metrics
        """
        logger.info(f"[{self.run_id}] Starting execution")
        
        start_time = datetime.utcnow()
        steps = script.get('steps', [])
        
        # On Windows with non-ProactorEventLoop, run full execution in a thread with sync Playwright
        if _should_use_sync_playwright():
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, lambda: self._execute_sync(script))
        
        steps_executed = 0
        steps_failed = 0
        steps_healed = 0
        screenshots = []
        error = None
        
        try:
            # Phase 1: Validate selectors upfront
            self.tracker.start_phase(ExecutionPhase.GENERATION)
            
            url = script.get('starting_url', '')
            if url:
                validation_result = await self.validator.validate_script(url, steps)
                
                if validation_result['fixed_count'] > 0:
                    logger.info(f"Pre-fixed {validation_result['fixed_count']} selectors")
                    steps = validation_result['steps']  # Use fixed steps
                
                self.tracker.complete_phase(ExecutionPhase.GENERATION, {
                    "validated": validation_result['valid_count'],
                    "fixed": validation_result['fixed_count']
                })
            else:
                self.tracker.skip_phase(ExecutionPhase.GENERATION, "No URL provided")
            
            # Phase 2: Execute steps
            self.tracker.start_phase(ExecutionPhase.EXECUTION)
            
            async with async_playwright() as p:
                self.browser = await p.chromium.launch(headless=self.headless)
                self.page = await self.browser.new_page()
                state = SessionState()
                run_start_ms = int(datetime.utcnow().timestamp() * 1000)

                for i, step in enumerate(steps, 1):
                    # Safety: global step limit and timeout
                    if i > MAX_TOTAL_STEPS:
                        error = f"Aborted: exceeded max steps ({MAX_TOTAL_STEPS})"
                        logger.warning(f"[{self.run_id}] {error}")
                        break
                    elapsed_ms = int(datetime.utcnow().timestamp() * 1000) - run_start_ms
                    if elapsed_ms > GLOBAL_TIMEOUT_MS:
                        error = f"Aborted: global timeout ({GLOBAL_TIMEOUT_MS}ms)"
                        logger.warning(f"[{self.run_id}] {error}")
                        break
                    try:
                        logger.info(
                            f"[{self.run_id}] Executing step {i}/{len(steps)}: {step.get('action')} (intent: {step.get('intent')})",
                            extra={"step_id": i, "run_id": self.run_id, "intent": step.get("intent")},
                        )

                        step_success = False
                        validation_retries = 0

                        while validation_retries <= STATE_VALIDATION_RETRIES:
                            # Page-type / conditional: select_product_with_condition
                            step_success = False
                            if step.get("semantic_action") == "select_product_with_condition" or (
                                step.get("intent") == "select_product_with_condition" and step.get("condition")
                            ):
                                step_success = await self._execute_select_product_with_condition_async(step)
                                if step_success:
                                    state.update_after_action("select_product_with_condition", True, url=self.page.url if self.page else "")

                            if not step_success:
                                step_success = await self._execute_step_with_retry(
                                    step, step_number=i, total_steps=len(steps)
                                )

                            if not step_success:
                                break

                            # Update state after step
                            try:
                                model = await extract_page_model_async(self.page)
                                state.last_page_model = model.to_dict()
                                state.update_after_action(step.get("action", ""), True, url=model.url, page_type=model.page_type)
                            except Exception:
                                pass

                            # Post-step state validation (deterministic: retry if transition failed)
                            valid, should_retry = await self._validate_after_step_async(step, state)
                            if valid:
                                break
                            if not should_retry:
                                break  # Don't retry on validation errors (e.g. extractor failure)
                            if validation_retries >= STATE_VALIDATION_RETRIES:
                                step_success = False  # Validation failed after retries
                                break
                            validation_retries += 1
                            logger.info(f"[{self.run_id}] Step {i} validation failed, retrying ({validation_retries}/{STATE_VALIDATION_RETRIES})")

                        if step_success:
                            steps_executed += 1
                            screenshot_path = await self._take_screenshot(f"step_{i}_{step['action']}")
                            screenshots.append(screenshot_path)
                            self.tracker.add_screenshot(screenshot_path, step_number=i)

                        else:
                            steps_failed += 1
                            # Preserve screenshot on every attempt including failed (per production plan)
                            try:
                                fail_path = await self._take_screenshot(f"step_{i}_{step.get('action', 'unknown')}_failed")
                                if fail_path:
                                    screenshots.append(fail_path)
                                    self.tracker.add_screenshot(fail_path, step_number=i)
                            except Exception:
                                pass
                            # Try healing if enabled
                            if self.enable_healing and self.healer:
                                logger.info(f"[{self.run_id}] Attempting to heal step {i}")
                                
                                healed = await self._heal_step(step, i)
                                
                                if healed:
                                    steps_healed += 1
                                    steps_executed += 1
                                    logger.info(
                                        f"[{self.run_id}] Successfully healed step {i}",
                                        extra={"step_id": i, "healed": True, "run_id": self.run_id},
                                    )
                                else:
                                    error = f"Step {i} failed and could not be healed"
                                    logger.error(f"[{self.run_id}] {error}", extra={"step_id": i, "healed": False})
                                    await self._capture_fatal_snapshot(i, error)
                                    break  # Fail fast
                            else:
                                error = f"Step {i} failed"
                                logger.error(f"[{self.run_id}] {error}", extra={"step_id": i})
                                await self._capture_fatal_snapshot(i, error)
                                break  # Fail fast
                    
                    except Exception as e:
                        steps_failed += 1
                        error = f"Step {i} exception: {str(e)}"
                        logger.error(f"[{self.run_id}] {error}", exc_info=True)
                        break  # Fail fast on exceptions
            
            # Complete execution phase
            success = (steps_failed == 0 and steps_executed == len(steps))
            
            self.tracker.complete_phase(ExecutionPhase.EXECUTION, {
                "steps_executed": steps_executed,
                "steps_failed": steps_failed,
                "steps_healed": steps_healed
            })
            
            # Complete run
            self.tracker.complete_run(success)
        
        except Exception as e:
            error = f"Execution error: {str(e)}"
            logger.error(f"[{self.run_id}] {error}", exc_info=True)
            self.tracker.fail_phase(ExecutionPhase.EXECUTION, error)
            self.tracker.complete_run(False)
            success = False
        
        finally:
            # Cleanup
            if self.browser:
                await self.browser.close()
        
        # Calculate duration
        end_time = datetime.utcnow()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        result = ExecutionResult(
            success=success,
            steps_executed=steps_executed,
            steps_failed=steps_failed,
            steps_healed=steps_healed,
            duration_ms=duration_ms,
            screenshots=screenshots,
            error=error
        )
        
        logger.info(
            f"[{self.run_id}] Execution completed: "
            f"success={success}, executed={steps_executed}/{len(steps)}, "
            f"healed={steps_healed}, duration={duration_ms}ms"
        )
        
        return result

    def _execute_sync(self, script: Dict[str, Any]) -> "ExecutionResult":
        """Run full execution with sync Playwright (used on Windows when event loop does not support subprocess)."""
        from playwright.sync_api import sync_playwright

        start_time = datetime.utcnow()
        steps = script.get("steps", [])
        url = script.get("starting_url", "")
        steps_executed = 0
        steps_failed = 0
        steps_healed = 0
        screenshots: List[str] = []
        error = None
        success = False

        try:
            self.tracker.start_phase(ExecutionPhase.GENERATION)
            if url:
                validation_result = self.validator._validate_script_sync(url, steps)
                if validation_result.get("fixed_count", 0) > 0:
                    steps = validation_result["steps"]
                self.tracker.complete_phase(ExecutionPhase.GENERATION, {
                    "validated": validation_result["valid_count"],
                    "fixed": validation_result["fixed_count"],
                })
            else:
                self.tracker.skip_phase(ExecutionPhase.GENERATION, "No URL provided")

            self.tracker.start_phase(ExecutionPhase.EXECUTION)

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                page = browser.new_page()
                context = page.context
                try:
                    # If first step is goto we'll load there; else load starting_url once and wait for banner
                    first_is_goto = steps and steps[0].get("action") == "goto"
                    if url and not first_is_goto:
                        page.goto(url, wait_until="domcontentloaded", timeout=60000)
                        page.wait_for_timeout(2500)
                    for i, step in enumerate(steps, 1):
                        try:
                            page = self._ensure_page_sync(page, context, browser, url, steps, i)
                            logger.info(f"[{self.run_id}] Executing step {i}/{len(steps)}: {step.get('action')}")
                            did_run = False
                            if step.get("semantic_action") == "select_product_with_condition" or (
                                step.get("intent") == "select_product_with_condition" and step.get("condition")
                            ):
                                did_run = self._execute_select_product_with_condition_sync(page, step)
                            if not did_run:
                                self._execute_action_sync(page, step)
                            steps_executed += 1
                            path = self._take_screenshot_sync(page, f"step_{i}_{step.get('action')}")
                            if path:
                                screenshots.append(path)
                                self.tracker.add_screenshot(path, step_number=i)
                        except Exception as e:
                            steps_failed += 1
                            error = f"Step {i} failed: {str(e)}"
                            logger.error(f"[{self.run_id}] {error}", exc_info=True)
                            # Try healing in sync path (same as async)
                            if self.enable_healing and self.healer:
                                try:
                                    logger.info(f"[{self.run_id}] Attempting to heal step {i} (sync)")
                                    page_elements = page.evaluate("""() => {
                                        const elements = [];
                                        document.querySelectorAll('button, a, input, select').forEach((el) => {
                                            elements.push({
                                                tag: el.tagName.toLowerCase(),
                                                text: (el.innerText || el.textContent || '').trim().substring(0, 100),
                                                id: el.id || '', name: el.name || '', type: el.type || '', placeholder: el.placeholder || ''
                                            });
                                        });
                                        return elements;
                                    }""")
                                    healed_selector = self.healer._fuzzy_match_from_page_elements(
                                        step.get("selector", ""), page_elements
                                    )
                                    if healed_selector:
                                        healed_step = {**step, "selector": healed_selector}
                                        self._execute_action_sync(page, healed_step)
                                        steps_executed += 1
                                        steps_healed += 1
                                        path = self._take_screenshot_sync(page, f"step_{i}_{step.get('action')}_healed")
                                        if path:
                                            screenshots.append(path)
                                            self.tracker.add_screenshot(path, step_number=i)
                                        logger.info(f"[{self.run_id}] Step {i} healed with selector: {healed_selector[:60]}")
                                        continue
                                    # Fuzzy match failed: try locator_hint (get_by_role / get_by_placeholder)
                                    if step.get("locator_hint") and step.get("action") in ("click", "fill", "type"):
                                        if _try_locator_hint_sync(page, step):
                                            steps_executed += 1
                                            steps_healed += 1
                                            path = self._take_screenshot_sync(page, f"step_{i}_{step.get('action')}_locator_hint")
                                            if path:
                                                screenshots.append(path)
                                                self.tracker.add_screenshot(path, step_number=i)
                                            logger.info(f"[{self.run_id}] Step {i} healed via locator_hint")
                                            continue
                                except Exception as heal_err:
                                    logger.debug("[%s] Sync heal failed: %s", self.run_id, heal_err)
                            break
                finally:
                    browser.close()

            success = steps_failed == 0 and steps_executed == len(steps)
            self.tracker.complete_phase(ExecutionPhase.EXECUTION, {
                "steps_executed": steps_executed,
                "steps_failed": steps_failed,
                "steps_healed": steps_healed,
            })
            self.tracker.complete_run(success)
        except Exception as e:
            error = f"Execution error: {str(e)}"
            logger.error(f"[{self.run_id}] {error}", exc_info=True)
            self.tracker.fail_phase(ExecutionPhase.EXECUTION, error)
            self.tracker.complete_run(False)
            success = False

        end_time = datetime.utcnow()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        result = ExecutionResult(
            success=success,
            steps_executed=steps_executed,
            steps_failed=steps_failed,
            steps_healed=steps_healed,
            duration_ms=duration_ms,
            screenshots=screenshots,
            error=error,
        )
        logger.info(
            f"[{self.run_id}] Execution completed (sync): "
            f"success={success}, executed={steps_executed}/{len(steps)}, duration={duration_ms}ms"
        )
        return result

    def _ensure_page_sync(
        self,
        page: Any,
        context: Any,
        browser: Any,
        url: str,
        steps: List[Dict[str, Any]],
        current_step_index: int,
    ) -> Any:
        """If the current page was closed (e.g. by site or popup), recover by using an open page or creating one."""
        try:
            if not page.is_closed():
                return page
        except Exception:
            pass
        logger.warning("[%s] Page was closed; attempting recovery", self.run_id)
        # Prefer an existing open page in the same context (e.g. new tab from link)
        for p in context.pages:
            try:
                if not p.is_closed():
                    logger.info("[%s] Using existing open page for next step", self.run_id)
                    return p
            except Exception:
                continue
        # No open page: create one and go to starting_url or last goto step so we can continue
        page = context.new_page()
        nav_url = url or ""
        for j in range(current_step_index - 1):
            if steps[j].get("action") == "goto" and steps[j].get("value"):
                nav_url = steps[j].get("value", "")
        if nav_url:
            page.goto(nav_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
        return page

    def _execute_select_product_with_condition_sync(self, page: Any, step: Dict[str, Any]) -> bool:
        """Sync version: same logic as async - get_by_role, scroll_into_view, try multiple buttons."""
        condition = step.get("condition") or {}
        price_max = condition.get("price_max")
        if price_max is None:
            return False
        try:
            model = extract_page_model_sync(page)
            eligible = [c for c in model.product_cards if c.price is not None and c.price <= price_max]
            if not eligible:
                eligible = model.product_cards[:1]
            if eligible:
                card = eligible[0]
                for sel in [card.buy_button_selector, card.link_selector]:
                    if sel and sel.strip():
                        try:
                            page.locator(sel).first.wait_for(state="visible", timeout=8000)
                            page.locator(sel).first.scroll_into_view_if_needed(timeout=5000)
                            page.locator(sel).first.click(timeout=10000)
                            page.wait_for_timeout(2000)
                            logger.info("[%s] select_product_with_condition (sync): clicked %s", self.run_id, sel[:60])
                            return True
                        except Exception:
                            pass
            for name_pattern in ["Buy Now", "Know More", "Buy", "Add to cart"]:
                try:
                    loc = page.get_by_role("button", name=re.compile(re.escape(name_pattern), re.I)).first
                    loc.wait_for(state="visible", timeout=5000)
                    loc.scroll_into_view_if_needed(timeout=3000)
                    loc.click(timeout=10000)
                    page.wait_for_timeout(2000)
                    logger.info("[%s] select_product_with_condition (sync): get_by_role %s", self.run_id, name_pattern)
                    return True
                except Exception:
                    pass
                try:
                    loc = page.get_by_role("link", name=re.compile(re.escape(name_pattern), re.I)).first
                    loc.wait_for(state="visible", timeout=5000)
                    loc.scroll_into_view_if_needed(timeout=3000)
                    loc.click(timeout=10000)
                    page.wait_for_timeout(2000)
                    return True
                except Exception:
                    pass
            for fallback in ["button:has-text('Buy Now')", ".cmp-button:has-text('Buy Now')", "a:has-text('Know More')"]:
                try:
                    loc = page.locator(fallback)
                    for i in range(min(loc.count(), 5)):
                        try:
                            btn = loc.nth(i)
                            btn.wait_for(state="visible", timeout=3000)
                            btn.scroll_into_view_if_needed(timeout=3000)
                            btn.click(timeout=10000)
                            page.wait_for_timeout(2000)
                            return True
                        except Exception:
                            continue
                except Exception:
                    continue
        except Exception as e:
            logger.warning("[%s] select_product_with_condition (sync) failed: %s", self.run_id, e)
        return False

    def _execute_action_sync(self, page: Any, step: Dict[str, Any]) -> None:
        """Execute a single step with sync Playwright page. Tries locator_hint (get_by_role/placeholder) first if present."""
        action = step.get("action")
        selector = step.get("selector", "")
        value = step.get("value", "")
        if action == "goto":
            page.goto(value or "", timeout=60000, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT_MS)
            except Exception:
                pass
            page.wait_for_timeout(GOTO_SETTLE_MS)
            return
        # Prefer Playwright locator_hint (role/placeholder/label) when present
        if step.get("locator_hint") and action in ("click", "fill", "type"):
            if _try_locator_hint_sync(page, step):
                return
        if action == "click":
            alternatives = step.get("alternatives") or []
            selectors_to_try = [selector] + [s for s in alternatives if s and isinstance(s, str) and s != selector]
            last_err = None
            for sel in selectors_to_try:
                try:
                    page.wait_for_selector(sel, state="visible", timeout=WAIT_FOR_SELECTOR_MS)
                    page.click(sel, timeout=self.step_timeout_ms)
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=AFTER_ACTION_DOM_TIMEOUT_MS)
                    except Exception:
                        pass
                    page.wait_for_timeout(AFTER_ACTION_SETTLE_MS)
                    return
                except Exception as e:
                    last_err = e
                    logger.debug("[%s] Selector failed %s: %s", self.run_id, sel[:50], e)
            if last_err:
                raise last_err
            return
        if action == "fill":
            alternatives = step.get("alternatives") or []
            selectors_to_try = [selector] + [s for s in alternatives if s and isinstance(s, str) and s != selector]
            last_err = None
            for sel in selectors_to_try:
                try:
                    page.wait_for_selector(sel, state="visible", timeout=WAIT_FOR_SELECTOR_MS)
                    page.fill(sel, value or "", timeout=self.step_timeout_ms)
                    return
                except Exception as e:
                    last_err = e
                    logger.debug("[%s] Fill selector failed %s: %s", self.run_id, sel[:50], e)
            if last_err:
                raise last_err
            return
        if action == "select":
            page.select_option(selector, value or "", timeout=self.step_timeout_ms)
            return
        if action == "press":
            page.press(selector, value or "", timeout=self.step_timeout_ms)
            return
        if action == "wait":
            wait_ms = int(value) if value else 1000
            page.wait_for_timeout(wait_ms)
            return
        # Other actions: treat as click if selector present
        if selector:
            page.click(selector, timeout=self.step_timeout_ms)
            page.wait_for_timeout(500)

    def _take_screenshot_sync(self, page: Any, name: str) -> str:
        """Take screenshot with sync Playwright page."""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = os.path.join(self.screenshot_dir, filename)
            os.makedirs(self.screenshot_dir, exist_ok=True)
            page.screenshot(path=filepath, full_page=False)
            return filepath
        except Exception as e:
            logger.debug("Screenshot failed: %s", e)
            return ""
    
    async def _execute_select_product_with_condition_async(self, step: Dict[str, Any]) -> bool:
        """
        State-aware + component-aware: extract page model, filter product_cards by condition (e.g. price < 30000), click first match.
        Uses get_by_role (resilient), scroll_into_view, and tries multiple Buy Now buttons when first fails.
        """
        if not self.page:
            return False
        condition = step.get("condition") or {}
        price_max = condition.get("price_max")
        if price_max is None:
            return False
        try:
            model = await extract_page_model_async(self.page)
            eligible = [
                c for c in model.product_cards
                if c.price is not None and c.price <= price_max
            ]
            if not eligible:
                eligible = model.product_cards[:1]
            if not eligible:
                logger.debug("[%s] No eligible product cards for condition %s", self.run_id, condition)

            # 1. Try page model selectors first (product card specific)
            if eligible:
                card = eligible[0]
                for sel in [card.buy_button_selector, card.link_selector]:
                    if sel and sel.strip():
                        try:
                            loc = self.page.locator(sel).first
                            await loc.wait_for(state="visible", timeout=8000)
                            await loc.scroll_into_view_if_needed(timeout=5000)
                            await loc.click(timeout=10000)
                            await self.page.wait_for_timeout(2000)
                            logger.info("[%s] select_product_with_condition: clicked %s (price_max=%s)", self.run_id, sel[:60], price_max)
                            return True
                        except Exception as e:
                            logger.debug("[%s] Selector %s failed: %s", self.run_id, sel[:40], e)

            # 2. Context-aware: get_by_role (resilient to DOM changes) - try each variant
            for name_pattern in ["Buy Now", "Know More", "Buy", "Add to cart"]:
                try:
                    loc = self.page.get_by_role("button", name=re.compile(re.escape(name_pattern), re.I)).first
                    await loc.wait_for(state="visible", timeout=5000)
                    await loc.scroll_into_view_if_needed(timeout=3000)
                    await loc.click(timeout=10000)
                    await self.page.wait_for_timeout(2000)
                    logger.info("[%s] select_product_with_condition: clicked get_by_role %s", self.run_id, name_pattern)
                    return True
                except Exception:
                    pass
                try:
                    loc = self.page.get_by_role("link", name=re.compile(re.escape(name_pattern), re.I)).first
                    await loc.wait_for(state="visible", timeout=5000)
                    await loc.scroll_into_view_if_needed(timeout=3000)
                    await loc.click(timeout=10000)
                    await self.page.wait_for_timeout(2000)
                    logger.info("[%s] select_product_with_condition: clicked link %s", self.run_id, name_pattern)
                    return True
                except Exception:
                    pass

            # 3. Fallback: try each Buy Now by index (first may be hidden/wrong - LG has multiple)
            for fallback in [
                "button:has-text('Buy Now')",
                ".cmp-button:has-text('Buy Now')",
                "a:has-text('Know More')",
                "button:has-text('Buy')",
            ]:
                try:
                    loc = self.page.locator(fallback)
                    count = await loc.count()
                    for i in range(min(count, 5)):  # Try first 5 matching buttons
                        try:
                            btn = loc.nth(i)
                            await btn.wait_for(state="visible", timeout=3000)
                            await btn.scroll_into_view_if_needed(timeout=3000)
                            await btn.click(timeout=10000)
                            await self.page.wait_for_timeout(2000)
                            logger.info("[%s] select_product_with_condition: clicked fallback %s [%d]", self.run_id, fallback, i)
                            return True
                        except Exception:
                            continue
                except Exception:
                    continue
        except Exception as e:
            logger.warning("[%s] select_product_with_condition failed: %s", self.run_id, e)
        return False

    async def _validate_after_step_async(
        self, step: Dict[str, Any], state: SessionState
    ) -> tuple[bool, bool]:
        """
        Post-step state validation. Returns (valid, should_retry).
        If validation fails for critical transitions, returns (False, True) to trigger retry.
        """
        if not self.page:
            return True, False
        try:
            url = self.page.url or ""
            intent = step.get("intent", "")
            action = step.get("action", "")

            # After search submit: verify we have search results (product grid or URL contains search)
            # Only validate when the step would have submitted search (press Enter or click search button)
            search_submit_action = intent in ("search_submit", "search") and action in ("press", "click")
            if search_submit_action:
                await self.page.wait_for_timeout(3000)  # Allow results to render (LG is dynamic)
                model = await extract_page_model_async(self.page)
                has_results = (
                    len(model.product_cards) > 0
                    or "search" in url.lower()
                    or model.page_type in (PageType.SEARCH_RESULTS, PageType.PRODUCT_LISTING)
                )
                if not has_results:
                    logger.warning("[%s] Validation: search did not yield results, may need retry", self.run_id)
                    return False, True

            # After add to cart / buy now: verify we navigated (product detail, cart, or checkout)
            if intent in ("add_to_cart", "buy_now", "select_product_with_condition"):
                await self.page.wait_for_timeout(1500)
                model = await extract_page_model_async(self.page)
                url_changed = url != (state.current_url or "")
                expected_page = model.page_type in (
                    PageType.PRODUCT_DETAIL,
                    PageType.CART,
                    PageType.CHECKOUT,
                    PageType.GUEST_CHECKOUT,
                )
                if not url_changed and not expected_page:
                    logger.warning(
                        "[%s] Validation: buy/add_to_cart did not transition to expected page",
                        self.run_id,
                    )
                    return False, True

            # After pincode check: verify delivery options or availability message
            if intent == "pincode_check":
                await self.page.wait_for_timeout(2000)
                try:
                    has_delivery = (
                        await self.page.get_by_text("delivery", exact=False).count() > 0
                        or await self.page.get_by_text("Delivery", exact=False).count() > 0
                    )
                    if not has_delivery:
                        logger.warning("[%s] Validation: pincode check may not have completed", self.run_id)
                        return False, True
                except Exception:
                    pass

            # After checkout click: verify URL contains checkout
            if intent in ("checkout", "guest_checkout"):
                await self.page.wait_for_timeout(2000)
                if "checkout" not in url.lower() and "cart" not in url.lower():
                    model = await extract_page_model_async(self.page)
                    if not model.checkout_visible:
                        logger.warning("[%s] Validation: checkout page not reached", self.run_id)
                        return False, True

            return True, False
        except Exception as e:
            logger.debug("[%s] Post-step validation: %s", self.run_id, e)
            return True, False  # Don't retry on validation error (might be extractor issue)

    def _get_registry_primary_selector(self, host: str, intent_name: str) -> Optional[str]:
        """Look up primary selector for host+intent from Selector Registry (UIElement / LocatorRegistry)."""
        if not self.selector_registry:
            return None
        return self.selector_registry.get_primary_selector(host, intent_name)

    async def _execute_step_with_retry(
        self,
        step: Dict[str, Any],
        step_number: int,
        total_steps: int
    ) -> bool:
        """
        Execute single step with deterministic locator attempt order (production-grade):

        1. locator_hint (get_by_role / get_by_placeholder / get_by_label)
        2. Registry primary selector (if host+intent has high-confidence stored selector)
        3. Step selector + alternatives
        On failure → healing tries: semantic action → fuzzy/text healer → locator_hint again.
        """
        action = step.get('action')
        selector = step.get('selector', '')
        value = step.get('value', '')
        alternatives = step.get('alternatives', [])

        # 1) Try locator_hint first (most resilient to DOM changes)
        if step.get("locator_hint") and action in ("click", "fill", "type") and self.page:
            try:
                if await self._try_locator_hint_async(step):
                    logger.debug(f"[{self.run_id}] Step {step_number} succeeded via locator_hint")
                    return True
            except Exception as e:
                logger.debug(f"[{self.run_id}] locator_hint failed: {e}")

        # 2) Registry primary (when Selector Registry is implemented)
        host = ""
        if self.page and self.page.url:
            try:
                from urllib.parse import urlparse
                host = urlparse(self.page.url).netloc or ""
            except Exception:
                pass
        intent_name = step.get("intent") or step.get("semantic_action") or ""
        registry_primary = self._get_registry_primary_selector(host, intent_name) if host else None
        if registry_primary and registry_primary not in (selector,):
            try:
                if await self._execute_action(action, registry_primary, value):
                    logger.debug(f"[{self.run_id}] Step {step_number} succeeded via registry_primary")
                    return True
            except Exception as e:
                logger.debug(f"[{self.run_id}] registry_primary failed: {e}")

        # 3) Step selector + alternatives
        selectors_to_try = [selector] + [alt for alt in alternatives if alt != selector]
        
        for attempt, sel in enumerate(selectors_to_try, 1):
            try:
                logger.debug(
                    f"[{self.run_id}] Step {step_number}: Trying selector '{sel}' "
                    f"(attempt {attempt}/{len(selectors_to_try)})"
                )
                
                success = await self._execute_action(action, sel, value)
                
                if success:
                    if attempt > 1:
                        logger.info(
                            f"[{self.run_id}] Step {step_number} succeeded with "
                            f"alternative selector (attempt {attempt})"
                        )
                    return True
            
            except Exception as e:
                logger.debug(
                    f"[{self.run_id}] Step {step_number} attempt {attempt} failed: {e}"
                )
                
                if attempt >= len(selectors_to_try):
                    # All attempts exhausted
                    return False
                
                # Wait briefly before next attempt
                await asyncio.sleep(0.5)
        
        return False
    
    async def _try_locator_hint_async(self, step: Dict[str, Any]) -> bool:
        """Execute step using Playwright locator_hint (get_by_role / get_by_placeholder / get_by_label). Returns True if done."""
        if not self.page:
            return False
        hint = step.get("locator_hint")
        if not isinstance(hint, dict) or not hint:
            return False
        action = step.get("action")
        value = (step.get("value") or "").strip()
        try:
            loc = None
            if hint.get("role"):
                role = hint["role"]
                name = hint.get("name")
                if name:
                    loc = self.page.get_by_role(role, name=re.compile(re.escape(name), re.I))
                else:
                    loc = self.page.get_by_role(role)
            elif hint.get("placeholder"):
                loc = self.page.get_by_placeholder(hint["placeholder"])
            elif hint.get("label"):
                loc = self.page.get_by_label(hint["label"])
            if not loc:
                return False
            await loc.first.wait_for(state="visible", timeout=WAIT_FOR_SELECTOR_MS)
            if action == "click":
                await loc.first.click(timeout=15000)
                await self.page.wait_for_timeout(1000)
                return True
            if action in ("fill", "type"):
                await loc.first.fill(value or "", timeout=15000)
                await self.page.wait_for_timeout(500)
                return True
        except Exception as e:
            logger.debug("[locator_hint] Async hint failed: %s", e)
            return False
        return False

    async def _execute_action(
        self,
        action: str,
        selector: str,
        value: str
    ) -> bool:
        """
        Execute single action on page.

        Args:
            action: Action type (goto, click, fill, select, etc.)
            selector: Element selector
            value: Action value

        Returns:
            True if action succeeded

        Raises:
            Exception if action fails
        """
        if not self.page:
            raise RuntimeError("No page available")
        
        if action == "goto":
            await self.page.goto(value, timeout=60000, wait_until="domcontentloaded")
            # Deterministic wait: networkidle then short settle (per production plan)
            try:
                await self.page.wait_for_load_state("networkidle", timeout=NETWORK_IDLE_TIMEOUT_MS)
            except Exception:
                pass  # SPAs may never reach networkidle; domcontentloaded is enough
            await self.page.wait_for_timeout(GOTO_SETTLE_MS)
            return True

        elif action == "click":
            # Explicit wait for element (reduces race conditions on dynamic sites)
            await self.page.locator(selector).first.wait_for(state="visible", timeout=WAIT_FOR_SELECTOR_MS)
            await self.page.click(selector, timeout=self.step_timeout_ms)
            # Post-click: domcontentloaded then settle (reduces race conditions)
            try:
                await self.page.wait_for_load_state("domcontentloaded", timeout=AFTER_ACTION_DOM_TIMEOUT_MS)
            except Exception:
                pass
            await self.page.wait_for_timeout(AFTER_ACTION_SETTLE_MS)
            return True
        
        elif action == "fill":
            await self.page.fill(selector, value, timeout=self.step_timeout_ms)
            return True
        
        elif action == "select":
            await self.page.select_option(selector, value, timeout=self.step_timeout_ms)
            return True
        
        elif action == "press":
            await self.page.press(selector, value, timeout=self.step_timeout_ms)
            return True
        
        elif action == "wait":
            wait_time = int(value) if value else 1000
            await self.page.wait_for_timeout(wait_time)
            return True
        
        else:
            logger.warning(f"Unknown action: {action}")
            return False
    
    async def _heal_step(
        self,
        step: Dict[str, Any],
        step_number: int
    ) -> bool:
        """
        Attempt to heal failed step using HealerAgent.
        
        Args:
            step: Failed step
            step_number: Step number
        
        Returns:
            True if healing succeeded and step executed
        """
        if not self.healer or not self.page:
            return False

        # For select_product_with_condition: retry semantic action (get_by_role, multiple buttons)
        if (step.get("intent") == "select_product_with_condition" or step.get("semantic_action") == "select_product_with_condition") and step.get("condition"):
            try:
                if await self._execute_select_product_with_condition_async(step):
                    self.tracker.add_healing_attempt(
                        step_number=step_number,
                        original_selector=step.get("selector", ""),
                        healed_selector="(select_product_with_condition)",
                        strategy="semantic_retry",
                        success=True,
                    )
                    self._record_heal_to_registry(step, "(select_product_with_condition)", "semantic_retry")
                    return True
            except Exception:
                pass

        try:
            # Extract page elements for context-aware healing
            page_elements = await self.page.evaluate("""
                () => {
                    const elements = [];
                    document.querySelectorAll('button, a, input, select').forEach((el, i) => {
                        elements.push({
                            tag: el.tagName.toLowerCase(),
                            text: (el.innerText || el.textContent || '').trim().substring(0, 100),
                            id: el.id || '',
                            name: el.name || '',
                            type: el.type || '',
                            placeholder: el.placeholder || ''
                        });
                    });
                    return elements;
                }
            """)
            
            # Prepare failure context
            failure_context = {
                "original_selector": step.get('selector'),
                "action": step.get('action'),
                "value": step.get('value'),
                "page_elements": page_elements
            }
            
            # Try healing with fuzzy matching first (_fuzzy_match_from_page_elements is sync)
            original_selector = step.get('selector', '')
            healed_selector = self.healer._fuzzy_match_from_page_elements(
                original_selector,
                page_elements
            )
            
            if healed_selector:
                # Record healing attempt
                self.tracker.add_healing_attempt(
                    step_number=step_number,
                    original_selector=original_selector,
                    healed_selector=healed_selector,
                    strategy="fuzzy_match",
                    success=True
                )
                
                # Try healed selector
                try:
                    success = await self._execute_action(
                        step.get('action'),
                        healed_selector,
                        step.get('value', '')
                    )
                    if success:
                        self._record_heal_to_registry(step, healed_selector, "fuzzy_match")
                        return True
                except Exception:
                    pass
            
            # Before giving up: try step via locator_hint (get_by_role / get_by_placeholder)
            if step.get("locator_hint") and step.get("action") in ("click", "fill", "type"):
                try:
                    if await self._try_locator_hint_async(step):
                        self.tracker.add_healing_attempt(
                            step_number=step_number,
                            original_selector=original_selector,
                            healed_selector="(locator_hint)",
                            strategy="locator_hint",
                            success=True
                        )
                        self._record_heal_to_registry(step, "(locator_hint)", "locator_hint")
                        return True
                except Exception:
                    pass
            
            # If fuzzy matching didn't work, record failure
            self.tracker.add_healing_attempt(
                step_number=step_number,
                original_selector=original_selector,
                healed_selector=None,
                strategy="fuzzy_match",
                success=False
            )
            
            return False
        
        except Exception as e:
            logger.error(f"Error during healing: {e}", exc_info=True)
            return False

    def _record_heal_to_registry(self, step: Dict[str, Any], selector_used: str, source: str) -> None:
        """Persist successful heal to Selector Registry (host + intent) for future runs. Skips placeholder selectors."""
        if not self.selector_registry or not self.page:
            return
        if not selector_used or selector_used.strip().startswith("("):
            return  # Don't store semantic placeholders like "(locator_hint)" as selectors
        try:
            from urllib.parse import urlparse
            url = self.page.url or ""
            host = urlparse(url).netloc or ""
            intent = step.get("intent") or step.get("semantic_action") or ""
            if host and intent:
                self.selector_registry.record_heal(host, intent, selector_used.strip(), source=source, confidence=0.8)
        except Exception as e:
            logger.debug("Record heal to registry: %s", e)

    async def _capture_fatal_snapshot(self, step_number: int, error_msg: str) -> None:
        """On fatal failure save DOM dump + HTML to run directory for debugging."""
        if not self.page:
            return
        try:
            os.makedirs(self.screenshot_dir, exist_ok=True)
            html_path = os.path.join(self.screenshot_dir, f"fatal_step_{step_number}.html")
            content = await self.page.content()
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(f"<!-- Error: {error_msg} -->\n")
                f.write(content)
            logger.info(f"[{self.run_id}] Fatal snapshot saved: {html_path}")
        except Exception as e:
            logger.debug("Fatal snapshot failed: %s", e)
    
    async def _take_screenshot(self, name: str) -> str:
        """
        Take screenshot of current page.
        Ensures screenshot directory exists before writing (robust for all code paths).
        
        Args:
            name: Screenshot name
        
        Returns:
            Path to screenshot file
        """
        if not self.page:
            return ""
        
        try:
            os.makedirs(self.screenshot_dir, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = os.path.join(self.screenshot_dir, filename)
            
            await self.page.screenshot(path=filepath, full_page=False)
            
            logger.debug(f"[{self.run_id}] Screenshot saved: {filepath}")
            
            return filepath
        
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return ""


# Convenience function
async def execute_with_tracking(
    run_id: str,
    script: Dict[str, Any],
    **kwargs
) -> ExecutionResult:
    """Quick execution with tracking"""
    executor = EnhancedExecutor(run_id, **kwargs)
    return await executor.execute(script)
