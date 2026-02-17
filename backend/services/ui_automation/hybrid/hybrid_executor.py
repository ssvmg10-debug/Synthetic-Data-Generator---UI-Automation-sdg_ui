"""
Hybrid Executor - 4-phase execution orchestrator.

Combines:
- Phase 1: Deterministic (your current strength)
- Phase 2: Smart Resolver (mathematical scoring)
- Phase 3: Autonomous Loop (goal-driven reasoning)
- Phase 4: LLM Healing (last resort)

This is the core that unifies Enterprise stability with OpenClaw adaptability.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from playwright.async_api import Page
import logging
import asyncio

from .page_state_extractor import PageStateExtractor, PageState
from .smart_element_scorer import SmartElementScorer
from .goal_validator import GoalValidator, Goal
from .autonomous_loop import AutonomousLoop

# Import Phase 1 components (existing deterministic execution)
from ..core.executor import execute_instructions
from ..core.element_resolver import smart_click, smart_type
from ..core.navigator import safe_navigate

logger = logging.getLogger(__name__)


@dataclass
class InstructionContext:
    """Context for executing an instruction."""
    action: str
    target: str
    value: Optional[str]
    instruction_text: str
    step_number: int


@dataclass
class HybridExecutionResult:
    """Result of hybrid execution."""
    success: bool
    phase_used: str  # "deterministic", "smart_resolver", "autonomous", "llm_healing"
    steps_completed: int
    steps_total: int
    execution_time: float
    phase_breakdown: Dict[str, int]  # Count of steps per phase
    validation_results: List[any]
    error_message: Optional[str] = None


class HybridExecutor:
    """
    4-Phase Hybrid Execution Engine.
    
    Architecture:
        Phase 1: Deterministic → Fast, predictable (existing system)
        Phase 2: Smart Resolver → Mathematical scoring (new)
        Phase 3: Autonomous Loop → Goal-driven reasoning (new)
        Phase 4: LLM Healing → AI-based recovery (existing fallback)
    
    Each phase is tried in order until success or all phases exhausted.
    """
    
    def __init__(self, page: Page, enable_screenshots: bool = False):
        self.page = page
        self.enable_screenshots = enable_screenshots
        self.state_extractor = PageStateExtractor(page)
        self.goal_validator = GoalValidator()
        
        # Phase counters
        self.phase_stats = {
            'phase1_deterministic': 0,
            'phase2_smart_resolver': 0,
            'phase3_autonomous': 0,
            'phase4_llm_healing': 0,
        }
        
    async def execute_instruction_hybrid(
        self,
        instruction: InstructionContext,
        before_state: Optional[PageState] = None
    ) -> Tuple[bool, str, Optional[PageState]]:
        """
        Execute a single instruction using 4-phase hybrid approach.
        
        Args:
            instruction: The instruction to execute
            before_state: Page state before execution (for validation)
            
        Returns:
            (success, phase_used, after_state)
        """
        logger.info("\n" + "=" * 80)
        logger.info(f"🚀 HYBRID EXECUTION: {instruction.instruction_text}")
        logger.info("=" * 80)
        
        # Capture before state if not provided
        if before_state is None:
            before_state = await self.state_extractor.extract_state()
        
        # Create goal for validation
        goal = self.goal_validator.create_goal_for_action(
            instruction.action,
            instruction.target,
            instruction.value
        )
        
        # Try Phase 1: Deterministic
        logger.info("\n🟢 PHASE 1: Deterministic Execution")
        success, phase = await self._phase1_deterministic(instruction)
        
        if success:
            after_state = await self.state_extractor.extract_state()
            validation = await self.goal_validator.validate(goal, before_state, after_state)
            
            if validation.success:
                self.phase_stats['phase1_deterministic'] += 1
                logger.info("✅ Phase 1 succeeded with goal validation")
                return True, 'phase1_deterministic', after_state
            else:
                logger.warning(f"⚠️ Phase 1 executed but goal not achieved: {validation.message}")
                # Continue to Phase 2
        
        # Try Phase 2: Smart Resolver
        logger.info("\n🟡 PHASE 2: Smart Resolver (Mathematical Scoring)")
        success, phase = await self._phase2_smart_resolver(instruction, before_state)
        
        if success:
            after_state = await self.state_extractor.extract_state()
            validation = await self.goal_validator.validate(goal, before_state, after_state)
            
            if validation.success:
                self.phase_stats['phase2_smart_resolver'] += 1
                logger.info("✅ Phase 2 succeeded with goal validation")
                return True, 'phase2_smart_resolver', after_state
            else:
                logger.warning(f"⚠️ Phase 2 executed but goal not achieved: {validation.message}")
        
        # Try Phase 3: Autonomous Loop
        logger.info("\n🔵 PHASE 3: Autonomous Loop (Goal-Driven Reasoning)")
        success, phase = await self._phase3_autonomous(instruction, goal, before_state)
        
        if success:
            after_state = await self.state_extractor.extract_state()
            self.phase_stats['phase3_autonomous'] += 1
            logger.info("✅ Phase 3 succeeded")
            return True, 'phase3_autonomous', after_state
        
        # Try Phase 4: LLM Healing (if available)
        logger.info("\n🔴 PHASE 4: LLM Healing (Last Resort)")
        success, phase = await self._phase4_llm_healing(instruction, before_state)
        
        if success:
            after_state = await self.state_extractor.extract_state()
            self.phase_stats['phase4_llm_healing'] += 1
            logger.info("✅ Phase 4 succeeded")
            return True, 'phase4_llm_healing', after_state
        
        # All phases failed
        logger.error("❌ All 4 phases exhausted - instruction failed")
        after_state = await self.state_extractor.extract_state()
        return False, 'all_failed', after_state
    
    async def _phase1_deterministic(self, instruction: InstructionContext) -> Tuple[bool, str]:
        """
        Phase 1: Use existing deterministic execution.
        
        This is your current system - fast, predictable, CI-friendly.
        """
        try:
            action = instruction.action.upper()
            
            if action == 'GOTO':
                result = await safe_navigate(self.page, instruction.target)
                return result, 'phase1'
            
            elif action == 'CLICK':
                result = await smart_click(self.page, instruction.target)
                return result, 'phase1'
            
            elif action == 'TYPE':
                result = await smart_type(self.page, instruction.target, instruction.value or '')
                return result, 'phase1'
            
            elif action == 'WAIT':
                await asyncio.sleep(2)
                return True, 'phase1'
            
            else:
                logger.warning(f"Unknown action: {action}")
                return False, 'phase1'
                
        except Exception as e:
            logger.warning(f"Phase 1 failed: {e}")
            return False, 'phase1'
    
    async def _phase2_smart_resolver(
        self,
        instruction: InstructionContext,
        page_state: PageState
    ) -> Tuple[bool, str]:
        """
        Phase 2: Use smart element scoring instead of blind strategies.
        
        Mathematical approach - no hardcoded strategy loops.
        """
        try:
            scorer = SmartElementScorer(page_state)
            action = instruction.action.upper()
            
            if action == 'CLICK':
                # Score all clickable elements
                best_element = scorer.find_best_match_for_click(instruction.target)
                
                if not best_element:
                    logger.warning("Phase 2: No good match found")
                    return False, 'phase2'
                
                # Execute click
                elem_locator = self.page.locator(best_element.selector).first
                await elem_locator.wait_for(state='visible', timeout=5000)
                await elem_locator.scroll_into_view_if_needed()
                await elem_locator.click(timeout=5000)
                
                logger.info(f"✅ Phase 2 clicked: {best_element.text[:50]}")
                return True, 'phase2'
            
            elif action == 'TYPE':
                # Score all input elements
                best_element = scorer.find_best_match_for_type(instruction.target, instruction.value or '')
                
                if not best_element:
                    logger.warning("Phase 2: No good input match found")
                    return False, 'phase2'
                
                # Execute type
                elem_locator = self.page.locator(best_element.selector).first
                await elem_locator.wait_for(state='visible', timeout=5000)
                await elem_locator.fill('')
                await elem_locator.fill(instruction.value or '')
                
                logger.info(f"✅ Phase 2 typed into: {best_element.attributes.get('name', best_element.tag)}")
                return True, 'phase2'
            
            else:
                # Not applicable for other actions
                return False, 'phase2'
                
        except Exception as e:
            logger.warning(f"Phase 2 failed: {e}")
            return False, 'phase2'
    
    async def _phase3_autonomous(
        self,
        instruction: InstructionContext,
        goal: Goal,
        page_state: PageState
    ) -> Tuple[bool, str]:
        """
        Phase 3: Autonomous goal-driven reasoning.
        
        This is the OpenClaw-style approach - stop following instructions,
        start reasoning about goals.
        """
        try:
            autonomous = AutonomousLoop(self.page, max_attempts=5)
            
            context = {
                'action': instruction.action,
                'target': instruction.target,
                'value': instruction.value,
            }
            
            result = await autonomous.achieve_goal(goal, context)
            
            if result.success:
                logger.info(f"✅ Phase 3 achieved goal: {result.reasoning}")
                return True, 'phase3'
            else:
                logger.warning(f"⚠️ Phase 3 could not achieve goal: {result.reasoning}")
                return False, 'phase3'
                
        except Exception as e:
            logger.error(f"Phase 3 failed: {e}")
            return False, 'phase3'
    
    async def _phase4_llm_healing(
        self,
        instruction: InstructionContext,
        page_state: PageState
    ) -> Tuple[bool, str]:
        """
        Phase 4: LLM-based healing (last resort).
        
        Send page state to LLM and ask for suggestion.
        NOTE: This requires AZURE_OPENAI_KEY configured.
        """
        try:
            # Check if healing is available
            from ..core.healing_agent import HealingAgent
            
            # This would need to be initialized with LLM credentials
            # For now, return False as it's not configured in the logs
            logger.warning("Phase 4: LLM healing not configured (requires AZURE_OPENAI_KEY)")
            return False, 'phase4'
            
        except Exception as e:
            logger.warning(f"Phase 4 not available: {e}")
            return False, 'phase4'
    
    async def execute_instructions(
        self,
        instructions: List[Dict[str, any]]
    ) -> HybridExecutionResult:
        """
        Execute a full list of instructions using hybrid approach.
        
        Args:
            instructions: List of instruction dicts with action, target, value
            
        Returns:
            HybridExecutionResult with complete execution report
        """
        logger.info("\n" + "=" * 80)
        logger.info("🚀 HYBRID EXECUTOR: Starting execution")
        logger.info(f"   Total instructions: {len(instructions)}")
        logger.info("=" * 80)
        
        import time
        start_time = time.time()
        
        steps_completed = 0
        validation_results = []
        last_state = None
        
        for i, instr_dict in enumerate(instructions):
            step_num = i + 1
            
            # Parse instruction
            instruction = InstructionContext(
                action=instr_dict.get('action', ''),
                target=instr_dict.get('target', ''),
                value=instr_dict.get('value'),
                instruction_text=instr_dict.get('text', f"{instr_dict.get('action')}('{instr_dict.get('target')}')"
),
                step_number=step_num
            )
            
            # Execute with hybrid approach
            success, phase_used, after_state = await self.execute_instruction_hybrid(
                instruction,
                before_state=last_state
            )
            
            if success:
                steps_completed += 1
                last_state = after_state
                logger.info(f"✅ Step {step_num}/{len(instructions)} completed via {phase_used}")
            else:
                logger.error(f"❌ Step {step_num}/{len(instructions)} failed after all phases")
                # Stop execution on failure
                break
            
            # Small delay between steps
            await asyncio.sleep(0.5)
        
        execution_time = time.time() - start_time
        
        # Build result
        result = HybridExecutionResult(
            success=(steps_completed == len(instructions)),
            phase_used='hybrid',
            steps_completed=steps_completed,
            steps_total=len(instructions),
            execution_time=execution_time,
            phase_breakdown=self.phase_stats.copy(),
            validation_results=validation_results,
            error_message=None if steps_completed == len(instructions) else "Execution stopped due to failure"
        )
        
        # Log summary
        logger.info("\n" + "=" * 80)
        logger.info("📊 HYBRID EXECUTION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"   Success: {result.success}")
        logger.info(f"   Steps: {result.steps_completed}/{result.steps_total}")
        logger.info(f"   Time: {result.execution_time:.2f}s")
        logger.info(f"   Phase breakdown:")
        for phase, count in result.phase_breakdown.items():
            if count > 0:
                logger.info(f"      {phase}: {count} steps")
        logger.info("=" * 80)
        
        return result
    
    def get_stats(self) -> Dict[str, any]:
        """Get execution statistics."""
        total = sum(self.phase_stats.values())
        
        return {
            'total_steps': total,
            'phase_breakdown': self.phase_stats.copy(),
            'phase_percentages': {
                phase: (count / total * 100) if total > 0 else 0
                for phase, count in self.phase_stats.items()
            }
        }
