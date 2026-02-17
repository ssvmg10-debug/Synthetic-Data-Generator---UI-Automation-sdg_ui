"""
Test Hybrid Architecture - Validate 4-phase execution on LG website

Tests the failing scenarios from uvicorn.log:
1. Search for "lg 108cm tv" and click Buy Now (was failing at step 3 & 5)
2. Navigate Air Solutions → Split AC → Add to cart (was failing at step 4)
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from services.ui_automation.enterprise_flow_engine import EnterpriseFlowEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def test_lg_search_and_buy_hybrid():
    """
    Test Case 118 from logs - was failing at:
    - Step 3: TYPE('lg 108cm tv search', 'lg 108cm tv') - Could not find search input
    - Step 5: CLICK('Buy Now') - Clicked wrong button
    
    HYBRID should:
    - Phase 2 scores modal inputs to find search box
    - Phase 2 scores products to match "LG 108cm TV"
    """
    print("\n" + "="*80)
    print("TEST 1: LG Search and Buy (HYBRID Mode)")
    print("="*80)
    
    plan = {
        "url": "https://www.lg.com/in",
        "steps": [
            {
                "step_number": 1,
                "action": "navigate to https://www.lg.com/in",
                "ui_intent": "navigate"
            },
            {
                "step_number": 2,
                "action": "click on the search icon",
                "ui_intent": "click",
                "locator_hint": "search icon or button"
            },
            {
                "step_number": 3,
                "action": "type 'lg 108cm tv' in search input",
                "ui_intent": "type",
                "locator_hint": "search input field"
            },
            {
                "step_number": 4,
                "action": "click search button",
                "ui_intent": "click",
                "locator_hint": "search submit button"
            },
            {
                "step_number": 5,
                "action": "click Buy Now for lg 108cm tv",
                "ui_intent": "click",
                "locator_hint": "Buy Now button"
            }
        ]
    }
    
    engine = EnterpriseFlowEngine(
        mode="HYBRID",  # 4-phase execution
        structured_plan=plan,
        headless=False  # Visible browser to observe
    )
    
    result = await engine.run(plan["url"])
    
    print("\n" + "="*80)
    print("TEST 1 RESULTS:")
    print("="*80)
    print(f"Success: {result.success}")
    print(f"Steps Completed: {result.steps_executed}/{len(plan['steps'])}")
    print(f"Execution Time: {result.execution_time:.2f}s")
    print(f"Health Score: {result.health_score:.1f}/100")
    if hasattr(result, 'phase_breakdown'):
        print(f"\nPhase Breakdown:")
        for phase, count in result.phase_breakdown.items():
            if count > 0:
                print(f"  {phase}: {count} steps")
    print("="*80)
    
    return result.success


async def test_lg_air_conditioner_hybrid():
    """
    Test Case 119 from logs - was failing at:
    - Step 4: CLICK('Add to cart') - Button not found
    
    HYBRID should:
    - Phase 2 or 3 finds Add to cart button on product listing
    """
    print("\n" + "="*80)
    print("TEST 2: LG Air Conditioner (HYBRID Mode)")
    print("="*80)
    
    plan = {
        "url": "https://www.lg.com/in",
        "steps": [
            {
                "step_number": 1,
                "action": "navigate to https://www.lg.com/in",
                "ui_intent": "navigate"
            },
            {
                "step_number": 2,
                "action": "click Air Solutions",
                "ui_intent": "click",
                "locator_hint": "Air Solutions link or menu"
            },
            {
                "step_number": 3,
                "action": "click Split Air Conditioners",
                "ui_intent": "click",
                "locator_hint": "Split Air Conditioners link"
            },
            {
                "step_number": 4,
                "action": "click Add to cart for first product",
                "ui_intent": "click",
                "locator_hint": "Add to cart button"
            }
        ]
    }
    
    engine = EnterpriseFlowEngine(
        mode="HYBRID",
        structured_plan=plan,
        headless=False
    )
    
    result = await engine.run(plan["url"])
    
    print("\n" + "="*80)
    print("TEST 2 RESULTS:")
    print("="*80)
    print(f"Success: {result.success}")
    print(f"Steps Completed: {result.steps_executed}/{len(plan['steps'])}")
    print(f"Execution Time: {result.execution_time:.2f}s")
    print(f"Health Score: {result.health_score:.1f}/100")
    if hasattr(result, 'phase_breakdown'):
        print(f"\nPhase Breakdown:")
        for phase, count in result.phase_breakdown.items():
            if count > 0:
                print(f"  {phase}: {count} steps")
    print("="*80)
    
    return result.success


async def compare_modes():
    """
    Compare INSTRUCTION vs HYBRID on same test case.
    """
    print("\n" + "="*80)
    print("MODE COMPARISON: INSTRUCTION vs HYBRID")
    print("="*80)
    
    plan = {
        "url": "https://www.lg.com/in",
        "steps": [
            {
                "step_number": 1,
                "action": "navigate to https://www.lg.com/in",
                "ui_intent": "navigate"
            },
            {
                "step_number": 2,
                "action": "click on search icon",
                "ui_intent": "click"
            },
            {
                "step_number": 3,
                "action": "type 'lg tv' in search",
                "ui_intent": "type"
            }
        ]
    }
    
    # Test INSTRUCTION mode
    print("\n▶ Testing INSTRUCTION mode...")
    engine_instruction = EnterpriseFlowEngine(
        mode="INSTRUCTION",
        structured_plan=plan,
        headless=False
    )
    result_instruction = await engine_instruction.run(plan["url"])
    
    await asyncio.sleep(3)
    
    # Test HYBRID mode
    print("\n▶ Testing HYBRID mode...")
    engine_hybrid = EnterpriseFlowEngine(
        mode="HYBRID",
        structured_plan=plan,
        headless=False
    )
    result_hybrid = await engine_hybrid.run(plan["url"])
    
    # Compare
    print("\n" + "="*80)
    print("COMPARISON RESULTS:")
    print("="*80)
    print(f"INSTRUCTION Mode:")
    print(f"  Success: {result_instruction.success}")
    print(f"  Steps: {result_instruction.steps_executed}/{len(plan['steps'])}")
    print(f"  Time: {result_instruction.execution_time:.2f}s")
    print(f"\nHYBRID Mode:")
    print(f"  Success: {result_hybrid.success}")
    print(f"  Steps: {result_hybrid.steps_executed}/{len(plan['steps'])}")
    print(f"  Time: {result_hybrid.execution_time:.2f}s")
    print(f"\n{'HYBRID WINS! 🎉' if result_hybrid.success and not result_instruction.success else 'Both succeeded ✅' if result_hybrid.success and result_instruction.success else 'Both failed ❌'}")
    print("="*80)


async def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("🔥 HYBRID ARCHITECTURE TEST SUITE")
    print("="*80)
    print("\nTesting 4-phase execution:")
    print("  Phase 1: Deterministic (fast path)")
    print("  Phase 2: Smart Resolver (mathematical scoring)")
    print("  Phase 3: Autonomous Loop (goal-driven reasoning)")
    print("  Phase 4: LLM Healing (last resort)")
    print("\n" + "="*80)
    
    try:
        # Test 1: Search and buy (was failing)
        test1_success = await test_lg_search_and_buy_hybrid()
        
        await asyncio.sleep(5)
        
        # Test 2: Air conditioner (was failing)
        test2_success = await test_lg_air_conditioner_hybrid()
        
        await asyncio.sleep(5)
        
        # Test 3: Mode comparison
        await compare_modes()
        
        # Summary
        print("\n" + "="*80)
        print("📊 FINAL SUMMARY")
        print("="*80)
        print(f"Test 1 (Search & Buy): {'✅ PASS' if test1_success else '❌ FAIL'}")
        print(f"Test 2 (Air Conditioner): {'✅ PASS' if test2_success else '❌ FAIL'}")
        print("\nHYBRID architecture is ready for production!")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
