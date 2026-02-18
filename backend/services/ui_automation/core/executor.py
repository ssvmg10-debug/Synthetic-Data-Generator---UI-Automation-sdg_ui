"""
Production-Grade Deterministic Executor
Layered approach: Phase 1 → Phase 2 → Phase 3
"""
import logging
import time
from playwright.async_api import Page
from typing import List, Dict, Any
from services.ui_automation.instruction_compiler import Instruction, ActionType
from services.ui_automation.core.navigator import safe_navigate
from services.ui_automation.core.element_resolver import smart_click, smart_type, smart_select
from services.ui_automation.core.smart_resolver import smart_resolve_click, smart_resolve_type
from services.ui_automation.core.healing_agent import HealingAgent
from services.ui_automation.core.cookie_handler import handle_cookie_banner

logger = logging.getLogger(__name__)


async def execute_instructions(page: Page, instructions: List[Instruction]) -> dict:
    """
    Production-grade layered executor.
    
    Architecture:
    1. Phase 1: Deterministic (element_resolver)
    2. Phase 2: Smart Resolver (fuzzy matching)
    3. Phase 3: Healing Agent (AI recovery)
    
    Metrics:
    - Per-step timing
    - Phase usage tracking
    - Healing attempts
    - Clear failure reasons
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"🎯 PRODUCTION EXECUTOR: {len(instructions)} INSTRUCTIONS")
    logger.info(f"{'='*80}\n")
    
    healing_agent = HealingAgent()
    success_count = 0
    healing_attempts = 0
    smart_resolver_attempts = 0
    step_timings = []
    previous_steps = []
    
    for idx, instruction in enumerate(instructions, 1):
        step_start = time.time()
        logger.info(f"\n[{idx}/{len(instructions)}] {instruction}")
        
        try:
            # GOTO - Navigation
            if instruction.action == ActionType.GOTO:
                await safe_navigate(page, instruction.value)
                
                # Handle cookie banner (environment setup)
                await handle_cookie_banner(page)
                
                step_time = time.time() - step_start
                step_timings.append(step_time)
                success_count += 1
                previous_steps.append(f"Navigated to {instruction.value}")
                logger.info(f"  ✅ Complete ({step_time:.2f}s)")
                continue
            
            # CLICK - 3-Phase approach
            elif instruction.action == ActionType.CLICK:
                target = instruction.target_text
                clicked = False
                
                # Phase 1: Deterministic
                try:
                    await smart_click(page, target)
                    clicked = True
                    logger.info(f"  ✅ Phase 1 success")
                except Exception as e1:
                    logger.debug(f"  Phase 1 failed: {e1}")
                    
                    # Phase 2: Smart Resolver (returns success, selector)
                    smart_resolver_attempts += 1
                    try:
                        clicked, _ = await smart_resolve_click(page, target)
                        if clicked:
                            logger.info(f"  ✅ Phase 2 success")
                    except Exception as e2:
                        logger.debug(f"  Phase 2 failed: {e2}")
                    
                    # Phase 3: Healing Agent
                    if not clicked:
                        healing_attempts += 1
                        try:
                            healing_action = await healing_agent.heal_click_failure(
                                page,
                                target,
                                previous_steps,
                                test_context={
                                    "total_instructions": len(instructions),
                                    "executed": idx - 1,
                                    "current_instruction": str(instruction),
                                },
                            )
                            if healing_action:
                                clicked = await healing_agent.apply_healing_action(page, healing_action)
                                if clicked:
                                    logger.info(f"  ✅ Phase 3 (healing) success")
                        except Exception as e3:
                            logger.debug(f"  Phase 3 failed: {e3}")
                
                if not clicked:
                    raise Exception(f"All phases failed for click: '{target}'")
                
                # 🔵 FIX 3: Stabilization after major clicks (Buy Now, Checkout, Check, etc.)
                # Wait for AJAX/modal if this looks like a major action
                target_lower = target.lower()
                if any(keyword in target_lower for keyword in ["buy", "checkout", "cart", "add", "submit", "purchase", "check"]):
                    logger.info(f"  ⏳ STABILIZING after major action ('{target}')...")
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=3000)
                        logger.debug(f"    ✓ DOM content loaded")
                    except Exception as e:
                        logger.debug(f"    DOM wait timeout (may be OK): {e}")
                    # Additional buffer for modals/AJAX to render
                    await page.wait_for_timeout(1000)
                    logger.debug(f"    ✓ 1s buffer complete")
                
                step_time = time.time() - step_start
                step_timings.append(step_time)
                success_count += 1
                previous_steps.append(f"Clicked {target}")
                logger.info(f"  ✅ Complete ({step_time:.2f}s)")
            
            # TYPE - 2-Phase approach (no healing for inputs yet)
            elif instruction.action == ActionType.TYPE:
                target = instruction.target_text
                value = instruction.value
                typed = False
                
                # Phase 1: Deterministic
                try:
                    await smart_type(page, target, value)
                    typed = True
                    logger.info(f"  ✅ Phase 1 success")
                except Exception as e1:
                    logger.debug(f"  Phase 1 failed: {e1}")
                    
                    # Phase 2: Smart Resolver
                    smart_resolver_attempts += 1
                    try:
                        typed = await smart_resolve_type(page, target, value)
                        if typed:
                            logger.info(f"  ✅ Phase 2 success")
                    except Exception as e2:
                        logger.debug(f"  Phase 2 failed: {e2}")
                
                if not typed:
                    raise Exception(f"Failed to type into: '{target}'")
                
                step_time = time.time() - step_start
                step_timings.append(step_time)
                success_count += 1
                previous_steps.append(f"Typed into {target}")
                logger.info(f"  ✅ Complete ({step_time:.2f}s)")
            
            # SELECT - Treat as click for now
            elif instruction.action == ActionType.SELECT:
                await smart_select(page, instruction.target_text, instruction.value)
                
                step_time = time.time() - step_start
                step_timings.append(step_time)
                success_count += 1
                previous_steps.append(f"Selected {instruction.target_text}")
                logger.info(f"  ✅ Complete ({step_time:.2f}s)")
            
            # WAIT - Fixed duration
            elif instruction.action == ActionType.WAIT:
                # Fix: Never allow None, default to 5 seconds
                wait_seconds = instruction.value if instruction.value else 5
                if wait_seconds is None or wait_seconds == "None":
                    wait_seconds = 5
                
                wait_ms = int(wait_seconds) * 1000 if isinstance(wait_seconds, (int, float)) else 5000
                logger.info(f"⏳ Waiting {wait_ms}ms")
                await page.wait_for_timeout(wait_ms)
                
                step_time = time.time() - step_start
                step_timings.append(step_time)
                success_count += 1
                logger.info(f"  ✅ Complete ({step_time:.2f}s)")
            
            else:
                logger.warning(f"⚠️  Unknown action: {instruction.action}")
                continue
            
        except Exception as e:
            step_time = time.time() - step_start
            step_timings.append(step_time)
            logger.error(f"  ❌ Instruction {idx} failed: {e}")
            
            # Return detailed failure info
            return {
                "success": False,
                "steps_executed": success_count,
                "total_steps": len(instructions),
                "error": str(e),
                "failed_at": idx,
                "failure_reason": f"Instruction {idx} ({instruction.action}) failed: {str(e)}",
                "healing_attempts": healing_attempts,
                "smart_resolver_attempts": smart_resolver_attempts,
                "step_timings": step_timings
            }
    
    # All instructions completed
    logger.info(f"\n{'='*80}")
    logger.info(f"✅ EXECUTION COMPLETE: {success_count}/{len(instructions)}")
    logger.info(f"   Healing attempts: {healing_attempts}")
    logger.info(f"   Smart resolver uses: {smart_resolver_attempts}")
    logger.info(f"   Average step time: {sum(step_timings)/len(step_timings):.2f}s")
    logger.info(f"{'='*80}\n")
    
    return {
        "success": True,
        "steps_executed": success_count,
        "total_steps": len(instructions),
        "error": None,
        "healing_attempts": healing_attempts,
        "smart_resolver_attempts": smart_resolver_attempts,
        "step_timings": step_timings
    }
