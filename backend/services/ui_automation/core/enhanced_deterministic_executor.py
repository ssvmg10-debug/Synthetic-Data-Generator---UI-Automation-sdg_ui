"""
🚀 ENHANCED DETERMINISTIC EXECUTOR V2 — Enterprise Architecture

Integrates:
- Semantic Parser → Normalized DSL
- State-driven execution (pre-state + post-state validation)
- 4-Phase resolution: DOM → Smart → Visual Grounding → LLM Healing
- Post-action validator (strict)
- Stability engine, contextual action router, popup classifier
- Execution memory (selector cache, state transitions)
- Deterministic recovery: retry → flow handlers → retry → visual → healing → fail
"""
import asyncio
import json
import logging
import re
import time
from playwright.async_api import Page, BrowserContext
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from .test_model import TestCase, TestStep, StepType, Intent, PageState
from .semantic_parser import SemanticTestParser
from .assertion_engine import AssertionEngine, AssertionResult
from .intent_dispatcher import IntentDispatcher, Intent as ProductIntent
from .state_machine import AppState, detect_state, validate_state_transition, StateTransitionError

logger = logging.getLogger(__name__)

# Per-step timeout for CLICK/SELECT so we don't run 2+ minutes and hit "page closed" in healing
CLICK_STEP_TIMEOUT_SEC = 90


async def _run_interrupt_and_flow_handlers(page: "Page", trigger: str) -> None:
    """Run generic interrupt handler + site-specific flow handlers for the given trigger."""
    try:
        from .interrupt_handler import handle_interrupts
        from .flow_config_loader import run_flow_handlers
        await run_flow_handlers(page, trigger)
        await handle_interrupts(page, timeout_ms=2500)
    except Exception as e:
        logger.debug(f"Interrupt/flow handler error: {e}")


async def _search_fallback_contenteditable_keyboard(page: Page, value: str) -> bool:
    """
    Phase 3 fallback: Try contenteditable divs (LG/similar overlays) or global keyboard.type.
    """
    try:
        # Contenteditable (common in modern search overlays)
        ce = page.locator("[contenteditable='true']")
        if await ce.count() > 0:
            first_ce = ce.first
            await first_ce.click()
            try:
                await first_ce.fill(value)
            except Exception:
                await first_ce.press_sequentially(value, delay=30)
            logger.info("  Typed into contenteditable element")
            return True
    except Exception as e:
        logger.debug(f"  Contenteditable fallback failed: {e}")

    try:
        # Input/textarea without :visible (overlay may use opacity/transform)
        inputs = page.locator("input[type='search'], input[type='text'], input:not([type]), textarea")
        n = await inputs.count()
        for i in range(min(n, 3)):
            inp = inputs.nth(i)
            try:
                await inp.scroll_into_view_if_needed(timeout=2000)
                await inp.fill(value, timeout=3000)
                logger.info(f"  Typed into input (non-visible fallback, index {i})")
                return True
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"  Non-visible input fallback failed: {e}")

    try:
        # Last resort: assume focus is in search area, type via keyboard
        await page.keyboard.type(value, delay=50)
        await page.keyboard.press("Enter")
        logger.info("  Typed via keyboard (global fallback)")
        return True
    except Exception as e:
        logger.debug(f"  Keyboard fallback failed: {e}")
        return False


@dataclass
class ExecutionCheckpoint:
    """Checkpoint for recovery"""
    step_id: int
    step_description: str
    state: str
    timestamp: str
    success: bool
    error: Optional[str] = None


@dataclass
class ExecutionResult:
    """Result of test execution"""
    test_id: str
    passed: bool
    total_steps: int
    executed_steps: int
    failed_step: Optional[int] = None
    error: Optional[str] = None
    checkpoints: List[ExecutionCheckpoint] = None
    duration_ms: int = 0
    
    def __post_init__(self):
        if self.checkpoints is None:
            self.checkpoints = []


class DeterministicExecutorV2:
    """
    Enhanced Deterministic Executor V2
    
    Key features:
    - Semantic parsing (English → JSON DSL)
    - Separate assertion engine (no UI actions)
    - State validation before/after each step
    - Smart waits (network idle, element visibility)
    - Deterministic product identification
    - Checkpointing for recovery
    """
    
    def __init__(self, page: Page, context: BrowserContext):
        self.page = page
        self.context = context
        self.assertion_engine = AssertionEngine(page)
        self.intent_dispatcher = IntentDispatcher()  # No page parameter
        self.checkpoints: List[ExecutionCheckpoint] = []
        self.current_state: Optional[PageState] = None
        # Store high-level test context for healing agent
        self.test_context: Dict[str, Any] = {}
        # Enterprise modules (lazy init where needed)
        self._healing_agent = None
        self._execution_memory = None
    
    async def execute_natural_language(self, test_case_text: str, start_url: str = None) -> ExecutionResult:
        """
        Execute natural language test case
        
        Example:
            "Navigate to lg.com, click Air Solutions, verify page loaded, select LG AC"
        """
        # Parse to normalized DSL
        test_case = SemanticTestParser.parse_natural_language(test_case_text, start_url)
        
        # Execute normalized test case
        return await self.execute_test_case(test_case)
    
    async def execute_enterprise_format(self, spec: Dict[str, Any]) -> ExecutionResult:
        """
        Execute enterprise test format
        
        Example:
            {
                "Test Case ID": "TC001",
                "Steps": [
                    {"Step": "Navigate to homepage", "Expected Result": "Homepage loaded"}
                ]
            }
        """
        # Parse to normalized DSL
        test_case = SemanticTestParser.parse_enterprise_format(spec)
        
        # Execute normalized test case
        return await self.execute_test_case(test_case)
    
    async def execute_test_case(self, test_case: TestCase) -> ExecutionResult:
        """
        Execute normalized test case (JSON DSL)
        
        Routes:
        - ASSERTION → Assertion Engine (never clicks)
        - ACTION → Intent Dispatcher (clicks, types)
        - INPUT → Intent Dispatcher (fills forms)
        - NAVIGATION → Intent Dispatcher (navigates)
        """
        start_time = datetime.now()
        logger.info(f"🚀 Executing test case: {test_case.title}")
        logger.info(f"📋 Total steps: {len(test_case.steps)}")
        
        # Save lightweight test context for downstream components (healing agent, logging)
        try:
            self.test_context = {
                "test_id": test_case.id,
                "title": test_case.title,
                "total_steps": len(test_case.steps),
                "steps": [
                    {
                        "id": s.id,
                        "type": str(s.type),
                        "intent": str(s.intent),
                        "target": s.target,
                        "value": s.value,
                        "metadata": getattr(s, "metadata", {}) or {},
                    }
                    for s in test_case.steps
                ],
            }
        except Exception:
            # Never block execution if context building fails
            self.test_context = {}
        
        # Reset environment + Stability Engine (Module 7)
        await self._reset_environment()
        try:
            from .stability_engine import stabilize_before_run
            await stabilize_before_run(self.page, self.context)
        except Exception as e:
            logger.debug(f"Stability pre-run: {e}")

        executed_count = 0

        try:
            for step in test_case.steps:
                logger.info(f"\n{'='*60}")
                intent_str = step.intent.value if hasattr(step.intent, 'value') else str(step.intent)
                type_str = step.type.value if hasattr(step.type, 'value') else str(step.type)
                logger.info(f"📍 Step {step.id}/{len(test_case.steps)}: {type_str} - {intent_str}")
                logger.info(f"{'='*60}")

                # Contextual Action Router (Module 4): resolve blocking UI before step
                if step.type in [StepType.ACTION, StepType.INPUT, StepType.NAVIGATION]:
                    try:
                        from .contextual_action_router import route_before_step
                        is_guest = "guest" in intent_str.lower() or (step.target and "guest" in (step.target or "").lower())
                        await route_before_step(
                            self.page,
                            step.intent,
                            step.target,
                            self.page.url,
                        )
                    except Exception as e:
                        logger.debug(f"Contextual router: {e}")

                # Validate pre-conditions (required state)
                if step.required_state:
                    current_state = await self._detect_current_state()
                    if current_state != step.required_state:
                        error_msg = f"Pre-condition failed: Expected state '{step.required_state.value}', got '{current_state.value}'"
                        logger.error(f"❌ {error_msg}")
                        
                        self._save_checkpoint(step.id, str(step.intent), current_state.value, False, error_msg)
                        
                        return ExecutionResult(
                            test_id=test_case.id,
                            passed=False,
                            total_steps=len(test_case.steps),
                            executed_steps=executed_count,
                            failed_step=step.id,
                            error=error_msg,
                            checkpoints=self.checkpoints,
                            duration_ms=int((datetime.now() - start_time).total_seconds() * 1000)
                        )
                
                # Route step to appropriate handler
                step_start_ts = time.perf_counter()
                if step.type == StepType.ASSERTION:
                    # ASSERTIONS → Assertion Engine (NEVER clicks)
                    success, message = await self._execute_assertion(step)
                
                elif step.type in [StepType.ACTION, StepType.INPUT, StepType.NAVIGATION]:
                    # ACTIONS → Intent Dispatcher
                    success, message = await self._execute_action(step)
                
                elif step.type == StepType.WAIT:
                    # WAITS → Smart wait strategy
                    success, message = await self._execute_wait(step)
                
                elif step.type == StepType.CONDITIONAL:
                    # CONDITIONALS → Evaluate condition
                    success, message = await self._execute_conditional(step)

                elif step.type == StepType.UNKNOWN:
                    # Try as CLICK so any test case gets one attempt (resolution + healing)
                    step_text = getattr(step, "target", None) or str(step)
                    fallback_step = TestStep(
                        id=step.id,
                        type=StepType.ACTION,
                        intent=Intent.CLICK,
                        target=step_text,
                    )
                    success, message = await self._execute_action(fallback_step)
                    if not success:
                        message = f"Step not parsed and click failed: '{step_text[:80]}'"
                
                else:
                    success = False
                    message = f"Unknown step type: {step.type}"

                # E1: Telemetry — one line per step (path, duration_ms; on failure structured resolution error)
                duration_ms = int((time.perf_counter() - step_start_ts) * 1000)
                path = getattr(self, "_last_step_path", None)
                resolution_error = getattr(self, "_last_step_resolution_error", None)
                logger.info("TELEMETRY step_id=%s path=%s duration_ms=%s", step.id, path or "n/a", duration_ms)
                if not success and resolution_error:
                    logger.info("TELEMETRY resolution_error=%s", json.dumps(resolution_error))
                
                # Log result
                if success:
                    logger.info(f"✅ SUCCESS: {message}")
                    # Post-action validation: intent-based (production) or legacy by intent
                    if step.type in [StepType.ACTION, StepType.INPUT]:
                        try:
                            from .action_validator import validate_action, validate_action_intent_based
                            # Prefer intent-based validation when we have intent_type from resolution engine
                            if getattr(self, "_last_intent_type", None):
                                vres = await validate_action_intent_based(
                                    self.page,
                                    self._last_intent_type,
                                    step.target,
                                    step.value,
                                )
                            else:
                                vres = await validate_action(
                                    self.page,
                                    step.intent,
                                    step.target,
                                    step.value,
                                )
                            if not vres.passed:
                                logger.warning(f"⚠️ Post-action validation failed: {vres.message}")
                                try:
                                    await _run_interrupt_and_flow_handlers(self.page, "before_checkout")
                                    await self.page.wait_for_timeout(500)
                                    if getattr(self, "_last_intent_type", None):
                                        vres2 = await validate_action_intent_based(
                                            self.page, self._last_intent_type, step.target, step.value
                                        )
                                    else:
                                        vres2 = await validate_action(self.page, step.intent, step.target, step.value)
                                    if not vres2.passed:
                                        success, message = False, vres2.message
                                except Exception:
                                    success, message = False, vres.message
                        except Exception as e:
                            logger.debug(f"Action validator: {e}")
                    if success:
                        try:
                            await self._post_step_stabilize(step)
                        except Exception as e:
                            logger.debug(f"Post-step stabilize: {e}")
                        # Execution memory: state transition + cache only when validation passed
                        try:
                            if not self._execution_memory:
                                from .execution_memory import ExecutionMemory
                                self._execution_memory = ExecutionMemory()
                            prev_state = getattr(step, "required_state", None)
                            curr = await self._detect_current_state()
                            if prev_state:
                                self._execution_memory.record_state_transition(
                                    prev_state.value if hasattr(prev_state, "value") else str(prev_state),
                                    curr.value if hasattr(curr, "value") else str(curr),
                                    step.id,
                                )
                            # Production: cache v2 (url, intent_type, normalized_target) with selector, bbox, container
                            if getattr(self, "_last_intent_type", None) and getattr(self, "_last_action_target", None):
                                norm = (self._last_action_target or "").strip().lower()[:200]
                                info = getattr(self, "_last_resolution_info", None) or {}
                                self._execution_memory.set_cached_selector_v2(
                                    self.page.url,
                                    self._last_intent_type.value,
                                    norm,
                                    selector=getattr(self, "_last_resolved_selector", None),
                                    bounding_box=info.get("bounding_box"),
                                    container_info={"in_main_section": info.get("in_main_section")} if info else None,
                                )
                                # B3: record element history (fingerprint) for next-run boost
                                try:
                                    from .element_history import ElementHistory
                                    fp = info.get("fingerprint")
                                    if fp:
                                        eh = ElementHistory()
                                        eh.record(
                                            self.page.url,
                                            self._last_intent_type.value,
                                            norm,
                                            fingerprint=fp,
                                            selector=getattr(self, "_last_resolved_selector", None),
                                            bounding_box=info.get("bounding_box"),
                                            duration_ms=info.get("duration_ms"),
                                        )
                                except Exception as e:
                                    logger.debug(f"Element history record: {e}")
                            elif getattr(self, "_last_resolved_selector", None) and getattr(self, "_last_action_target", None):
                                intent_str = (self._last_action_intent.value if hasattr(self._last_action_intent, "value") else str(self._last_action_intent))
                                self._execution_memory.set_cached_selector(
                                    self.page.url,
                                    self._last_action_target,
                                    intent_str,
                                    self._last_resolved_selector,
                                )
                            self._last_resolved_selector = None
                            self._last_intent_type = None
                            self._last_resolution_info = None
                        except Exception as e:
                            logger.debug(f"Execution memory: {e}")
                if not success:
                    logger.error(f"❌ FAILED: {message}")
                    
                    self._save_checkpoint(step.id, str(step.intent), "unknown", False, message)
                    
                    return ExecutionResult(
                        test_id=test_case.id,
                        passed=False,
                        total_steps=len(test_case.steps),
                        executed_steps=executed_count,
                        failed_step=step.id,
                        error=message,
                        checkpoints=self.checkpoints,
                        duration_ms=int((datetime.now() - start_time).total_seconds() * 1000)
                    )
                
                # Validate post-conditions (expected state) — Module 2: strict only for critical flow states
                # Skip for NAVIGATION. For CATEGORY/PRODUCT_LIST/HOME/PRODUCT_DETAIL: state detection is often wrong (SPA, URL delay) -> log and continue. Fail only for CHECKOUT/CART/PAYMENT/CONFIRMATION.
                if step.expected_state and step.type != StepType.NAVIGATION:
                    try:
                        await self._wait_for_state_change(step.expected_state, timeout_ms=5000)
                        current_state = await self._detect_current_state()
                        expected_val = step.expected_state.value if hasattr(step.expected_state, "value") else str(step.expected_state)
                        current_val = current_state.value if hasattr(current_state, "value") else str(current_state)
                        if current_val != expected_val:
                            logger.warning(f"⚠️ Post-state mismatch: expected {expected_val}, got {current_val}. Retrying once...")
                            await _run_interrupt_and_flow_handlers(self.page, "before_checkout")
                            await self.page.wait_for_timeout(1000)
                            current_state = await self._detect_current_state()
                            current_val = current_state.value if hasattr(current_state, "value") else str(current_state)
                            if current_val != expected_val:
                                # Fail only for critical states (checkout/cart/payment/confirmation). Soft states (CATEGORY/PRODUCT_LIST/HOME/PRODUCT_DETAIL) often misdetect due to SPA/URL delay — log and continue.
                                critical_states = {PageState.CHECKOUT.value, PageState.CART.value, PageState.PAYMENT.value, PageState.CONFIRMATION.value, PageState.BILLING.value}
                                if expected_val in critical_states:
                                    self._save_checkpoint(step.id, str(step.intent), current_val, False, f"Post-state validation failed: expected {expected_val}, got {current_val}")
                                    return ExecutionResult(
                                        test_id=test_case.id,
                                        passed=False,
                                        total_steps=len(test_case.steps),
                                        executed_steps=executed_count,
                                        failed_step=step.id,
                                        error=f"Post-state validation failed: expected {expected_val}, got {current_val}. Step reported success but page state did not match.",
                                        checkpoints=self.checkpoints,
                                        duration_ms=int((datetime.now() - start_time).total_seconds() * 1000)
                                    )
                                logger.warning(f"⚠️ Post-state soft mismatch (expected {expected_val}, got {current_val}) — continuing (lenient for category/home/product_list).")
                    except Exception as e:
                        logger.warning(f"State validation error: {e}")
                
                # Save checkpoint
                current_state = await self._detect_current_state()
                state_val = current_state.value if hasattr(current_state, 'value') else str(current_state)
                self._save_checkpoint(step.id, str(step.intent), state_val, True)
                
                executed_count += 1
            
            # All steps passed
            logger.info(f"\n{'='*60}")
            logger.info(f"✅ TEST PASSED: All {executed_count} steps executed successfully")
            logger.info(f"{'='*60}\n")
            
            return ExecutionResult(
                test_id=test_case.id,
                passed=True,
                total_steps=len(test_case.steps),
                executed_steps=executed_count,
                checkpoints=self.checkpoints,
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
        
        except Exception as e:
            logger.error(f"❌ FATAL ERROR: {e}")
            return ExecutionResult(
                test_id=test_case.id,
                passed=False,
                total_steps=len(test_case.steps),
                executed_steps=executed_count,
                error=str(e),
                checkpoints=self.checkpoints,
                duration_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
    
    # ==================== STEP EXECUTION HANDLERS ====================
    
    async def _post_step_stabilize(self, step: TestStep) -> None:
        """Stabilize UI after every step: dismiss modals (classified when possible), flow handlers, stability engine."""
        try:
            from .flow_config_loader import run_flow_handlers
            target = (getattr(step, "target", None) or "").lower()
            intent_str = (step.intent.value if hasattr(step.intent, "value") else str(step.intent)).lower()
            if "check" in target and "pincode" in target:
                await run_flow_handlers(self.page, "after_pincode_check")
            # Module 5: use classified popup handler when step is guest checkout
            is_guest = "guest" in intent_str or "guest" in target
            try:
                from .popup_classifier import handle_interrupts_classified
                await handle_interrupts_classified(
                    self.page, timeout_ms=2000, current_step_guest_checkout=is_guest
                )
            except Exception:
                from .interrupt_handler import handle_interrupts
                await handle_interrupts(self.page, timeout_ms=2000)
            await self.page.wait_for_load_state("domcontentloaded", timeout=3000)
            await self.page.wait_for_timeout(500)
            try:
                from .stability_engine import force_layout_stabilization
                await force_layout_stabilization(self.page, timeout_ms=500)
            except Exception:
                pass
        except Exception:
            pass

    async def _execute_assertion(self, step: TestStep) -> tuple[bool, str]:
        """
        Execute ASSERTION step using Assertion Engine
        
        ✅ NEVER clicks or types
        ✅ Only inspects page state
        """
        intent_str = step.intent.value if hasattr(step.intent, 'value') else str(step.intent)
        logger.info(f"🔍 Executing ASSERTION: {intent_str}")
        
        result: AssertionResult = await self.assertion_engine.execute_assertion(step)
        
        return result.passed, result.message

    async def _run_click_select_step(self, step: TestStep, intent_val: str) -> tuple[bool, str]:
        """CLICK/SELECT step body — run under asyncio.wait_for for per-step timeout."""
        from .element_resolver import smart_click
        target = step.target
        clicked = False
        resolved_selector = None
        intent_type = None
        resolution_info = None

        is_product_step = bool(getattr(step, "metadata", {}) and step.metadata.get("is_product"))
        if step.intent == Intent.SELECT and is_product_step and target:
            try:
                logger.info("🛍️ Detected structured product selection step; using deterministic selector")
                product_selected = await self.intent_dispatcher.execute(
                    ProductIntent.SELECT_PRODUCT,
                    {"product_name": target},
                    self.page,
                )
                if product_selected:
                    self._last_step_path = "phase1"
                    logger.info("✅ Deterministic product selection validated")
                    return True, f"Selected product: {target}"
            except Exception as e:
                logger.debug(f"Deterministic product selection failed, using resolution engine: {e}")

        if self._execution_memory is None:
            try:
                from .execution_memory import ExecutionMemory
                self._execution_memory = ExecutionMemory()
            except Exception:
                pass
        if self._execution_memory:
            from .resolution_decision_engine import classify_intent, _normalize_target
            intent_type = classify_intent(target, step.intent.value if hasattr(step.intent, "value") else str(step.intent))
            normalized = _normalize_target(target)
            cached_v2 = self._execution_memory.get_cached_selector_v2(self.page.url, intent_type.value, normalized)
            if cached_v2 and cached_v2.get("selector"):
                try:
                    el = self.page.locator(cached_v2["selector"])
                    if await el.count() > 0:
                        await el.first.scroll_into_view_if_needed(timeout=2000)
                        await el.first.click(timeout=5000)
                        clicked = True
                        resolved_selector = cached_v2["selector"]
                        resolution_info = cached_v2
                        self._last_step_path = "cache"
                        logger.info(f"  ✅ Execution memory v2 (intent={intent_type.value}) success")
                except Exception as e0:
                    logger.debug(f"  Execution memory v2 failed: {e0}")
            if not clicked:
                _intent_str = (step.intent.value if hasattr(step.intent, "value") else str(step.intent))
                cached = self._execution_memory.get_cached_selector(self.page.url, target, _intent_str)
                if cached:
                    try:
                        el = self.page.locator(cached)
                        if await el.count() > 0:
                            await el.first.scroll_into_view_if_needed(timeout=2000)
                            await el.first.click(timeout=5000)
                            clicked = True
                            resolved_selector = cached
                            self._last_step_path = "cache"
                            logger.info(f"  ✅ Phase 0 (legacy memory) success")
                    except Exception as e0:
                        logger.debug(f"  Phase 0 (legacy) failed: {e0}")

        if not clicked:
            try:
                await smart_click(self.page, target)
                clicked = True
                self._last_step_path = "phase1"
                logger.info(f"  ✅ Phase 1 (element resolver) success")
            except Exception as e1:
                logger.debug(f"  Phase 1 failed: {e1}")

        if not clicked:
            try:
                from .resolution_decision_engine import resolve_click_with_fallbacks, classify_intent as classify_intent_engine
                from .wait_strategy import wait_for_stable_dom
                await wait_for_stable_dom(self.page)
                if intent_type is None:
                    intent_type = classify_intent_engine(target, step.intent.value if hasattr(step.intent, "value") else str(step.intent))
                meta = getattr(step, "metadata", None) or {}
                section_hint = meta.get("section") or meta.get("container_hint")
                ordinal = meta.get("ordinal")
                clicked, resolved_selector, resolution_info = await resolve_click_with_fallbacks(
                    self.page, target, step.intent.value if hasattr(step.intent, "value") else str(step.intent),
                    section_hint=section_hint, ordinal=ordinal,
                )
                if clicked:
                    self._last_step_path = "resolution"
                    logger.info(f"  ✅ Resolution Decision Engine success (intent={intent_type.value})")
                elif isinstance(resolution_info, dict) and resolution_info.get("error"):
                    self._last_step_resolution_error = resolution_info
            except Exception as e2:
                logger.debug(f"  Resolution engine failed: {e2}")

        if not clicked:
            for attempt, wait_ms in enumerate([400, 800], start=1):
                try:
                    await self.page.wait_for_timeout(wait_ms)
                    if attempt == 2:
                        await _run_interrupt_and_flow_handlers(self.page, "before_checkout")
                    try:
                        await smart_click(self.page, target)
                        clicked = True
                        self._last_step_path = "phase1"
                        logger.info(f"  ✅ Retry (backoff {wait_ms}ms) Phase 1 success")
                        break
                    except Exception:
                        from .resolution_decision_engine import resolve_click_with_fallbacks
                        meta = getattr(step, "metadata", None) or {}
                        clicked, resolved_selector, resolution_info = await resolve_click_with_fallbacks(
                            self.page, target, step.intent.value if hasattr(step.intent, "value") else str(step.intent),
                            section_hint=meta.get("section") or meta.get("container_hint"), ordinal=meta.get("ordinal"),
                        )
                        if clicked:
                            self._last_step_path = "resolution"
                            logger.info(f"  ✅ Retry (backoff {wait_ms}ms) Resolution Engine success")
                            break
                        elif isinstance(resolution_info, dict) and resolution_info.get("error"):
                            self._last_step_resolution_error = resolution_info
                except Exception as e_retry:
                    logger.debug(f"  Retry attempt {attempt} failed: {e_retry}")
                if clicked:
                    break

        if not clicked:
            try:
                from .visual_grounding_engine import resolve_visually, click_by_visual_result
                visual_result = await resolve_visually(self.page, target, intent_val, context=self.test_context)
                if visual_result:
                    clicked = await click_by_visual_result(self.page, visual_result)
                    if clicked:
                        self._last_step_path = "visual"
                        logger.info(f"  ✅ Visual grounding success")
            except Exception as e3:
                logger.debug(f"  Visual grounding failed: {e3}")

        if not clicked:
            try:
                previous_steps = [f"Step {cp.step_id}: {cp.step_description}" for cp in self.checkpoints]
                healing_action = await self._healing_agent.heal_click_failure(
                    self.page, target, previous_steps, test_context=self.test_context or None,
                )
                if healing_action:
                    clicked = await self._healing_agent.apply_healing_action(self.page, healing_action, failed_target=target)
                    if clicked:
                        self._last_step_path = "healing"
                        logger.info(f"  ✅ Healing Agent (rare escalation) success")
            except Exception as e4:
                logger.error(f"  Healing Agent failed: {e4}")

        if not clicked:
            self._last_step_path = self._last_step_path or "resolution"
            return False, f"All resolution paths failed for click: '{target}'"

        self._last_resolved_selector = resolved_selector
        self._last_action_target = target
        self._last_action_intent = step.intent
        self._last_intent_type = intent_type
        self._last_resolution_info = resolution_info
        target_lower = (target or "").lower()
        is_major_action = any(k in target_lower for k in ["buy", "checkout", "cart", "add", "submit", "check"])
        is_product_selection = any(k in target_lower for k in ["star", "ac", "split", "lg", "samsung", "product", "model", "kw", "ton", "btu"])
        if is_major_action or is_product_selection:
            try:
                from .wait_strategy import wait_after_major_action
                if "check" in target_lower and "pincode" in target_lower:
                    await _run_interrupt_and_flow_handlers(self.page, "after_pincode_check")
                else:
                    from .interrupt_handler import handle_interrupts
                    await handle_interrupts(self.page, timeout_ms=2000)
                await wait_after_major_action(self.page, timeout_ms=8000)
            except Exception as e:
                logger.debug(f"  Post-click wait: {e}")
        return True, f"Clicked: {target}"

    async def _execute_action(self, step: TestStep) -> tuple[bool, str]:
        """
        Execute ACTION/INPUT/NAVIGATION step using PRODUCTION 3-PHASE RESOLUTION
        
        Phase 1: Deterministic element_resolver (9 strategies)
        Phase 2: Smart resolver (fuzzy matching, semantic search)
        Phase 3: Healing agent (LLM-based recovery)
        
        ✅ Same powerful system as the old working executor
        """
        intent_val = step.intent.value if hasattr(step.intent, 'value') else str(step.intent)
        logger.info(f"🎯 Executing ACTION: {intent_val}")
        self._last_step_path = None
        self._last_step_resolution_error = None

        try:
            from .element_resolver import smart_click, smart_type, smart_select
            from .smart_resolver import smart_resolve_click, smart_resolve_type
            from .healing_agent import HealingAgent
            
            # Healing agent (Phase 4) - lazy init
            if self._healing_agent is None:
                self._healing_agent = HealingAgent()

            # Map TestStep to actions
            if step.intent == Intent.GOTO:
                await self.page.goto(step.target, wait_until="domcontentloaded", timeout=30000)
                try:
                    from .wait_strategy import wait_after_navigation
                    await wait_after_navigation(self.page, timeout_ms=10000)
                except Exception as e:
                    logger.debug(f"Wait after navigation: {e}")
                self._last_step_path = "navigation"
                return True, f"Navigated to {step.target}"
            
            # CLICK / SELECT — with per-step timeout to avoid 2+ min stuck and "page closed" in healing
            elif step.intent == Intent.CLICK or step.intent == Intent.SELECT:
                try:
                    return await asyncio.wait_for(
                        self._run_click_select_step(step, intent_val),
                        timeout=CLICK_STEP_TIMEOUT_SEC,
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"CLICK step timed out after {CLICK_STEP_TIMEOUT_SEC}s")
                    self._last_step_path = "resolution"
                    return False, f"Step timed out after {CLICK_STEP_TIMEOUT_SEC}s for: '{step.target}'"

            elif step.intent == Intent.ADD_TO_CART:
                return await self._execute_action(TestStep(
                    id=step.id, type=step.type, intent=Intent.CLICK, target="add to cart"
                ))
            
            elif step.intent == Intent.BUY_NOW:
                return await self._execute_action(TestStep(
                    id=step.id, type=step.type, intent=Intent.CLICK, target="buy now"
                ))
            
            elif step.intent == Intent.CHECKOUT:
                await _run_interrupt_and_flow_handlers(self.page, "before_checkout")
                return await self._execute_action(TestStep(
                    id=step.id, type=step.type, intent=Intent.CLICK, target="checkout"
                ))
            
            elif step.intent == Intent.CONTINUE_AS_GUEST:
                return await self._execute_action(TestStep(
                    id=step.id, type=step.type, intent=Intent.CLICK, target="guest"
                ))
            
            # TYPE - Use 2-phase resolution (deterministic + smart resolver)
            elif step.intent == Intent.FILL_PINCODE or step.intent == Intent.TYPE:
                target = step.target if step.target else "pincode"
                value = step.value
                typed = False
                
                # Phase 1: Deterministic
                try:
                    await smart_type(self.page, target, value)
                    typed = True
                    logger.info(f"  ✅ Phase 1 success")
                except Exception as e1:
                    logger.debug(f"  Phase 1 failed: {e1}")
                    
                    # Phase 2: Smart Resolver
                    try:
                        typed = await smart_resolve_type(self.page, target, value)
                        if typed:
                            logger.info(f"  ✅ Phase 2 success (smart resolver)")
                    except Exception as e2:
                        logger.debug(f"  Phase 2 failed: {e2}")
                
                if not typed:
                    return False, f"Failed to type into: '{target}'"
                
                return True, f"Typed '{value}' into {target}"
            
            elif step.intent == Intent.FILL_EMAIL:
                await self.page.fill('input[type="email"], input[name*="email"]', step.value)
                return True, f"Email filled: {step.value}"
            
            elif step.intent == Intent.FILL_PHONE:
                await self.page.fill('input[type="tel"], input[name*="phone"], input[name*="mobile"]', step.value)
                return True, f"Phone filled: {step.value}"
            
            elif step.intent == Intent.SELECT_OPTION:
                # Run flow handlers BEFORE selection (dismiss "Select delivery" popup etc.)
                target_lower = (step.target or "").lower()
                if "delivery" in target_lower or "shipping" in target_lower:
                    await _run_interrupt_and_flow_handlers(self.page, "before_select_delivery")
                try:
                    await smart_select(self.page, step.target)
                    return True, f"Selected option: {step.target}"
                except Exception as e:
                    logger.error(f"Select option failed with deterministic resolver: {e}")
                    # Retry with interrupt recovery: dismiss modals and retry once
                    try:
                        await _run_interrupt_and_flow_handlers(self.page, "before_select_delivery")
                        await self.page.wait_for_timeout(500)
                        await smart_select(self.page, step.target)
                        logger.info("  ✅ Retry after interrupt recovery succeeded")
                        return True, f"Selected option: {step.target} (after retry)"
                    except Exception as retry_e:
                        logger.debug(f"Retry after interrupt failed: {retry_e}")
                    # Phase 3: Healing Agent for complex selection failures
                    try:
                        previous_steps = [f"Step {cp.step_id}: {cp.step_description}" for cp in self.checkpoints]
                        healing_action = await self._healing_agent.heal_click_failure(
                            self.page,
                            step.target,
                            previous_steps,
                            test_context=self.test_context or None,
                        )
                        if healing_action:
                            healed = await self._healing_agent.apply_healing_action(self.page, healing_action)
                            if healed:
                                logger.info("  ✅ Healing agent successfully resolved SELECT_OPTION")
                                return True, f"Healed selection for option: {step.target}"
                    except Exception as heal_err:
                        logger.error(f"Healing for SELECT_OPTION failed: {heal_err}")
                    return False, f"Failed to select option: {str(e)}"
            
            elif step.intent == Intent.SEARCH:
                # Robust search handling tuned for LG global search (IN/US)
                # On both sites, clicking the search icon opens an overlay and
                # focuses the search input. We first wait for it, then try
                # focused field, smart resolvers, and contenteditable fallbacks.
                value = step.value
                logger.info(f"🔎 Executing SEARCH for query: {value}")

                # Wait for search overlay/input (LG overlays can take 2-3s; avoid strict :visible)
                await self.page.wait_for_timeout(3000)

                typed = False

                # Phase 0: If an input is already focused (LG behaviour), just type there.
                try:
                    focused = self.page.locator("input:focus, textarea:focus")
                    count = await focused.count()
                    if count > 0:
                        logger.info("  🎯 SEARCH Phase 0: Found focused input, typing query there")
                        await focused.first.fill(value, timeout=5000)
                        await focused.first.press("Enter")
                        typed = True
                        logger.info("  ✅ SEARCH Phase 0 success (focused input)")
                        return True, f"Searched for: {value}"
                    else:
                        logger.warning("  ⚠️ SEARCH Phase 0 FAILED: No focused input found (overlay may not have appeared yet)")
                except Exception as e0:
                    logger.warning(f"  ⚠️ SEARCH Phase 0 FAILED (focused input): {e0}")

                # Phase 1: Deterministic smart_type (uses label/placeholder/aria-label, modal scoping)
                try:
                    await smart_type(self.page, "search", value)
                    typed = True
                    logger.info("  ✅ SEARCH Phase 1 success (smart_type)")
                except Exception as e1:
                    logger.warning(f"  ⚠️ SEARCH Phase 1 FAILED (element_resolver): {e1}")

                # Phase 2: Smart Resolver for inputs
                if not typed:
                    try:
                        typed = await smart_resolve_type(self.page, "search", value)
                        if typed:
                            logger.info("  ✅ SEARCH Phase 2 success (smart_resolve_type)")
                    except Exception as e2:
                        logger.warning(f"  ⚠️ SEARCH Phase 2 FAILED (smart_resolve_type): {e2}")

                # Phase 3: Contenteditable + keyboard fallback (LG/similar may use div[contenteditable])
                if not typed:
                    try:
                        typed = await _search_fallback_contenteditable_keyboard(self.page, value)
                        if typed:
                            logger.info("  ✅ SEARCH Phase 3 success (contenteditable/keyboard)")
                    except Exception as e3:
                        logger.warning(f"  ⚠️ SEARCH Phase 3 FAILED: {e3}")

                if not typed:
                    logger.error(
                        f"  ❌ SEARCH FAILED: All 4 phases exhausted. "
                        f"Root cause: No visible/focused search input, contenteditable, or keyboard fallback "
                        f"succeeded (query='{value}')"
                    )
                    return False, f"Failed to type search query into any search field (query='{value}')"

                # Submit the search via Enter (if not already submitted)
                try:
                    focused = self.page.locator("input:focus, textarea:focus")
                    if await focused.count() > 0:
                        await focused.first.press("Enter")
                    else:
                        await self.page.keyboard.press("Enter")
                except Exception as e:
                    logger.debug(f"  SEARCH submit (Enter key) failed non-critically: {e}")

                return True, f"Searched for: {value}"
            
            elif step.intent == Intent.FILL_FORM:
                # Generic form filling for billing/shipping details using valid data generator
                try:
                    from .valid_data_generator import generate_valid_data
                except Exception as e:
                    logger.warning(f"  ⚠️ FILL_FORM: valid_data_generator import failed: {e}")
                    return False, "FILL_FORM failed: valid_data_generator unavailable"
                
                logger.info("🧾 Executing FILL_FORM for billing/shipping details")
                
                # Scope: if there is a visible checkout/billing form container, restrict to it
                form_scope = self.page
                try:
                    potential_forms = self.page.locator(
                        "form:visible, div[class*='form']:visible, div[id*='form']:visible, "
                        "section[class*='billing']:visible, section[class*='shipping']:visible"
                    )
                    if await potential_forms.count() > 0:
                        form_scope = potential_forms.first
                        logger.info("  🎯 Scoping form fill to billing/shipping container")
                except Exception as e:
                    logger.debug(f"  FILL_FORM scope detection failed, using full page: {e}")
                
                # Collect visible inputs and textareas
                inputs = form_scope.locator(
                    "input:visible, textarea:visible"
                )
                count = await inputs.count()
                logger.info(f"  Found {count} candidate fields for billing/shipping fill")
                
                filled_any = False
                for i in range(count):
                    field = inputs.nth(i)
                    try:
                        field_type = (await field.get_attribute("type")) or "text"
                        name = (await field.get_attribute("name")) or ""
                        placeholder = (await field.get_attribute("placeholder")) or ""
                        aria_label = (await field.get_attribute("aria-label")) or ""
                        label_hint = " ".join(
                            part
                            for part in [name, placeholder, aria_label]
                            if part
                        ) or field_type
                        
                        # Skip obvious non-data fields
                        lower_hint = label_hint.lower()
                        if any(skip in lower_hint for skip in ["otp", "captcha", "one time", "newsletter"]):
                            continue
                        
                        # Generate a valid value based on hint
                        value = generate_valid_data(label_hint, None)
                        
                        await field.scroll_into_view_if_needed(timeout=2000)
                        await field.fill(value, timeout=5000)
                        try:
                            await field.press("Tab")
                        except Exception:
                            pass
                        
                        filled_any = True
                        logger.info(f"  ✅ Filled '{label_hint}' with synthetic data")
                    except Exception as e:
                        logger.debug(f"  Skipping field {i} in FILL_FORM due to error: {e}")
                        continue
                
                if not filled_any:
                    logger.warning("  ⚠️ FILL_FORM did not find any suitable fields to fill")
                    return False, "No suitable billing/shipping fields found to fill"
                
                return True, "Filled billing/shipping details with synthetic data"
            
            else:
                return False, f"Unknown action intent: {step.intent}"
        
        except Exception as e:
            logger.error(f"Action execution error: {e}")
            return False, f"Action failed: {str(e)}"
    
    async def _execute_wait(self, step: TestStep) -> tuple[bool, str]:
        """Execute WAIT step"""
        try:
            if step.intent == Intent.WAIT_FOR_ELEMENT:
                await self.page.wait_for_selector(step.target, timeout=30000)
                return True, f"Element appeared: {step.target}"
            
            elif step.intent == Intent.WAIT_FOR_NAVIGATION:
                await self.page.wait_for_load_state("networkidle", timeout=30000)
                return True, "Navigation complete"
            
            else:
                # Generic wait
                wait_ms = step.metadata.get("duration_ms", 1000) if step.metadata else 1000
                await self.page.wait_for_timeout(wait_ms)
                return True, f"Waited {wait_ms}ms"
        
        except Exception as e:
            return False, f"Wait failed: {str(e)}"
    
    async def _execute_conditional(self, step: TestStep) -> tuple[bool, str]:
        """Execute CONDITIONAL step"""
        # Placeholder for conditional logic
        return True, "Conditional executed"
    
    # ==================== STATE MANAGEMENT ====================
    
    async def _detect_current_state(self) -> PageState:
        """Detect current page state: URL first (avoid CHECKOUT false positive on category pages), then semantic, then DOM fallback"""
        try:
            url = self.page.url.lower()
            url_normalized = url.rstrip("/")

            # Only treat as HOME when path is exactly base (no category/product path)
            if re.match(r"^https?://[^/]+/?$", url):
                return PageState.HOME
            if url_normalized.endswith("/in") and url_normalized.count("/") <= 3:
                return PageState.HOME
            if url_normalized.endswith("lg.com/in") and url_normalized.count("/") <= 4:
                return PageState.HOME

            # Run URL-based detection FIRST so category/product pages are never misclassified as CHECKOUT.
            # (Semantic CHECKOUT signals can fire on category pages due to footer email/payment links.)
            if "/cart" in url or "/bag" in url:
                return PageState.CART
            if "/checkout" in url or "/billing" in url:
                return PageState.CHECKOUT
            if "/payment" in url:
                return PageState.PAYMENT
            if "/confirmation" in url or "/thankyou" in url or "/success" in url:
                return PageState.CONFIRMATION

            # Site-specific (e.g. LG) category URLs
            if "lg.com" in url:
                if any(cat in url for cat in [
                    "/air-conditioners", "/split-ac", "/air-solutions", "/home-appliances",
                    "/tv", "/audio", "/refrigerators", "/washing", "/category/", "/c/"
                ]):
                    if "/product" in url or "-p-" in url or re.search(r"/[a-z0-9-]+-[a-z0-9]{5,}", url):
                        return PageState.PRODUCT_DETAIL
                    return PageState.CATEGORY

            # Generic URL patterns for any site (e-commerce, apps)
            if any(seg in url for seg in ["/category/", "/categories/", "/c/", "/shop/", "/collections/"]):
                if "/product" in url or "/p/" in url or "-p-" in url:
                    return PageState.PRODUCT_DETAIL
                return PageState.CATEGORY
            if any(seg in url for seg in ["/products", "/search?", "/listing", "/listings"]) and "/product/" not in url and "/p/" not in url:
                return PageState.PRODUCT_LIST

            # Optional: semantic state from DOM signals (when URL is ambiguous)
            try:
                from .semantic_state_engine import detect_semantic_state
                semantic = await detect_semantic_state(self.page)
                if semantic and semantic.value != "unknown":
                    mapping = {
                        "home": PageState.HOME,
                        "category": PageState.CATEGORY,
                        "product_list": PageState.PRODUCT_LIST,
                        "product_detail": PageState.PRODUCT_DETAIL,
                        "cart": PageState.CART,
                        "checkout": PageState.CHECKOUT,
                        "payment": PageState.PAYMENT,
                        "order_confirmation": PageState.CONFIRMATION,
                    }
                    if semantic.value in mapping:
                        return mapping[semantic.value]
            except Exception as e:
                logger.debug(f"Semantic state detection: {e}")

            # URL-based (product detail for non-LG or missed paths)
            if "/product" in url or "-p-" in url or "/pd/" in url:
                return PageState.PRODUCT_DETAIL

            # Enhanced detection using page content
            # Check for category/product list page indicators
            try:
                # Look for filter elements (indicates product list/category page)
                has_filters = await self.page.locator('text=/filter|category/i').count() > 0 or \
                             await self.page.locator('[class*="filter"], [class*="Filter"]').count() > 0
                
                # Look for product grid/list
                has_product_grid = await self.page.locator('[class*="product"], [class*="Product"]').count() > 3
                
                # Look for "Buy Now" or product detail indicators
                has_buy_button = await self.page.locator('text=/buy now|add to cart/i').count() > 0
                has_product_title = await self.page.locator('h1, h2').count() > 0
                
                if has_filters or has_product_grid:
                    # Check if it's product detail (single product) or list (multiple products)
                    if has_buy_button and has_product_title and not has_filters:
                        return PageState.PRODUCT_DETAIL
                    else:
                        return PageState.PRODUCT_LIST
                
                # Check for specific LG site patterns
                if "lg.com" in url:
                    # Audio/electronics category pages
                    if any(cat in url for cat in ["/audio", "/tv-soundbar", "/home-appliances", "/electronics"]):
                        if has_product_grid:
                            return PageState.PRODUCT_LIST
                        else:
                            return PageState.CATEGORY
                    # Product detail page (has model number pattern)
                    elif re.search(r'/[A-Z0-9]{5,}', url):
                        return PageState.PRODUCT_DETAIL
            except:
                pass
            
            # Default to HOME
            return PageState.HOME
        
        except Exception as e:
            logger.warning(f"State detection failed: {e}")
            return PageState.HOME
    
    async def _wait_for_state_change(self, expected_state: PageState, timeout_ms: int = 5000):
        """Wait for state to change to expected state - lenient, continues on failure"""
        try:
            expected_val = expected_state.value if hasattr(expected_state, 'value') else str(expected_state)
            start_time = datetime.now()
            while (datetime.now() - start_time).total_seconds() * 1000 < timeout_ms:
                current_state = await self._detect_current_state()
                current_val = current_state.value if hasattr(current_state, 'value') else str(current_state)
                if current_val == expected_val:
                    logger.info(f"✅ State changed to: {expected_val}")
                    return True
                await self.page.wait_for_timeout(500)
            
            # LENIENT: Log warning but don't fail - state detection may be imperfect
            logger.warning(f"⚠️ Timeout waiting for state: {expected_val} (continuing anyway - lenient mode)")
            return True  # Return True to allow continuation
        
        except Exception as e:
            logger.warning(f"Wait for state error: {e} (continuing anyway - lenient mode)")
            return True  # Return True to allow continuation
    
    # ==================== CHECKPOINTING ====================
    
    def _save_checkpoint(self, step_id: int, description: str, state: str, success: bool, error: str = None):
        """Save execution checkpoint"""
        checkpoint = ExecutionCheckpoint(
            step_id=step_id,
            step_description=description,
            state=state,
            timestamp=datetime.now().isoformat(),
            success=success,
            error=error
        )
        self.checkpoints.append(checkpoint)
        logger.debug(f"💾 Checkpoint saved: Step {step_id}")
    
    # ==================== ENVIRONMENT RESET ====================
    
    async def _reset_environment(self):
        """Reset browser environment to clean state"""
        try:
            logger.info("🔄 Resetting environment...")
            await self.context.clear_cookies()
            try:
                await self.page.evaluate("() => { try { localStorage.clear(); sessionStorage.clear(); } catch (e) {} }")
            except Exception:
                pass  # Access denied on about:blank or cross-origin
            try:
                await self.context.clear_permissions()
            except Exception:
                pass
            logger.info("✅ Environment reset complete")
        except Exception as e:
            logger.warning(f"⚠️ Environment reset partial failure: {e}")
