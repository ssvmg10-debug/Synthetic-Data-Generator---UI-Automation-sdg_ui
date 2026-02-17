"""
Test Enterprise Flow Engine v3

Validates the new probabilistic, structural, healing-enabled architecture.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from services.ui_automation.enterprise_flow_engine import EnterpriseFlowEngine, EnterpriseFlowResult
from services.ui_automation.goal_extractor import extract_goal_from_text
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_lg_india():
    """Test LG India e-commerce flow."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: LG India E-Commerce")
    logger.info("=" * 80)
    
    # Test case
    raw_input = """
    Navigate to https://www.lg.com/in
    Click on Air Solutions
    Click on Split Air Conditioners
    Buy product under 50000 rupees
    """
    
    # Extract goal
    goal = extract_goal_from_text(raw_input)
    
    logger.info(f"Goal: {goal}")
    
    # Run engine
    engine = EnterpriseFlowEngine(goal=goal, headless=False)
    result = await engine.run("https://www.lg.com/in")
    
    # Print results
    print_result(result)
    
    return result


async def test_sauce_demo():
    """Test Sauce Demo login and purchase."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Sauce Demo")
    logger.info("=" * 80)
    
    raw_input = """
    Go to https://www.saucedemo.com
    Login with username standard_user and password secret_sauce
    Add Sauce Labs Backpack to cart
    Checkout
    """
    
    goal = extract_goal_from_text(raw_input)
    logger.info(f"Goal: {goal}")
    
    engine = EnterpriseFlowEngine(goal=goal, headless=False)
    result = await engine.run("https://www.saucedemo.com")
    
    print_result(result)
    
    return result


async def test_exploration_mode():
    """Test exploration when no clear intent matches."""
    logger.info("\n" + "=" * 80)
    logger.info("TEST: Exploration Mode")
    logger.info("=" * 80)
    
    # Vague goal to force exploration
    raw_input = """
    Navigate to https://www.lg.com/in
    Browse the site
    """
    
    goal = extract_goal_from_text(raw_input)
    goal.complete_purchase = False  # No specific goal
    
    logger.info(f"Goal: {goal}")
    
    engine = EnterpriseFlowEngine(goal=goal, headless=False)
    result = await engine.run("https://www.lg.com/in")
    
    print_result(result)
    
    return result


def print_result(result: EnterpriseFlowResult):
    """Pretty print test result."""
    print("\n" + "=" * 80)
    print("RESULT SUMMARY")
    print("=" * 80)
    print(f"✅ Success: {result.success}")
    print(f"🎯 Goal Reached: {result.goal_reached}")
    print(f"📊 Steps Executed: {result.steps_executed}")
    print(f"⏱️  Execution Time: {result.execution_time:.2f}s")
    print(f"💯 Health Score: {result.health_score:.2f}")
    print(f"\n📈 Enterprise Metrics:")
    print(f"  - Avg Confidence: {sum(result.confidence_scores) / len(result.confidence_scores):.2f}" if result.confidence_scores else "  - No scores")
    print(f"  - Healing Attempts: {result.healing_attempts}")
    print(f"  - Exploration Count: {result.exploration_count}")
    print(f"  - Deadlock Recoveries: {result.deadlock_recoveries}")
    
    if result.error:
        print(f"\n❌ Error: {result.error}")
    
    print(f"\n📸 Screenshots: {len(result.screenshots)}")
    if result.screenshots:
        print(f"  First: {result.screenshots[0]}")
        print(f"  Last: {result.screenshots[-1]}")
    
    print("=" * 80 + "\n")


async def run_all_tests():
    """Run comprehensive test suite."""
    logger.info("\n" + "🚀" * 30)
    logger.info("ENTERPRISE FLOW ENGINE V3 - TEST SUITE")
    logger.info("🚀" * 30 + "\n")
    
    results = {}
    
    # Test 1: LG India
    try:
        results["lg_india"] = await test_lg_india()
    except Exception as e:
        logger.error(f"LG India test failed: {e}", exc_info=True)
        results["lg_india"] = None
    
    # Test 2: Sauce Demo
    try:
        results["sauce_demo"] = await test_sauce_demo()
    except Exception as e:
        logger.error(f"Sauce Demo test failed: {e}", exc_info=True)
        results["sauce_demo"] = None
    
    # Test 3: Exploration
    try:
        results["exploration"] = await test_exploration_mode()
    except Exception as e:
        logger.error(f"Exploration test failed: {e}", exc_info=True)
        results["exploration"] = None
    
    # Summary
    print("\n" + "=" * 80)
    print("FINAL TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for r in results.values() if r and r.success)
    total = len(results)
    
    print(f"\n✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")
    
    for test_name, result in results.items():
        status = "✅ PASS" if result and result.success else "❌ FAIL"
        print(f"  {status} - {test_name}")
    
    print("\n" + "=" * 80)
    
    return results


if __name__ == "__main__":
    # Run tests
    results = asyncio.run(run_all_tests())
    
    # Exit with proper code
    all_passed = all(r and r.success for r in results.values())
    sys.exit(0 if all_passed else 1)
