"""
UI Automation Agent Nodes
LangGraph nodes that wrap existing Playwright agents
"""
import logging
import json
from typing import Dict, Any
from sqlalchemy.orm import Session
from agents.ui_automation.state import UIAutomationState
from services.ui_automation.agents.planner.agent import PlannerAgent
from services.ui_automation.agents.generator.agent import GeneratorAgent
from services.ui_automation.agents.validator.agent import ValidatorAgent
from services.ui_automation.agents.healer.agent import HealerAgent
from services.ui_automation.engine.executor import PlaywrightExecutor
from models import UITestCase, HealingHistory, WorkflowExecution

logger = logging.getLogger(__name__)


def plan_test_node(state: UIAutomationState, db: Session) -> Dict[str, Any]:
    """
    Node 1: Plan test case using PlannerAgent
    """
    logger.info("================================================================================")
    logger.info("🔹 NODE 1: PLAN TEST")
    logger.info("================================================================================")
    
    test_case = state['test_case']
    logger.info(f"📝 Input Test Case: {test_case[:100]}...")
    
    try:
        planner = PlannerAgent()
        structured_plan = planner.plan(test_case)
        
        logger.info("✅ Test plan generated")
        logger.info(f"📋 Steps: {len(structured_plan.get('steps', []))}")
        
        return {
            **state,
            'structured_plan': structured_plan,
            'current_step': 'generate_script'
        }
        
    except Exception as e:
        logger.error(f"❌ Planning failed: {str(e)}")
        return {
            **state,
            'error': f"Planning failed: {str(e)}",
            'execution_status': 'failed'
        }


def generate_script_node(state: UIAutomationState, db: Session) -> Dict[str, Any]:
    """
    Node 2: Generate Playwright script using GeneratorAgent
    """
    logger.info("================================================================================")
    logger.info("🔹 NODE 2: GENERATE PLAYWRIGHT SCRIPT")
    logger.info("================================================================================")
    
    structured_plan = state['structured_plan']
    
    try:
        app_config = None
        try:
            from config.app_config import get_app_config_for_url
            plan_url = (structured_plan or {}).get("url") or ""
            app_config = get_app_config_for_url(plan_url)
        except Exception:
            pass
        generator = GeneratorAgent()
        ake_script = None
        try:
            from services.ui_automation.ake import get_ake_script
            ake_script = get_ake_script()
        except Exception:
            pass
        playwright_script = generator.generate(structured_plan, ake_script=ake_script, db=db, app_config=app_config)
        
        logger.info("✅ Playwright script generated")
        logger.info(f"📄 Script length: {len(playwright_script)} chars")
        
        # Save test case (model: raw_input, structured_json, script JSON)
        db_testcase = UITestCase(
            raw_input=state["test_case"],
            structured_json=structured_plan,
            script={"language": "javascript", "content": playwright_script},
        )
        db.add(db_testcase)
        db.commit()
        db.refresh(db_testcase)
        
        logger.info(f"💾 Test case saved with ID: {db_testcase.id}")
        
        return {
            **state,
            'playwright_script': playwright_script,
            'testcase_id': db_testcase.id,
            'current_step': 'execute_test'
        }
        
    except Exception as e:
        logger.error(f"❌ Script generation failed: {str(e)}")
        return {
            **state,
            'error': f"Script generation failed: {str(e)}",
            'execution_status': 'failed'
        }


def execute_test_node(state: UIAutomationState, db: Session) -> Dict[str, Any]:
    """
    Node 3: Execute Playwright script
    """
    logger.info("================================================================================")
    logger.info("🔹 NODE 3: EXECUTE TEST")
    logger.info("================================================================================")
    
    playwright_script = state["playwright_script"]
    testcase_id = state.get("testcase_id")
    test_case_id_for_run = testcase_id if testcase_id is not None else 0
    if test_case_id_for_run == 0 and (state.get("structured_plan") or state.get("playwright_script")):
        logger.warning("testcase_id missing in state (using 0); execution will use run_0")

    try:
        executor = PlaywrightExecutor()
        result = executor.execute(playwright_script, test_case_id=test_case_id_for_run)
        success = result.get("status") == "passed"

        if success:
            logger.info("Test execution PASSED")
            
            # Update test case status
            if testcase_id:
                db_testcase = db.query(UITestCase).filter(UITestCase.id == testcase_id).first()
                if db_testcase:
                    db.commit()
            
            return {
                **state,
                'execution_status': 'passed',
                'logs': result.get("logs"),
                'logs_path': result.get("logs_path"),
                'screenshot_path': result.get("screenshot_path"),
                'step_screenshots': result.get("step_screenshots", []),
                'current_step': 'complete'
            }
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.warning(f"⚠️ Test execution FAILED: {error_msg}")
            failed_locator = result.get('failed_selector') or extract_failed_locator(error_msg)
            return {
                **state,
                'execution_status': 'failed',
                'error': error_msg,
                'last_error_locator': failed_locator,
                'failed_step_index': result.get('failed_step_index'),
                'failure_url': result.get('failure_url'),
                'failure_page_elements': result.get('failure_page_elements'),
                'logs': result.get("logs"),
                'logs_path': result.get("logs_path"),
                'screenshot_path': result.get("screenshot_path"),
                'step_screenshots': result.get("step_screenshots", []),
                'current_step': 'monitor_execution'
            }
        
    except Exception as e:
        logger.error(f"❌ Test execution error: {str(e)}")
        return {
            **state,
            'execution_status': 'failed',
            'error': str(e),
            'logs': None,
            'logs_path': None,
            'current_step': 'monitor_execution'
        }


def monitor_execution_node(state: UIAutomationState, db: Session) -> Dict[str, Any]:
    """
    Node 4: Monitor execution and decide next action
    """
    logger.info("================================================================================")
    logger.info("🔹 NODE 4: MONITOR EXECUTION")
    logger.info("================================================================================")
    
    execution_status = state.get('execution_status')
    healing_attempts = state.get('healing_attempts', 0)
    max_healing_attempts = state.get('max_healing_attempts', 3)
    
    if execution_status == 'passed':
        logger.info("✅ Test passed - workflow complete")
        return {
            **state,
            'current_step': 'complete'
        }
    
    if healing_attempts >= max_healing_attempts:
        logger.error(f"❌ Max healing attempts ({max_healing_attempts}) reached")
        return {
            **state,
            'execution_status': 'failed',
            'current_step': 'complete'
        }
    
    logger.info(f"🔧 Test failed - attempting heal (attempt {healing_attempts + 1}/{max_healing_attempts})")
    
    return {
        **state,
        'current_step': 'heal_failure'
    }


def heal_failure_node(state: UIAutomationState, db: Session) -> Dict[str, Any]:
    """
    Node 5: Heal failed locators using HealerAgent (CRITICAL)
    """
    logger.info("================================================================================")
    logger.info("🔹 NODE 5: HEAL FAILURE (SELF-HEALING)")
    logger.info("================================================================================")
    
    playwright_script = state['playwright_script']
    error = state.get('error', '')
    failed_locator = state.get('last_error_locator', '')
    healing_attempts = state.get('healing_attempts', 0)
    
    logger.info(f"🩺 Healing attempt {healing_attempts + 1}")
    logger.info(f"❌ Failed locator: {failed_locator}")
    
    try:
        healer = HealerAgent()
        plan = state.get('structured_plan')
        healing_result = healer.heal(
            script=playwright_script,
            error=error,
            db=db,
            failed_locator=failed_locator,
            plan=plan,
            failed_step_index=state.get('failed_step_index'),
            steps_before_failure=plan.get("steps", [])[: (state.get('failed_step_index') or 1) - 1] if plan else None,
            failure_url=state.get('failure_url'),
            failure_page_elements=state.get('failure_page_elements'),
        )
        
        healed_script = healing_result.get('healed_script')
        healed_locator = healing_result.get('healed_locator')
        strategy = healing_result.get('strategy', 'unknown')
        confidence = healing_result.get('confidence', 0.0)
        
        if not healed_script:
            logger.error("❌ Healing failed - no healed script returned")
            return {
                **state,
                'healed': False,
                'healing_attempts': healing_attempts + 1,
                'current_step': 'monitor_execution'
            }
        
        logger.info(f"✅ Healing successful")
        logger.info(f"🔧 Strategy: {strategy}")
        logger.info(f"📊 Confidence: {confidence}")
        logger.info(f"🆕 Healed locator: {healed_locator}")
        
        # Save healing history when we have an execution_id (set by router after run)
        execution_id = state.get('execution_id')
        if execution_id is not None:
            healing_history_entry = HealingHistory(
                execution_id=execution_id,
                failed_locator=failed_locator,
                healed_locator=healed_locator,
                strategy_used=strategy,
                success=1,
                confidence_score=int(confidence * 100) if isinstance(confidence, float) else confidence,
            )
            db.add(healing_history_entry)
            db.commit()
        
        # Update healing history in state
        healing_history = state.get('healing_history', [])
        healing_history.append({
            'attempt': healing_attempts + 1,
            'failed_locator': failed_locator,
            'healed_locator': healed_locator,
            'strategy': strategy,
            'confidence': confidence
        })
        
        return {
            **state,
            'playwright_script': healed_script,
            'healed': True,
            'healing_attempts': healing_attempts + 1,
            'healing_history': healing_history,
            'current_step': 'retry_execution'
        }
        
    except Exception as e:
        logger.error(f"❌ Healing error: {str(e)}")
        return {
            **state,
            'healed': False,
            'healing_attempts': healing_attempts + 1,
            'current_step': 'monitor_execution'
        }


def retry_execution_node(state: UIAutomationState, db: Session) -> Dict[str, Any]:
    """
    Node 6: Retry execution with healed script
    """
    logger.info("================================================================================")
    logger.info("🔹 NODE 6: RETRY EXECUTION")
    logger.info("================================================================================")
    
    playwright_script = state['playwright_script']
    
    logger.info("Retrying with healed script...")

    try:
        executor = PlaywrightExecutor()
        result = executor.execute(playwright_script, test_case_id=state.get("testcase_id") or 0)
        success = result.get("status") == "passed"

        if success:
            logger.info("Retry PASSED - healing successful!")
            
            # Update test case status
            testcase_id = state.get('testcase_id')
            if testcase_id:
                db_testcase = db.query(UITestCase).filter(UITestCase.id == testcase_id).first()
                if db_testcase:
                    db_testcase.script = {"language": "javascript", "content": playwright_script}
                    db.commit()
            
            return {
                **state,
                'execution_status': 'passed',
                'current_step': 'complete'
            }
        else:
            error_msg = result.get('error', 'Unknown error')
            logger.warning(f"⚠️ Retry FAILED: {error_msg}")
            
            # Extract new failed locator
            failed_locator = extract_failed_locator(error_msg)
            
            return {
                **state,
                'execution_status': 'failed',
                'error': error_msg,
                'last_error_locator': failed_locator,
                'current_step': 'monitor_execution'
            }
        
    except Exception as e:
        logger.error(f"❌ Retry execution error: {str(e)}")
        return {
            **state,
            'execution_status': 'failed',
            'error': str(e),
            'current_step': 'monitor_execution'
        }


# Utility functions
def extract_failed_locator(error_message: str) -> str:
    """
    Extract failed locator from error message
    """
    # Common patterns:
    # - "locator.click: Timeout waiting for selector 'button#submit'"
    # - "Element not found: #username"
    # - "Unable to find element with selector 'input[name="email"]'"
    
    import re
    
    patterns = [
        r"selector ['\"](.*?)['\"]",
        r"Element not found: (.*?)(?:\s|$)",
        r"with selector ['\"](.*?)['\"]"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, error_message)
        if match:
            return match.group(1)
    
    return ""
