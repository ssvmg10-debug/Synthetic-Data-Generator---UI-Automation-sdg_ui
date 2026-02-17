"""
Production-Grade Enterprise UI Automation Engine - STATE-DRIVEN ARCHITECTURE

NEW ARCHITECTURE (v5 - State-Driven):
┌────────────────────┐
│   Planner (LLM)    │  ← Converts user intent to structured plan
└─────────┬──────────┘
          ↓
┌────────────────────────────────────────────────┐
│         LAYER 1: Page Intelligence             │
│   (DOM fingerprinting, page type detection)    │
└─────────┬──────────────────────────────────────┘
          ↓
┌────────────────────────────────────────────────┐
│         LAYER 2: Intent Normalization          │
│   (English → Structured Intent)                │
└─────────┬──────────────────────────────────────┘
          ↓
┌────────────────────────────────────────────────┐
│         LAYER 3: Context-Aware Execution       │
│   (Scoped resolution, product matching)        │
└─────────┬──────────────────────────────────────┘
          ↓
┌────────────────────────────────────────────────┐
│         LAYER 4: State Validation              │
│   (Validate transitions after every action)    │
└────────────────────────────────────────────────┘

EXECUTION MODES:
- INSTRUCTION (legacy): Direct text-based matching
- STATE_DRIVEN (v5): Full context-aware execution

KEY IMPROVEMENTS:
✅ Understands page context (HOME, LISTING, DETAIL, CART, CHECKOUT)
✅ Normalizes intents (buy product → scoped action)
✅ Product similarity matching (handles fuzzy names)
✅ Scoped element resolution (searches within containers)
✅ State validation after every step

TARGET: 90-95% success rate on "ANY test case"
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import logging
from pathlib import Path

# Phase 1 Core - ONLY imports we need
from services.ui_automation.instruction_compiler import InstructionCompiler, Instruction, ActionType
from services.ui_automation.core.executor import execute_instructions

# State-Driven Architecture (v5) imports
from services.ui_automation.core.page_intelligence import PageIntelligenceEngine, PageType
from services.ui_automation.core.intent_normalizer import IntentNormalizer, ActionIntent
from services.ui_automation.core.context_executor import ContextAwareExecutor
from services.ui_automation.core.state_validator import StateValidator, create_validation_rules_for_action

# Hybrid Architecture (v6) imports
from services.ui_automation.hybrid import (
    HybridExecutor, 
    HybridExecutionResult, 
    InstructionContext,
    PageStateExtractor
)

logger = logging.getLogger(__name__)


@dataclass
class EnterpriseFlowResult:
    """Production-grade result with all required fields."""
    success: bool
    goal_reached: bool
    steps_executed: int
    screenshots: List[str] = field(default_factory=list)
    error: Optional[str] = None
    execution_time: float = 0.0
    
    # Router-expected fields (never remove)
    healing_attempts: int = 0
    instructions_compiled: int = 0
    failed_at: Optional[int] = None
    instruction_mode: bool = True  # Always True for Phase 1 deterministic execution
    health_score: float = 0.0  # Calculated from success metrics
    
    # Phase 2+ metrics
    smart_resolver_attempts: int = 0
    step_timings: List[float] = field(default_factory=list)
    failure_reason: Optional[str] = None


class EnterpriseFlowEngine:
    """
    Hybrid Execution Engine (v6) - OpenClaw + Enterprise
    
    Three execution modes:
    - INSTRUCTION (legacy): Direct instruction-based (Phase 1-3)
    - STATE_DRIVEN (v5): Full context-aware execution
    - HYBRID (v6): 4-phase adaptive execution:
        ► Phase 1: Deterministic (fast, CI-friendly)
        ► Phase 2: Smart Resolver (mathematical scoring)
        ► Phase 3: Autonomous Loop (goal-driven reasoning)
        ► Phase 4: LLM Healing (last resort)
    
    HYBRID Target: 95%+ success rate, adaptive to ANY scenario
    """
    
    def __init__(
        self, 
        mode: str = "HYBRID",  # Changed default to HYBRID
        raw_input: str = None,
        structured_plan: Dict = None,
        headless: bool = False,
        run_id: Optional[str] = None
    ):
        self.mode = mode.upper()
        self.structured_plan = structured_plan
        self.headless = headless
        self.run_id = run_id or f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        # Phase 1: ONLY instruction compiler (for INSTRUCTION mode)
        self.instruction_compiler = InstructionCompiler()
        self.instructions = None
        
        # State-Driven v5 components
        self.intent_normalizer = IntentNormalizer() if mode == "STATE_DRIVEN" else None
        
        # Output paths (for failure screenshots only)
        self.output_dir = Path("backend/test_outputs") / self.run_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🚀 Engine initialized: {self.run_id}")
        logger.info(f"   Mode: {self.mode}")
        if self.mode == "STATE_DRIVEN":
            logger.info(f"   ✨ Using state-driven architecture with context awareness")
        elif self.mode == "HYBRID":
            logger.info(f"   🔥 Using HYBRID architecture (4-phase adaptive execution)")
    
    # Phase 1: Element interaction handled by core/element_resolver.py
    # No complex methods here - keep engine minimal

    
    async def run(self, url: str) -> EnterpriseFlowResult:
        """
        Main execution entry point with MODE SWITCHING.
        
        Three completely separate pipelines:
        - INSTRUCTION: plan → compile → execute (legacy, Phase 1-3)
        - STATE_DRIVEN: plan → normalize → context-aware execute (v5)
        - HYBRID: plan → compile → 4-phase hybrid execute (v6)
        
        HYBRID pipeline combines deterministic stability with autonomous adaptability.
        """
        start_time = datetime.utcnow()
        
        if self.mode == "HYBRID":
            logger.info("🔥 Using HYBRID execution (v6 - 4-Phase Adaptive)")
            return await self._execute_hybrid(url, start_time)
        
        elif self.mode == "STATE_DRIVEN":
            logger.info("✨ Using STATE-DRIVEN execution (v5 - Context-Aware)")
            return await self._execute_state_driven(url, start_time)
        
        elif self.mode == "INSTRUCTION":
            logger.info("📝 Compiling instructions from structured plan (INSTRUCTION mode)")
            
            # Compile instructions from plan (1:1 mapping, no interpretation)
            self.instructions = self.instruction_compiler.compile_from_plan(self.structured_plan)
            
            # Validation guard: prevent step collapsing
            plan_steps = self.structured_plan.get("steps", [])
            executable_steps = [s for s in plan_steps if s.get("action") not in ("navigate", "goto")]
            
            if len(self.instructions) < len(executable_steps) - 1:
                error_msg = f"⚠️ Instruction collapse detected! Plan had {len(executable_steps)} steps, compiled to {len(self.instructions)} instructions"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            logger.info(f"Compiled {len(self.instructions)} instructions:")
            for i, instr in enumerate(self.instructions, 1):
                logger.info(f"{i}. {instr}")
            
            return await self._execute_instructions(url, start_time)
        
        else:
            raise ValueError(f"Unknown mode: {self.mode}. Use 'INSTRUCTION', 'STATE_DRIVEN', or 'HYBRID'")
    
    async def _execute_instructions(self, url: str, start_time: datetime) -> EnterpriseFlowResult:
        """
        Production-grade execution with proper browser lifecycle and metrics.
        
        Phase integration:
        - Delegates to core executor (handles Phase 1-3)
        - Captures all metrics
        - Screenshot only on failure
        - Proper cleanup
        """
        async with async_playwright() as p:
            # Proper browser lifecycle
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800}
            )
            page = await context.new_page()
            
            try:
                # Execute using production executor (Phase 1-3 integrated)
                result_dict = await execute_instructions(page, self.instructions)
                
                # Screenshot only on failure
                screenshot_path = None
                if not result_dict["success"]:
                    screenshot_path = await self._take_failure_screenshot(page)
                
                # Calculate health score (0-100): success rate + phase efficiency
                steps_executed = result_dict["steps_executed"]
                total_steps = len(self.instructions)
                base_score = (steps_executed / total_steps * 100) if total_steps > 0 else 0
                
                # Penalty for using fallback phases
                healing_penalty = result_dict.get("healing_attempts", 0) * 5
                smart_penalty = result_dict.get("smart_resolver_attempts", 0) * 2
                health_score = max(0, base_score - healing_penalty - smart_penalty)
                
                # Build result with all metrics
                result = EnterpriseFlowResult(
                    success=result_dict["success"],
                    goal_reached=result_dict["success"],
                    steps_executed=steps_executed,
                    screenshots=[screenshot_path] if screenshot_path else [],
                    error=result_dict.get("error"),
                    instructions_compiled=len(self.instructions),
                    failed_at=result_dict.get("failed_at"),
                    execution_time=(datetime.utcnow() - start_time).total_seconds(),
                    healing_attempts=result_dict.get("healing_attempts", 0),
                    smart_resolver_attempts=result_dict.get("smart_resolver_attempts", 0),
                    step_timings=result_dict.get("step_timings", []),
                    failure_reason=result_dict.get("failure_reason"),
                    health_score=health_score
                )
                
                # Log final metrics
                logger.info(f"\n{'='*80}")
                logger.info(f"📊 EXECUTION METRICS:")
                logger.info(f"   Success: {result.success}")
                logger.info(f"   Steps: {result.steps_executed}/{len(self.instructions)}")
                logger.info(f"   Time: {result.execution_time:.2f}s")
                logger.info(f"   Healing attempts: {result.healing_attempts}")
                logger.info(f"   Smart resolver uses: {result.smart_resolver_attempts}")
                if result.step_timings:
                    avg_time = sum(result.step_timings) / len(result.step_timings)
                    logger.info(f"   Avg step time: {avg_time:.2f}s")
                logger.info(f"{'='*80}\n")
                
                # Proper cleanup
                await context.close()
                await browser.close()
                
                return result
                
            except Exception as e:
                logger.error(f"❌ Fatal error: {e}", exc_info=True)
                
                # Take failure screenshot
                screenshot_path = await self._take_failure_screenshot(page)
                
                result = EnterpriseFlowResult(
                    success=False,
                    goal_reached=False,
                    steps_executed=0,
                    screenshots=[screenshot_path] if screenshot_path else [],
                    error=str(e),
                    instructions_compiled=len(self.instructions),
                    execution_time=(datetime.utcnow() - start_time).total_seconds(),
                    failure_reason=f"Fatal error: {str(e)}",
                    health_score=0.0
                )
                
                await context.close()
                await browser.close()
                return result
    
    async def _execute_state_driven(self, url: str, start_time: datetime) -> EnterpriseFlowResult:
        """
        State-Driven Execution (v5) - Context-aware execution with full understanding.
        
        Flow:
        1. Navigate to URL
        2. For each step:
           a. Detect page type (LAYER 1: Page Intelligence)
           b. Normalize intent (LAYER 2: Intent Normalization)
           c. Execute with context (LAYER 3: Context-Aware Execution)
           d. Validate state (LAYER 4: State Validation)
        3. Return enriched metrics
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800}
            )
            page = await context.new_page()
            
            try:
                # Initialize state-driven components
                context_executor = ContextAwareExecutor(page)
                state_validator = StateValidator(page)
                
                # Navigate to starting URL
                logger.info(f"🌐 Navigating to: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)  # Let page settle
                
                # Get steps from plan
                steps = self.structured_plan.get("steps", [])
                total_steps = len(steps)
                steps_executed = 0
                validation_failures = 0
                
                logger.info(f"\n{'='*80}")
                logger.info(f"🚀 STARTING STATE-DRIVEN EXECUTION: {total_steps} steps")
                logger.info(f"{'='*80}\n")
                
                for idx, step in enumerate(steps, 1):
                    logger.info(f"\n[{idx}/{total_steps}] Processing: {step.get('action', 'unknown')}")
                    
                    # Skip navigation step (already done)
                    if step.get("ui_intent") in ["navigate", "goto"]:
                        logger.info("  ⏭️ Skipping navigate (already at URL)")
                        steps_executed += 1
                        continue
                    
                    step_start = datetime.utcnow()
                    
                    # LAYER 2: Normalize intent
                    intent = self.intent_normalizer.normalize(
                        step.get("action", ""),
                        step
                    )
                    logger.info(f"  🧠 Intent: {intent}")
                    
                    # Capture pre-action state snapshot
                    pre_snapshot = await state_validator.capture_state_snapshot()
                    
                    # LAYER 3: Execute with full context awareness
                    result = await context_executor.execute_intent(
                        intent,
                        validate_transition=False  # We'll validate separately
                    )
                    
                    step_time = (datetime.utcnow() - step_start).total_seconds()
                    
                    if result["success"]:
                        logger.info(f"  ✅ Success ({step_time:.2f}s)")
                        steps_executed += 1
                        
                        # LAYER 4: Validate state transition
                        validation_rules = create_validation_rules_for_action(intent.action.value)
                        validation_passed = await state_validator.validate(
                            validation_rules,
                            pre_snapshot
                        )
                        
                        if not validation_passed:
                            logger.warning(f"  ⚠️ State validation failed (but action succeeded)")
                            validation_failures += 1
                    else:
                        logger.error(f"  ❌ Failed: {result.get('message')}")
                        # Take failure screenshot
                        screenshot_path = await self._take_failure_screenshot(page)
                        
                        # Decide whether to continue or stop
                        # For now, stop on first failure
                        logger.info(f"\n{'='*80}")
                        logger.info(f"❌ EXECUTION STOPPED: Step {idx} failed")
                        logger.info(f"{'='*80}\n")
                        
                        result = EnterpriseFlowResult(
                            success=False,
                            goal_reached=False,
                            steps_executed=steps_executed,
                            screenshots=[screenshot_path] if screenshot_path else [],
                            error=result.get("message"),
                            instructions_compiled=total_steps,
                            failed_at=idx,
                            execution_time=(datetime.utcnow() - start_time).total_seconds(),
                            failure_reason=f"Step {idx} failed: {result.get('message')}",
                            health_score=0.0
                        )
                        
                        await context.close()
                        await browser.close()
                        return result
                
                # All steps completed successfully
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                
                # Calculate health score
                success_rate = (steps_executed / total_steps * 100) if total_steps > 0 else 0
                validation_penalty = validation_failures * 5
                health_score = max(0, success_rate - validation_penalty)
                
                result = EnterpriseFlowResult(
                    success=True,
                    goal_reached=True,
                    steps_executed=steps_executed,
                    screenshots=[],
                    instructions_compiled=total_steps,
                    execution_time=execution_time,
                    healing_attempts=0,  # Not used in state-driven mode
                    smart_resolver_attempts=0,  # Built into context executor
                    health_score=health_score
                )
                
                # Log final metrics
                logger.info(f"\n{'='*80}")
                logger.info(f"📊 STATE-DRIVEN EXECUTION COMPLETE:")
                logger.info(f"   Success: {result.success}")
                logger.info(f"   Steps: {result.steps_executed}/{total_steps}")
                logger.info(f"   Time: {result.execution_time:.2f}s")
                logger.info(f"   Validation failures: {validation_failures}")
                logger.info(f"   Health score: {result.health_score:.1f}/100")
                logger.info(f"{'='*80}\n")
                
                await context.close()
                await browser.close()
                
                return result
                
            except Exception as e:
                logger.error(f"❌ Fatal error in state-driven execution: {e}", exc_info=True)
                
                screenshot_path = await self._take_failure_screenshot(page)
                
                result = EnterpriseFlowResult(
                    success=False,
                    goal_reached=False,
                    steps_executed=0,
                    screenshots=[screenshot_path] if screenshot_path else [],
                    error=str(e),
                    instructions_compiled=len(self.structured_plan.get("steps", [])),
                    execution_time=(datetime.utcnow() - start_time).total_seconds(),
                    failure_reason=f"Fatal error: {str(e)}",
                    health_score=0.0
                )
                
                await context.close()
                await browser.close()
                return result
    
    async def _execute_hybrid(self, url: str, start_time: datetime) -> EnterpriseFlowResult:
        """
        HYBRID execution (v6) - 4-phase adaptive pipeline.
        
        Combines:
        - Phase 1: Deterministic (fast, stable)
        - Phase 2: Smart Resolver (mathematical)
        - Phase 3: Autonomous Loop (goal-driven)
        - Phase 4: LLM Healing (last resort)
        
        Each instruction tries phases in order until success.
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800}
            )
            page = await context.new_page()
            
            try:
                # Initialize hybrid executor
                hybrid_executor = HybridExecutor(
                    page,
                    enable_screenshots=False  # Only screenshot on failure
                )
                
                # Navigate to starting URL
                logger.info(f"🌐 Navigating to: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)
                
                # Compile instructions from plan
                self.instructions = self.instruction_compiler.compile_from_plan(self.structured_plan)
                logger.info(f"📝 Compiled {len(self.instructions)} instructions")
                
                # Convert to instruction contexts
                instruction_dicts = []
                for i, instr in enumerate(self.instructions):
                    instruction_dicts.append({
                        'action': instr.action.value,
                        'target': instr.target,
                        'value': instr.value,
                        'text': str(instr)
                    })
                
                # Execute with hybrid executor
                hybrid_result = await hybrid_executor.execute_instructions(instruction_dicts)
                
                # Take screenshot on failure
                screenshot_path = None
                if not hybrid_result.success:
                    screenshot_path = await self._take_failure_screenshot(page)
                
                # Calculate health score
                success_rate = (hybrid_result.steps_completed / hybrid_result.steps_total * 100) \
                               if hybrid_result.steps_total > 0 else 0
                
                # Build result
                result = EnterpriseFlowResult(
                    success=hybrid_result.success,
                    goal_reached=hybrid_result.success,
                    steps_executed=hybrid_result.steps_completed,
                    screenshots=[screenshot_path] if screenshot_path else [],
                    instructions_compiled=hybrid_result.steps_total,
                    execution_time=hybrid_result.execution_time,
                    healing_attempts=hybrid_result.phase_breakdown.get('phase4_llm_healing', 0),
                    smart_resolver_attempts=hybrid_result.phase_breakdown.get('phase2_smart_resolver', 0),
                    failed_at=None if hybrid_result.success else hybrid_result.steps_completed + 1,
                    error=hybrid_result.error_message,
                    failure_reason=hybrid_result.error_message,
                    health_score=success_rate
                )
                
                # Log stats
                stats = hybrid_executor.get_stats()
                logger.info(f"\n{'='*80}")
                logger.info(f"📊 HYBRID EXECUTION COMPLETE:")
                logger.info(f"   Success: {result.success}")
                logger.info(f"   Steps: {result.steps_executed}/{hybrid_result.steps_total}")
                logger.info(f"   Time: {result.execution_time:.2f}s")
                logger.info(f"   Health score: {result.health_score:.1f}/100")
                logger.info(f"\n   Phase Breakdown:")
                for phase, count in hybrid_result.phase_breakdown.items():
                    if count > 0:
                        percentage = (count / hybrid_result.steps_completed * 100) if hybrid_result.steps_completed > 0 else 0
                        logger.info(f"      {phase}: {count} steps ({percentage:.1f}%)")
                logger.info(f"{'='*80}\n")
                
                await context.close()
                await browser.close()
                
                return result
                
            except Exception as e:
                logger.error(f"❌ Fatal error in hybrid execution: {e}", exc_info=True)
                
                screenshot_path = await self._take_failure_screenshot(page)
                
                result = EnterpriseFlowResult(
                    success=False,
                    goal_reached=False,
                    steps_executed=0,
                    screenshots=[screenshot_path] if screenshot_path else [],
                    error=str(e),
                    instructions_compiled=len(self.instructions) if self.instructions else 0,
                    execution_time=(datetime.utcnow() - start_time).total_seconds(),
                    failure_reason=f"Fatal error: {str(e)}",
                    health_score=0.0
                )
                
                await context.close()
                await browser.close()
                return result
    
    async def _take_failure_screenshot(self, page: Page) -> Optional[str]:
        """Phase 1: Only take screenshot on failure (not every step)."""
        try:
            if page.is_closed():
                return None
            
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"failure_{timestamp}.png"
            filepath = self.output_dir / filename
            
            await page.screenshot(path=str(filepath), full_page=True, timeout=10000)
            logger.info(f"📸 Failure screenshot: {filename}")
            return str(filepath)
            
        except Exception as e:
            logger.warning(f"Failed to take screenshot: {e}")
            return None
