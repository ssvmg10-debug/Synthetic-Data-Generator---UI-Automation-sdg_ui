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
import sys
import os

# Fix for Windows: Set event loop policy before any async operations
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from services.ui_automation.run_status import RunStatusTracker, ExecutionPhase, get_or_create_tracker
from services.ui_automation.agents.healer.agent import HealerAgent
from services.ui_automation.utils.selector_validator import SelectorValidator

logger = logging.getLogger(__name__)


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
        step_timeout_ms: int = 30000,
        enable_healing: bool = True
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
        """
        self.run_id = run_id
        self.headless = headless
        self.screenshot_dir = screenshot_dir or f"screenshots/{run_id}"
        self.max_retries_per_step = max_retries_per_step
        self.step_timeout_ms = step_timeout_ms
        self.enable_healing = enable_healing
        
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
                
                for i, step in enumerate(steps, 1):
                    try:
                        logger.info(f"[{self.run_id}] Executing step {i}/{len(steps)}: {step['action']}")
                        
                        # Execute step with retry
                        step_success = await self._execute_step_with_retry(
                            step, 
                            step_number=i,
                            total_steps=len(steps)
                        )
                        
                        if step_success:
                            steps_executed += 1
                            
                            # Take screenshot
                            screenshot_path = await self._take_screenshot(f"step_{i}_{step['action']}")
                            screenshots.append(screenshot_path)
                            self.tracker.add_screenshot(screenshot_path, step_number=i)
                        
                        else:
                            steps_failed += 1
                            
                            # Try healing if enabled
                            if self.enable_healing and self.healer:
                                logger.info(f"[{self.run_id}] Attempting to heal step {i}")
                                
                                healed = await self._heal_step(step, i)
                                
                                if healed:
                                    steps_healed += 1
                                    steps_executed += 1
                                    logger.info(f"[{self.run_id}] Successfully healed step {i}")
                                else:
                                    error = f"Step {i} failed and could not be healed"
                                    logger.error(f"[{self.run_id}] {error}")
                                    break  # Fail fast
                            else:
                                error = f"Step {i} failed"
                                logger.error(f"[{self.run_id}] {error}")
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
    
    async def _execute_step_with_retry(
        self,
        step: Dict[str, Any],
        step_number: int,
        total_steps: int
    ) -> bool:
        """
        Execute single step with retry logic.
        
        Retry strategy:
        1. Try original selector
        2. Try alternative selectors (if provided)
        3. Return False (let healing handle it)
        
        Args:
            step: Step to execute
            step_number: Step number (1-indexed)
            total_steps: Total number of steps
        
        Returns:
            True if step succeeded, False otherwise
        """
        action = step.get('action')
        selector = step.get('selector', '')
        value = step.get('value', '')
        alternatives = step.get('alternatives', [])
        
        # Build selector list: original + alternatives
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
            await self.page.goto(value, timeout=self.step_timeout_ms, wait_until="networkidle")
            return True
        
        elif action == "click":
            await self.page.click(selector, timeout=self.step_timeout_ms)
            await self.page.wait_for_timeout(1000)  # Wait for navigation/changes
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
            
            # Try healing with fuzzy matching first
            original_selector = step.get('selector', '')
            healed_selector = await self.healer._fuzzy_match_from_page_elements(
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
                    return success
                except:
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
    
    async def _take_screenshot(self, name: str) -> str:
        """
        Take screenshot of current page.
        
        Args:
            name: Screenshot name
        
        Returns:
            Path to screenshot file
        """
        if not self.page:
            return ""
        
        try:
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
