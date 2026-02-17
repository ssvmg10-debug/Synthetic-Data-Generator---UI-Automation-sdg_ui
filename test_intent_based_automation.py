"""
Intent-Based Automation Test Script
Demonstrates the new production-grade intent system
"""
import asyncio
import logging
from playwright.async_api import async_playwright
from services.ui_automation.core import execute_test_case_with_intents

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)


async def test_lg_ecommerce_intent_based():
    """
    Test LG e-commerce flow using intent-based automation.
    
    This demonstrates:
    - Semantic intent planning
    - SearchFlow for search
    - ProductFlow for product selection
    - CheckoutFlow for checkout
    - State validation
    - CTA classification
    """
    
    test_case = """
    Search for "lg 108cm tv"
    Click buy now for "LG 4 Star (1.5 Ton) Split AC 2026 Model"
    Enter pincode 500032
    Select delivery option "free delivery"
    """
    
    url = "https://www.lg.com/in"
    
    logger.info("="*80)
    logger.info("🚀 INTENT-BASED AUTOMATION TEST")
    logger.info("="*80)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            # Execute using intent system
            result = await execute_test_case_with_intents(page, test_case, url)
            
            # Print results
            logger.info("\n" + "="*80)
            logger.info("📊 TEST RESULTS")
            logger.info("="*80)
            logger.info(f"Success: {result['success']}")
            logger.info(f"Total Intents: {result['total_intents']}")
            logger.info(f"Executed: {result['executed_intents']}")
            logger.info(f"Success Count: {result['success_count']}")
            logger.info(f"Failure Count: {result['failure_count']}")
            logger.info(f"Total Time: {result['total_time']:.2f}s")
            logger.info(f"Avg Time/Intent: {result['avg_time_per_intent']:.2f}s")
            
            logger.info("\n📈 Phase Usage:")
            logger.info(f"  Flow Executors: {result['phase_stats']['flow_executors']}")
            logger.info(f"  Resolver: {result['phase_stats']['resolver']}")
            logger.info(f"  Retries: {result['phase_stats']['retry']}")
            
            logger.info("\n📋 Intent Breakdown:")
            for i, intent in enumerate(result['intent_breakdown'], 1):
                status = "✅" if intent['success'] else "❌"
                logger.info(
                    f"  {i}. {status} {intent['intent']} "
                    f"({intent['execution_time']:.2f}s) "
                    f"[validated: {intent['state_validated']}]"
                )
            
            logger.info("="*80)
            
            return result['success']
            
        except Exception as e:
            logger.error(f"❌ Test failed: {e}", exc_info=True)
            return False
        finally:
            await browser.close()


async def test_simple_search_intent():
    """
    Simple test: Just search functionality
    """
    
    test_case = "Search for 'lg refrigerator'"
    url = "https://www.lg.com/in"
    
    logger.info("🔍 Testing simple search intent")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            result = await execute_test_case_with_intents(page, test_case, url)
            logger.info(f"Result: {result['success']}")
            return result['success']
        finally:
            await browser.close()


async def test_product_selection_intent():
    """
    Test: Search + product selection
    """
    
    test_case = """
    Search for "lg washing machine"
    Select product "LG 6.5 Kg Front Load"
    """
    
    url = "https://www.lg.com/in"
    
    logger.info("🛍️  Testing product selection intent")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            result = await execute_test_case_with_intents(page, test_case, url)
            logger.info(f"Result: {result['success']}")
            return result['success']
        finally:
            await browser.close()


if __name__ == "__main__":
    # Run tests
    logger.info("🎬 Starting Intent-Based Automation Tests\n")
    
    # Test 1: Simple search
    logger.info("\n" + "="*80)
    logger.info("TEST 1: Simple Search")
    logger.info("="*80)
    asyncio.run(test_simple_search_intent())
    
    # Test 2: Product selection
    logger.info("\n" + "="*80)
    logger.info("TEST 2: Product Selection")
    logger.info("="*80)
    asyncio.run(test_product_selection_intent())
    
    # Test 3: Full e-commerce flow
    logger.info("\n" + "="*80)
    logger.info("TEST 3: Full E-commerce Flow")
    logger.info("="*80)
    asyncio.run(test_lg_ecommerce_intent_based())
    
    logger.info("\n✅ All tests complete!")
