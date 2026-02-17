"""
Test State-Driven Architecture with LG website.

This script tests the new context-aware execution against the failing test cases.
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from services.ui_automation.enterprise_flow_engine import EnterpriseFlowEngine
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_lg_search_and_buy():
    """
    Test Case 1: Search for TV and Buy
    
    This was failing at:
    - Step 3: TYPE('lg 108cm tv search', 'lg 108cm tv') → Failed to find input
    - Step 5: CLICK('Buy Now') → Failed to find or clicked wrong button
    """
    logger.info("="*80)
    logger.info("TEST 1: LG Search and Buy TV")
    logger.info("="*80)
    
    test_plan = {
        "steps": [
            {
                "step_number": 1,
                "action": "navigate to https://www.lg.com/in",
                "ui_intent": "navigate"
            },
            {
                "step_number": 2,
                "action": "click on Search",
                "ui_intent": "click"
            },
            {
                "step_number": 3,
                "action": "search for lg 108cm tv",
                "ui_intent": "type",
                "locator_hint": "search input"
            },
            {
                "step_number": 4,
                "action": "click on Search button",
                "ui_intent": "click"
            },
            {
                "step_number": 5,
                "action": "click on buynow for LG 4 Star (1.5 Ton) Split AC",
                "ui_intent": "click",
                "locator_hint": "Buy Now button for LG 4 Star AC"
            }
        ]
    }
    
    engine = EnterpriseFlowEngine(
        mode="STATE_DRIVEN",
        structured_plan=test_plan,
        headless=False,
        run_id="test_lg_search_buy"
    )
    
    result = await engine.run("https://www.lg.com/in")
    
    logger.info("="*80)
    logger.info(f"TEST 1 RESULT:")
    logger.info(f"  Success: {result.success}")
    logger.info(f"  Steps: {result.steps_executed}/{len(test_plan['steps'])}")
    logger.info(f"  Health Score: {result.health_score:.1f}/100")
    logger.info(f"  Time: {result.execution_time:.2f}s")
    if not result.success:
        logger.info(f"  Error: {result.error}")
    logger.info("="*80)
    
    return result


async def test_lg_air_conditioner_flow():
    """
    Test Case 2: Air Conditioner Purchase Flow
    
    This was failing at:
    - Step 4: CLICK('Add to cart') → Failed to find button
    """
    logger.info("="*80)
    logger.info("TEST 2: LG Air Conditioner Purchase")
    logger.info("="*80)
    
    test_plan = {
        "steps": [
            {
                "step_number": 1,
                "action": "navigate to https://www.lg.com/in",
                "ui_intent": "navigate"
            },
            {
                "step_number": 2,
                "action": "click on Air Solutions",
                "ui_intent": "click"
            },
            {
                "step_number": 3,
                "action": "click on Split Air Conditioners",
                "ui_intent": "click"
            },
            {
                "step_number": 4,
                "action": "buy first split AC",
                "ui_intent": "click",
                "locator_hint": "Add to cart or Buy Now"
            }
        ]
    }
    
    engine = EnterpriseFlowEngine(
        mode="STATE_DRIVEN",
        structured_plan=test_plan,
        headless=False,
        run_id="test_lg_ac_buy"
    )
    
    result = await engine.run("https://www.lg.com/in")
    
    logger.info("="*80)
    logger.info(f"TEST 2 RESULT:")
    logger.info(f"  Success: {result.success}")
    logger.info(f"  Steps: {result.steps_executed}/{len(test_plan['steps'])}")
    logger.info(f"  Health Score: {result.health_score:.1f}/100")
    logger.info(f"  Time: {result.execution_time:.2f}s")
    if not result.success:
        logger.info(f"  Error: {result.error}")
    logger.info("="*80)
    
    return result


async def compare_modes():
    """
    Compare INSTRUCTION mode vs STATE_DRIVEN mode.
    """
    logger.info("="*80)
    logger.info("COMPARISON TEST: INSTRUCTION vs STATE_DRIVEN")
    logger.info("="*80)
    
    test_plan = {
        "steps": [
            {
                "step_number": 1,
                "action": "navigate to https://www.lg.com/in",
                "ui_intent": "navigate"
            },
            {
                "step_number": 2,
                "action": "click on Air Solutions",
                "ui_intent": "click"
            },
            {
                "step_number": 3,
                "action": "click on Split Air Conditioners",
                "ui_intent": "click"
            }
        ]
    }
    
    # Test with INSTRUCTION mode
    logger.info("\n--- Testing INSTRUCTION mode ---")
    engine_instruction = EnterpriseFlowEngine(
        mode="INSTRUCTION",
        structured_plan=test_plan,
        headless=False,
        run_id="test_comparison_instruction"
    )
    result_instruction = await engine_instruction.run("https://www.lg.com/in")
    
    logger.info(f"INSTRUCTION mode: {result_instruction.success} ({result_instruction.steps_executed}/{len(test_plan['steps'])} steps)")
    
    # Small delay between tests
    await asyncio.sleep(3)
    
    # Test with STATE_DRIVEN mode
    logger.info("\n--- Testing STATE_DRIVEN mode ---")
    engine_state = EnterpriseFlowEngine(
        mode="STATE_DRIVEN",
        structured_plan=test_plan,
        headless=False,
        run_id="test_comparison_state"
    )
    result_state = await engine_state.run("https://www.lg.com/in")
    
    logger.info(f"STATE_DRIVEN mode: {result_state.success} ({result_state.steps_executed}/{len(test_plan['steps'])} steps)")
    
    # Compare
    logger.info("="*80)
    logger.info("COMPARISON RESULTS:")
    logger.info(f"  INSTRUCTION:  {result_instruction.success} | Steps: {result_instruction.steps_executed} | Time: {result_instruction.execution_time:.2f}s")
    logger.info(f"  STATE_DRIVEN: {result_state.success} | Steps: {result_state.steps_executed} | Time: {result_state.execution_time:.2f}s")
    logger.info("="*80)


async def main():
    """Run all tests."""
    logger.info("\n" + "="*80)
    logger.info("STARTING STATE-DRIVEN ARCHITECTURE TESTS")
    logger.info("="*80 + "\n")
    
    # Test 1: Search and Buy
    try:
        result1 = await test_lg_search_and_buy()
    except Exception as e:
        logger.error(f"Test 1 failed with exception: {e}", exc_info=True)
        result1 = None
    
    await asyncio.sleep(3)
    
    # Test 2: Air Conditioner Flow
    try:
        result2 = await test_lg_air_conditioner_flow()
    except Exception as e:
        logger.error(f"Test 2 failed with exception: {e}", exc_info=True)
        result2 = None
    
    await asyncio.sleep(3)
    
    # Comparison Test
    try:
        await compare_modes()
    except Exception as e:
        logger.error(f"Comparison test failed with exception: {e}", exc_info=True)
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("FINAL SUMMARY")
    logger.info("="*80)
    if result1:
        logger.info(f"Test 1 (Search & Buy):  {'✅ PASSED' if result1.success else '❌ FAILED'}")
    if result2:
        logger.info(f"Test 2 (AC Purchase):   {'✅ PASSED' if result2.success else '❌ FAILED'}")
    logger.info("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
