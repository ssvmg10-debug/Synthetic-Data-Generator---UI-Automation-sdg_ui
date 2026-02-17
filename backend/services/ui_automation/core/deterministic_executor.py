"""
🔒 DETERMINISTIC EXECUTOR
Combines all phases: State Machine + Intent Dispatch + Checkpointing + Validation
"""
import logging
from playwright.async_api import Page, BrowserContext
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
import re
from datetime import datetime

from .state_machine import AppState, detect_state, validate_state_transition, StateTransitionError
from .intent_dispatcher import Intent, IntentDispatcher

logger = logging.getLogger(__name__)


@dataclass
class IntentStep:
    """Structured intent step with parameters"""
    intent: Intent
    parameters: Dict[str, Any]
    description: str
    expected_state: Optional[str] = None
    
    def __repr__(self):
        params_str = ", ".join(f"{k}={v}" for k, v in self.parameters.items())
        return f"{self.intent.value}({params_str})"


class SimpleIntentPlanner:
    """Simple rule-based intent parser"""
    
    @staticmethod
    def parse_test_case(test_case: str) -> List[IntentStep]:
        """Parse test case into intent steps"""
        steps = []
        instructions = [s.strip() for s in test_case.replace(',', '\n').split('\n') if s.strip()]
        
        for instruction in instructions:
            step = SimpleIntentPlanner._parse_instruction(instruction)
            if step:
                steps.append(step)
        
        return steps
    
    @staticmethod
    def _parse_instruction(instruction: str) -> Optional[IntentStep]:
        """Parse single instruction"""
        inst_lower = instruction.lower().strip()
        
        # Navigate to URL
        if inst_lower.startswith("navigate to") or inst_lower.startswith("go to"):
            url = instruction.split(" to ", 1)[1].strip()
            return IntentStep(
                Intent.NAVIGATE_TO_URL,
                {"url": url},
                f"Navigate to {url}",
                "home"
            )
        
        # Category navigation
        if "air solutions" in inst_lower:
            return IntentStep(
                Intent.NAVIGATE_TO_CATEGORY,
                {"category": "Air Solutions"},
                "Navigate to Air Solutions",
                "category"
            )
        
        if "split ac" in inst_lower and ("click" in inst_lower or "select" in inst_lower):
            return IntentStep(
                Intent.NAVIGATE_TO_CATEGORY,
                {"category": "Split AC"},
                "Navigate to Split AC",
                "product_list"
            )
        
        # Product selection
        if ("select" in inst_lower or "choose" in inst_lower) and any(brand in inst_lower for brand in ["lg", "samsung", "product"]):
            for trigger in ["select ", "choose "]:
                if trigger in inst_lower:
                    product_name = instruction.split(trigger, 1)[1].strip()
                    return IntentStep(
                        Intent.SELECT_PRODUCT,
                        {"product_name": product_name},
                        f"Select product: {product_name}",
                        "product_detail"
                    )
        
        # Add to cart
        if "add to cart" in inst_lower or "buy" in inst_lower:
            return IntentStep(
                Intent.ADD_TO_CART,
                {},
                "Add product to cart",
                "cart"
            )
        
        # Pincode
        if "pincode" in inst_lower or "zip" in inst_lower:
            pincode_match = re.search(r'\b\d{5,6}\b', instruction)
            pincode = pincode_match.group() if pincode_match else "560001"
            return IntentStep(
                Intent.FILL_PINCODE,
                {"pincode": pincode},
                f"Fill pincode: {pincode}"
            )
        
        # Delivery
        if "delivery" in inst_lower and ("free" in inst_lower or "standard" in inst_lower or "select" in inst_lower):
            delivery_type = "free" if "free" in inst_lower else "standard"
            return IntentStep(
                Intent.SELECT_DELIVERY_OPTION,
                {"delivery_type": delivery_type},
                f"Select {delivery_type} delivery"
            )
        
        # Guest checkout
        if "guest" in inst_lower:
            return IntentStep(
                Intent.COMPLETE_CHECKOUT_AS_GUEST,
                {},
                "Continue as guest",
                "checkout"
            )
        
        # Checkout
        if "checkout" in inst_lower:
            return IntentStep(
                Intent.PROCEED_TO_CHECKOUT,
                {},
                "Proceed to checkout",
                "checkout"
            )
        
        # Generic click
        if "click" in inst_lower:
            element = instruction.split("click", 1)[1].strip()
            return IntentStep(
                Intent.CLICK_ELEMENT,
                {"element": element},
                f"Click: {element}"
            )
        
        # Fallback
        return IntentStep(
            Intent.CLICK_ELEMENT,
            {"element": instruction},
            f"Generic: {instruction}"
        )


class ExecutionCheckpoint:
    """
    🔒 PHASE 8 — EXECUTION CHECKPOINTING
    Store and resume from known-good states
    """
    
    def __init__(self):
        self.checkpoints: List[Dict[str, Any]] = []
        self.current_step = 0
    
    def add_checkpoint(self, step_index: int, state: AppState, url: str, description: str):
        """Add checkpoint after successful milestone"""
        checkpoint = {
            "step_index": step_index,
            "state": state.value,
            "url": url,
            "description": description,
            "timestamp": datetime.now().isoformat()
        }
        self.checkpoints.append(checkpoint)
        logger.info(f"✅ Checkpoint saved: {description} (state: {state.value})")
    
    def get_last_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Get last successful checkpoint"""
        return self.checkpoints[-1] if self.checkpoints else None
    
    def can_resume_from(self, step_index: int) -> bool:
        """Check if we can resume from a checkpoint"""
        return any(cp["step_index"] < step_index for cp in self.checkpoints)


class DeterministicExecutor:
    """
    🔒 PHASES 1-10 INTEGRATED
    
    Deterministic, state-validated, checkpointed execution
    """
    
    def __init__(self):
        self.dispatcher = IntentDispatcher()
        self.checkpoint_manager = ExecutionCheckpoint()
    
    async def execute_test_case(
        self,
        test_case: str,
        start_url: str,
        page: Page,
        context: BrowserContext,
        visible: bool = False
    ) -> Dict[str, Any]:
        """
        Execute test case with full deterministic architecture
        
        Returns:
            {
                "success": bool,
                "steps_completed": int,
                "total_steps": int,
                "checkpoints": int,
                "final_state": str,
                "error": Optional[str]
            }
        """
        logger.info(f"🚀 Starting deterministic execution")
        logger.info(f"📝 Test case: {test_case}")
        
        # 🔒 PHASE 9 — RESET ENVIRONMENT
        await self._reset_environment(context, page)
        
        # Parse test case into structured intents
        intent_steps = SimpleIntentPlanner.parse_test_case(test_case)
        
        logger.info(f"📋 Parsed {len(intent_steps)} intent steps:")
        for i, step in enumerate(intent_steps, 1):
            logger.info(f"  {i}. {step}")
        
        # Navigate to start URL
        logger.info(f"🌐 Navigating to: {start_url}")
        await page.goto(start_url if start_url.startswith("http") else f"https://{start_url}")
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
        await page.wait_for_load_state("networkidle", timeout=10000)
        
        # Detect initial state
        current_state = await detect_state(page)
        logger.info(f"🎯 Initial state: {current_state.value}")
        
        # Execute steps
        steps_completed = 0
        last_error = None
        
        for i, step in enumerate(intent_steps):
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"[{i+1}/{len(intent_steps)}] Executing: {step.description}")
                logger.info(f"{'='*60}")
                
                # Get state before step
                state_before = await detect_state(page)
                logger.info(f"State before: {state_before.value}")
                
                # Execute intent
                success = await self.dispatcher.execute(
                    step.intent,
                    step.parameters,
                    page
                )
                
                if not success:
                    raise Exception(f"Intent execution returned failure")
                
                # Wait for page to stabilize
                await page.wait_for_timeout(500)
                
                # 🔒 PHASE 1 — VALIDATE STATE TRANSITION
                if step.expected_state:
                    expected_state = AppState(step.expected_state)
                    await validate_state_transition(page, expected_state)
                    current_state = expected_state
                else:
                    # Detect new state
                    current_state = await detect_state(page)
                    logger.info(f"State after: {current_state.value}")
                
                steps_completed += 1
                
                # 🔒 PHASE 8 — ADD CHECKPOINT after major milestones
                if self._is_milestone_state(current_state):
                    self.checkpoint_manager.add_checkpoint(
                        i,
                        current_state,
                        page.url,
                        step.description
                    )
                
            except StateTransitionError as e:
                # 🔒 PHASE 10 — STRICT FAILURE POLICY
                logger.error(f"❌ State transition failed at step {i+1}")
                logger.error(f"   {e}")
                logger.error(f"   Stopping execution (no drifting allowed)")
                last_error = str(e)
                break
            
            except Exception as e:
                logger.error(f"❌ Step {i+1} failed: {e}")
                
                # 🔒 RETRY ONCE
                logger.warning(f"🔄 Retrying step {i+1}...")
                try:
                    await page.wait_for_timeout(1000)
                    success = await self.dispatcher.execute(
                        step.intent,
                        step.parameters,
                        page
                    )
                    
                    if success:
                        steps_completed += 1
                        logger.info(f"✅ Step {i+1} succeeded on retry")
                        continue
                except Exception as retry_error:
                    logger.error(f"❌ Retry failed: {retry_error}")
                
                # 🔒 STOP if retry fails (no drifting)
                last_error = str(e)
                break
        
        # Final state detection
        final_state = await detect_state(page)
        
        result = {
            "success": steps_completed == len(intent_steps),
            "steps_completed": steps_completed,
            "total_steps": len(intent_steps),
            "checkpoints": len(self.checkpoint_manager.checkpoints),
            "final_state": final_state.value,
            "error": last_error
        }
        
        logger.info(f"\n{'='*60}")
        logger.info(f"🏁 Execution Complete")
        logger.info(f"   Success: {result['success']}")
        logger.info(f"   Steps: {result['steps_completed']}/{result['total_steps']}")
        logger.info(f"   Checkpoints: {result['checkpoints']}")
        logger.info(f"   Final State: {result['final_state']}")
        if last_error:
            logger.info(f"   Error: {last_error}")
        logger.info(f"{'='*60}\n")
        
        return result
    
    async def _reset_environment(self, context: BrowserContext, page: Page):
        """
        🔒 PHASE 9 — RESET ENVIRONMENT
        Ensure clean state for each run
        """
        logger.info("🧹 Resetting environment...")
        
        try:
            # Clear cookies
            await context.clear_cookies()
            logger.debug("  ✅ Cookies cleared")
        except:
            pass
        
        try:
            # Clear permissions
            await context.clear_permissions()
            logger.debug("  ✅ Permissions cleared")
        except:
            pass
        
        try:
            # Go to blank page
            await page.goto("about:blank")
            logger.debug("  ✅ Navigated to blank page")
        except:
            pass
        
        # Small wait for cleanup
        await page.wait_for_timeout(500)
        
        logger.info("✅ Environment reset complete")
    
    def _is_milestone_state(self, state: AppState) -> bool:
        """Check if state is a major milestone worthy of checkpoint"""
        milestone_states = {
            AppState.PRODUCT_DETAIL,
            AppState.CART,
            AppState.CHECKOUT,
            AppState.PAYMENT,
            AppState.ORDER_CONFIRMATION
        }
        return state in milestone_states
