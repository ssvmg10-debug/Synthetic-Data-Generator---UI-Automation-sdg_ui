"""
LangGraph Integration Test
Test both workflows end-to-end
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db import DATABASE_URL
from agents.synthetic_data.graph import run_synthetic_data_workflow
from agents.ui_automation.graph import run_ui_automation_workflow
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_test_db():
    """Get test database session"""
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    return db


async def test_synthetic_data_workflow():
    """
    Test Synthetic Data Workflow
    """
    logger.info("="*80)
    logger.info("🧪 TEST 1: SYNTHETIC DATA WORKFLOW")
    logger.info("="*80)
    
    db = get_test_db()
    
    test_case = """
    Fill out the registration form at https://example.com/register with:
    - Full Name
    - Email Address
    - Phone Number
    - Age
    - Address
    Generate 5 rows of test data.
    """
    
    try:
        result = await run_synthetic_data_workflow(
            test_case=test_case,
            num_rows=5,
            db=db
        )
        
        if result['status'] == 'success':
            logger.info(f"✅ TEST PASSED")
            logger.info(f"   Run ID: {result['run_id']}")
            logger.info(f"   Schema ID: {result['schema_id']}")
            logger.info(f"   Rows Generated: {len(result['generated_data'])}")
            return True
        else:
            logger.error(f"❌ TEST FAILED: {result.get('error')}")
            return False
            
    except Exception as e:
        logger.error(f"❌ TEST ERROR: {str(e)}")
        return False
    finally:
        db.close()


async def test_ui_automation_workflow():
    """
    Test UI Automation Workflow with Self-Healing
    """
    logger.info("="*80)
    logger.info("🧪 TEST 2: UI AUTOMATION WORKFLOW (with self-healing)")
    logger.info("="*80)
    
    db = get_test_db()
    
    test_case = """
    Test Case: Login Functionality
    URL: https://practicetestautomation.com/practice-test-login/
    
    Steps:
    1. Navigate to the login page
    2. Enter username: student
    3. Enter password: Password123
    4. Click the login button
    5. Verify successful login
    """
    
    try:
        result = await run_ui_automation_workflow(
            test_case=test_case,
            db=db,
            max_healing_attempts=3
        )
        
        if result['status'] == 'passed':
            logger.info(f"✅ TEST PASSED")
            logger.info(f"   Test Case ID: {result['testcase_id']}")
            logger.info(f"   Healing Attempts: {result['healing_attempts']}")
            logger.info(f"   Healing History: {len(result['healing_history'])} events")
            return True
        elif result['status'] == 'failed':
            logger.warning(f"⚠️ TEST FAILED (but workflow completed)")
            logger.warning(f"   Error: {result.get('error')}")
            logger.warning(f"   Healing Attempts: {result['healing_attempts']}")
            return False  # Expected if test fails
        else:
            logger.error(f"❌ TEST ERROR: {result.get('error')}")
            return False
            
    except Exception as e:
        logger.error(f"❌ TEST ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


async def run_all_tests():
    """
    Run all integration tests
    """
    logger.info("="*80)
    logger.info("🚀 LANGGRAPH INTEGRATION TESTS")
    logger.info("="*80)
    
    results = {}
    
    # Test 1: Synthetic Data Workflow
    results['synthetic_data'] = await test_synthetic_data_workflow()
    
    logger.info("\n")
    
    # Test 2: UI Automation Workflow
    results['ui_automation'] = await test_ui_automation_workflow()
    
    # Summary
    logger.info("="*80)
    logger.info("📊 TEST SUMMARY")
    logger.info("="*80)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("="*80)
        logger.info("🎉 ALL TESTS PASSED")
        logger.info("="*80)
    else:
        logger.error("="*80)
        logger.error("❌ SOME TESTS FAILED")
        logger.error("="*80)
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
