"""
Test Enterprise Flow Engine v4 - Deterministic Instruction-Following

Validates the new deterministic architecture with LG India test case.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from services.ui_automation.enterprise_flow_engine import EnterpriseFlowEngine, EnterpriseFlowResult
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_lg_india_deterministic():
    """
    Test LG India with deterministic instruction execution.
    
    Expected behavior:
    - Compile 3 instructions from raw text
    - Execute each instruction strictly
    - Verify state changes
    - No random exploration
    - Complete successfully
    """
    logger.info("\n" + "=" * 80)
    logger.info("TEST: LG India - Deterministic Instruction-Following")
    logger.info("=" * 80)
    
    raw_input = """
    navigate to https://www.lg.com/in
    click on air solutions
    click on split air conditioner
    """
    
    logger.info(f"Raw Input:\n{raw_input}")
    
    # Initialize engine with raw input
    engine = EnterpriseFlowEngine(
        raw_input=raw_input,
        headless=False  # Set to True for headless mode
    )
    
    # Run engine (will auto-select instruction mode)
    result = await engine.run("https://www.lg.com/in")
    
    # Print results
    print_result(result)
    
    return result


async def test_lg_india_with_plan():
    """
    Test LG India with structured plan.
    
    Shows how v4 works with existing plan structure.
    """
    logger.info("\n" + "=" * 80)
    logger.info("TEST: LG India - With Structured Plan")
    logger.info("=" * 80)
    
    structured_plan = {
        "url": "https://www.lg.com/in",
        "steps": [
            {
                "intent": "navigate",
                "url": "https://www.lg.com/in"
            },
            {
                "intent": "click",
                "target": "Air Solutions"
            },
            {
                "intent": "click",
                "target": "Split Air Conditioners"
            }
        ]
    }
    
    logger.info(f"Structured Plan: {len(structured_plan['steps'])} steps")
    
    # Initialize engine with plan
    engine = EnterpriseFlowEngine(
        structured_plan=structured_plan,
        headless=False
    )
    
    # Run engine
    result = await engine.run("https://www.lg.com/in")
    
    # Print results
    print_result(result)
    
    return result


async def test_amazon_search():
    """
    Test Amazon search flow.
    
    Shows v4 working on different application.
    """
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Amazon - Search Flow")
    logger.info("=" * 80)
    
    raw_input = """
    navigate to https://www.amazon.in
    type laptop in search box
    click on search button
    """
    
    engine = EnterpriseFlowEngine(
        raw_input=raw_input,
        headless=False
    )
    
    result = await engine.run("https://www.amazon.in")
    
    print_result(result)
    
    return result


def print_result(result: EnterpriseFlowResult):
    """Pretty print test result."""
    print("\n" + "=" * 80)
    print("RESULT SUMMARY")
    print("=" * 80)
    print(f"✅ Success: {result.success}")
    print(f"🎯 Goal Reached: {result.goal_reached}")
    print(f"📋 Mode: {'INSTRUCTION (Deterministic)' if result.instruction_mode else 'AUTONOMOUS (Exploratory)'}")
    print(f"📝 Instructions Compiled: {result.instructions_compiled}")
    print(f"📊 Steps Executed: {result.steps_executed}")
    print(f"⏱️  Execution Time: {result.execution_time:.2f}s")
    print(f"💯 Health Score: {result.health_score:.2f}")
    
    if result.error:
        print(f"\n❌ Error: {result.error}")
    
    if result.screenshots:
        print(f"\n📸 Screenshots: {len(result.screenshots)} captured")
        print(f"   First: {result.screenshots[0]}")
        print(f"   Last: {result.screenshots[-1]}")
    
    print("=" * 80 + "\n")


async def run_all_tests():
    """Run comprehensive test suite."""
    logger.info("\n" + "=" * 80)
    logger.info("ENTERPRISE V4 TEST SUITE")
    logger.info("=" * 80)
    
    results = []
    
    # Test 1: LG India with raw text
    try:
        result1 = await test_lg_india_deterministic()
        results.append(("LG India (Raw Text)", result1.success))
    except Exception as e:
        logger.error(f"Test 1 failed: {e}", exc_info=True)
        results.append(("LG India (Raw Text)", False))
    
    # Test 2: LG India with structured plan
    try:
        result2 = await test_lg_india_with_plan()
        results.append(("LG India (Structured Plan)", result2.success))
    except Exception as e:
        logger.error(f"Test 2 failed: {e}", exc_info=True)
        results.append(("LG India (Structured Plan)", False))
    
    # Test 3: Amazon search
    # Uncomment to test Amazon
    # try:
    #     result3 = await test_amazon_search()
    #     results.append(("Amazon Search", result3.success))
    # except Exception as e:
    #     logger.error(f"Test 3 failed: {e}", exc_info=True)
    #     results.append(("Amazon Search", False))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUITE SUMMARY")
    print("=" * 80)
    
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 80 + "\n")
    
    return all(success for _, success in results)


if __name__ == "__main__":
    # Run single test
    # asyncio.run(test_lg_india_deterministic())
    
    # Or run full suite
    success = asyncio.run(run_all_tests())
    
    sys.exit(0 if success else 1)
