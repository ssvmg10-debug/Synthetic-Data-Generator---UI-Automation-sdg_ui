"""
🧪 TEST CASE: LG India Banner Navigation - Party Speaker Purchase
Tests the specific scenario: Banner → Buy Electronics → Audio → Party Speakers → Checkout

This test case validates the new Enhanced Deterministic System V2 with:
- Banner click (India ka passion LG ka celebration)
- Category navigation (Buy Electronics & IT → Audio)
- Filter application (Party Speakers checkbox)
- Product selection (LG XBOOM RNC5)
- Checkout flow with pincode, delivery, payment
"""
import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from playwright.async_api import async_playwright
from services.ui_automation.core.enhanced_deterministic_executor import DeterministicExecutorV2
from services.ui_automation.core.semantic_parser import SemanticTestParser
from services.ui_automation.core.test_model import TestCase, TestStep, StepType, Intent, PageState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_lg_banner_party_speaker():
    """
    Test Case: LG India Banner → Party Speaker Purchase
    
    Steps:
    1. Navigate to https://www.lg.com/in
    2. Click banner: "India ka passion LG ka celebration" → Buy Electronics & IT
    3. Click Audio category
    4. Apply filter: Party Speakers checkbox
    5. Select product: LG XBOOM RNC5
    6. Click Buy Now
    7. Fill pincode: 500032
    8. Click check button (wait 5s)
    9. Select free delivery option
    10. Click checkout
    11. Continue as guest
    12. Fill billing/shipping details
    13. Select payment: QR code
    14. Accept all checkboxes
    15. Place order
    """
    logger.info("="*80)
    logger.info("TEST: LG India Banner → Party Speaker Purchase")
    logger.info("="*80)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()
        
        executor = DeterministicExecutorV2(page, context)
        
        # Method 1: Natural Language Format (Easy)
        logger.info("\n" + "="*60)
        logger.info("METHOD 1: Natural Language Format")
        logger.info("="*60)
        
        natural_language_test = """
        Navigate to https://www.lg.com/in,
        Click on India ka passion LG ka celebration banner,
        Click Buy electronics & IT,
        Click Audio,
        Under filters under category click party speakers checkbox,
        Click product LG XBOOM RNC5 Deep Bass Powerful Sound Karaoke Bluetooth Party Speaker,
        Click buy now,
        Fill pincode 500032,
        Click check beside pincode,
        Wait 5 seconds,
        Select free delivery option in delivery method,
        Click checkout,
        Click continue with this condition complete purchase as guest,
        Fill billing shipping details,
        In payment click QR code,
        Click all checkboxes,
        Click place order
        """
        
        # Execute
        result = await executor.execute_natural_language(natural_language_test)
        
        # Print results
        logger.info("\n" + "="*60)
        logger.info("EXECUTION RESULT:")
        logger.info("="*60)
        logger.info(f"Status: {'✅ PASSED' if result.passed else '❌ FAILED'}")
        logger.info(f"Steps Executed: {result.executed_steps}/{result.total_steps}")
        logger.info(f"Duration: {result.duration_ms}ms")
        
        if not result.passed:
            logger.error(f"❌ Failed at step {result.failed_step}")
            logger.error(f"Error: {result.error}")
        
        logger.info("\nCheckpoints:")
        for cp in result.checkpoints:
            status = "✅" if cp.success else "❌"
            logger.info(f"{status} Step {cp.step_id}: {cp.step_description}")
            logger.info(f"   State: {cp.state}")
            if cp.error:
                logger.error(f"   Error: {cp.error}")
        
        await browser.close()
    
    return result


async def test_lg_banner_enterprise_format():
    """
    Same test case in Enterprise Format (Production-ready)
    """
    logger.info("="*80)
    logger.info("TEST: LG Banner (Enterprise Format)")
    logger.info("="*80)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        
        executor = DeterministicExecutorV2(page, context)
        
        # Enterprise format with structured steps
        enterprise_spec = {
            "Test Case ID": "TC_LG_BANNER_001",
            "Objective": "Verify LG India banner navigation and party speaker purchase flow",
            "Preconditions": [
                "Browser opened",
                "Internet connection available",
                "LG India website accessible"
            ],
            "Test Data": {
                "url": "https://www.lg.com/in",
                "product": "LG XBOOM RNC5",
                "pincode": "500032",
                "category": "Audio",
                "filter": "Party Speakers"
            },
            "Steps": [
                {
                    "Step": "Navigate to LG India homepage",
                    "Expected Result": "Homepage loaded with banner visible"
                },
                {
                    "Step": "Click on 'India ka passion LG ka celebration' banner",
                    "Expected Result": "Banner menu displayed"
                },
                {
                    "Step": "Click Buy electronics & IT",
                    "Expected Result": "Electronics category page displayed"
                },
                {
                    "Step": "Click Audio category",
                    "Expected Result": "Audio products page loaded"
                },
                {
                    "Step": "Under filters, under category, click party speakers checkbox",
                    "Expected Result": "Filter applied, party speakers displayed"
                },
                {
                    "Step": "Click product LG XBOOM RNC5 Deep Bass Powerful Sound Karaoke Bluetooth Party Speaker",
                    "Expected Result": "Product detail page loaded with product information"
                },
                {
                    "Step": "Click buy now button",
                    "Expected Result": "Checkout page loaded"
                },
                {
                    "Step": "Fill pincode field with 500032",
                    "Expected Result": "Pincode entered in field"
                },
                {
                    "Step": "Click check button beside pincode field",
                    "Expected Result": "Pincode validation started"
                },
                {
                    "Step": "Wait for 5 seconds",
                    "Expected Result": "Delivery options loaded"
                },
                {
                    "Step": "Select free delivery option in delivery method",
                    "Expected Result": "Free delivery selected"
                },
                {
                    "Step": "Click checkout button",
                    "Expected Result": "Billing page displayed"
                },
                {
                    "Step": "Click continue with condition 'complete purchase as guest'",
                    "Expected Result": "Guest checkout form displayed"
                },
                {
                    "Step": "Fill billing and shipping details",
                    "Expected Result": "Details filled successfully"
                },
                {
                    "Step": "In payment section, click QR code option",
                    "Expected Result": "QR code payment selected"
                },
                {
                    "Step": "Click all checkboxes for terms and conditions",
                    "Expected Result": "All checkboxes checked"
                },
                {
                    "Step": "Click place order button",
                    "Expected Result": "Order placed successfully"
                }
            ]
        }
        
        # Execute
        result = await executor.execute_enterprise_format(enterprise_spec)
        
        # Print results
        logger.info("\n" + "="*60)
        logger.info("EXECUTION RESULT (Enterprise Format):")
        logger.info("="*60)
        logger.info(f"Test ID: {result.test_id}")
        logger.info(f"Status: {'✅ PASSED' if result.passed else '❌ FAILED'}")
        logger.info(f"Steps: {result.executed_steps}/{result.total_steps}")
        logger.info(f"Duration: {result.duration_ms}ms ({result.duration_ms/1000:.2f}s)")
        
        if not result.passed:
            logger.error(f"\n❌ FAILURE DETAILS:")
            logger.error(f"Failed Step: {result.failed_step}")
            logger.error(f"Error: {result.error}")
        
        await browser.close()
    
    return result


async def test_direct_dsl_format():
    """
    Direct DSL format (most advanced - for fine-grained control)
    """
    logger.info("="*80)
    logger.info("TEST: LG Banner (Direct DSL Format)")
    logger.info("="*80)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        executor = DeterministicExecutorV2(page, context)
        
        # Create test case using direct DSL
        test_case = TestCase(
            id="TC_LG_BANNER_DSL_001",
            title="LG Banner Party Speaker Purchase (Direct DSL)",
            objective="Validate banner navigation and checkout flow",
            steps=[
                # Step 1: Navigate
                TestStep(
                    id=1,
                    type=StepType.NAVIGATION,
                    intent=Intent.GOTO,
                    target="https://www.lg.com/in",
                    expected_state=PageState.HOME
                ),
                
                # Step 2: Verify homepage loaded
                TestStep(
                    id=2,
                    type=StepType.ASSERTION,
                    intent=Intent.PAGE_LOADED,
                    value="homepage with banner",
                    required_state=PageState.HOME
                ),
                
                # Step 3: Click banner
                TestStep(
                    id=3,
                    type=StepType.ACTION,
                    intent=Intent.CLICK,
                    target="India ka passion LG ka celebration",
                    required_state=PageState.HOME
                ),
                
                # Step 4: Click Buy Electronics
                TestStep(
                    id=4,
                    type=StepType.ACTION,
                    intent=Intent.CLICK,
                    target="Buy electronics & IT",
                    expected_state=PageState.CATEGORY
                ),
                
                # Step 5: Verify category page
                TestStep(
                    id=5,
                    type=StepType.ASSERTION,
                    intent=Intent.PAGE_LOADED,
                    value="electronics category",
                    required_state=PageState.CATEGORY
                ),
                
                # Step 6: Click Audio
                TestStep(
                    id=6,
                    type=StepType.ACTION,
                    intent=Intent.CLICK,
                    target="Audio",
                    expected_state=PageState.PRODUCT_LIST
                ),
                
                # Step 7: Apply filter
                TestStep(
                    id=7,
                    type=StepType.ACTION,
                    intent=Intent.CLICK,
                    target="party speakers checkbox",
                    metadata={"is_filter": True}
                ),
                
                # Step 8: Verify filter applied
                TestStep(
                    id=8,
                    type=StepType.ASSERTION,
                    intent=Intent.FILTER_APPLIED,
                    value="party speakers filter"
                ),
                
                # Step 9: Select product
                TestStep(
                    id=9,
                    type=StepType.ACTION,
                    intent=Intent.SELECT,
                    target="LG XBOOM RNC5",
                    required_state=PageState.PRODUCT_LIST,
                    expected_state=PageState.PRODUCT_DETAIL,
                    metadata={"is_product": True}
                ),
                
                # Step 10: Verify product page
                TestStep(
                    id=10,
                    type=StepType.ASSERTION,
                    intent=Intent.PAGE_LOADED,
                    value="product detail page",
                    required_state=PageState.PRODUCT_DETAIL
                ),
                
                # Step 11: Buy now
                TestStep(
                    id=11,
                    type=StepType.ACTION,
                    intent=Intent.BUY_NOW,
                    required_state=PageState.PRODUCT_DETAIL,
                    expected_state=PageState.CART
                ),
                
                # Step 12: Fill pincode
                TestStep(
                    id=12,
                    type=StepType.INPUT,
                    intent=Intent.FILL_PINCODE,
                    target="pincode",
                    value="500032"
                ),
                
                # Step 13: Check pincode
                TestStep(
                    id=13,
                    type=StepType.ACTION,
                    intent=Intent.CLICK,
                    target="check",
                    metadata={"related_to": "pincode"}
                ),
                
                # Step 14: Wait for delivery options
                TestStep(
                    id=14,
                    type=StepType.WAIT,
                    intent=Intent.WAIT_FOR_ELEMENT,
                    target=".delivery-option",
                    metadata={"duration_ms": 5000}
                ),
                
                # Step 15: Verify delivery options loaded
                TestStep(
                    id=15,
                    type=StepType.ASSERTION,
                    intent=Intent.DELIVERY_OPTIONS_LOADED,
                    value="delivery options"
                ),
                
                # Step 16: Select free delivery
                TestStep(
                    id=16,
                    type=StepType.ACTION,
                    intent=Intent.SELECT_OPTION,
                    target="free delivery option"
                ),
                
                # Step 17: Checkout
                TestStep(
                    id=17,
                    type=StepType.ACTION,
                    intent=Intent.CHECKOUT,
                    required_state=PageState.CART,
                    expected_state=PageState.CHECKOUT
                ),
                
                # Step 18: Continue as guest
                TestStep(
                    id=18,
                    type=StepType.ACTION,
                    intent=Intent.CONTINUE_AS_GUEST,
                    expected_state=PageState.CHECKOUT
                ),
                
                # Remaining steps would follow similar pattern...
            ]
        )
        
        # Execute
        result = await executor.execute_test_case(test_case)
        
        logger.info(f"\nDirect DSL Result: {'✅ PASSED' if result.passed else '❌ FAILED'}")
        logger.info(f"Steps: {result.executed_steps}/{result.total_steps}")
        
        await browser.close()
    
    return result


async def run_all_lg_banner_tests():
    """Run all test variations"""
    logger.info("\n" + "="*80)
    logger.info("RUNNING ALL LG BANNER TEST VARIATIONS")
    logger.info("="*80)
    
    results = []
    
    # Test 1: Natural Language
    try:
        logger.info("\n🧪 Test 1: Natural Language Format")
        result1 = await test_lg_banner_party_speaker()
        results.append(("Natural Language", result1.passed))
    except Exception as e:
        logger.error(f"Test 1 failed with exception: {e}")
        results.append(("Natural Language", False))
    
    # Test 2: Enterprise Format
    try:
        logger.info("\n🧪 Test 2: Enterprise Format")
        result2 = await test_lg_banner_enterprise_format()
        results.append(("Enterprise Format", result2.passed))
    except Exception as e:
        logger.error(f"Test 2 failed with exception: {e}")
        results.append(("Enterprise Format", False))
    
    # Test 3: Direct DSL (optional - comment out if too long)
    # try:
    #     logger.info("\n🧪 Test 3: Direct DSL Format")
    #     result3 = await test_direct_dsl_format()
    #     results.append(("Direct DSL", result3.passed))
    # except Exception as e:
    #     logger.error(f"Test 3 failed with exception: {e}")
    #     results.append(("Direct DSL", False))
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("TEST SUMMARY:")
    logger.info("="*80)
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
    
    passed_count = sum(1 for _, passed in results if passed)
    logger.info(f"\nTotal: {passed_count}/{len(results)} tests passed")
    logger.info("="*80)


if __name__ == "__main__":
    # Run the natural language test (easiest to start with)
    asyncio.run(test_lg_banner_party_speaker())
    
    # Or run all tests
    # asyncio.run(run_all_lg_banner_tests())
