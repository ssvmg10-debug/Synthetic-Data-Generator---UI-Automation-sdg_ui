"""
UI Automation LangGraph Workflow
Workflow with self-healing loop: plan → generate → execute → monitor → heal → retry
"""
import logging
from langgraph.graph import StateGraph, END
from agents.ui_automation.state import UIAutomationState
from agents.ui_automation.nodes import (
    plan_test_node,
    generate_script_node,
    execute_test_node,
    monitor_execution_node,
    heal_failure_node,
    retry_execution_node
)
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def should_heal(state: UIAutomationState) -> str:
    """
    Conditional edge: Decide if healing is needed
    """
    current_step = state.get('current_step')
    execution_status = state.get('execution_status')
    healing_attempts = state.get('healing_attempts', 0)
    max_healing_attempts = state.get('max_healing_attempts', 3)
    
    # If complete, end workflow
    if current_step == 'complete':
        return "end"
    
    # If passed, end workflow
    if execution_status == 'passed':
        return "end"
    
    # If max healing attempts reached, end workflow
    if healing_attempts >= max_healing_attempts:
        return "end"
    
    # If failed and haven't exceeded max attempts, go to heal
    if execution_status == 'failed' and current_step == 'heal_failure':
        return "heal"
    
    # Otherwise, continue monitoring
    return "monitor"


def create_ui_automation_graph(db: Session):
    """
    Create the UI automation workflow graph with self-healing loop
    
    Workflow:
    START → plan_test → generate_script → execute_test → monitor_execution
                                                            ↓
                                            [failed] → heal_failure → retry_execution
                                                            ↑                ↓
                                                            ← ← ← [failed] ← 
                                            [passed or max attempts] → END
    """
    
    # Create graph
    workflow = StateGraph(UIAutomationState)
    
    # Add nodes
    workflow.add_node("plan_test", lambda state: plan_test_node(state, db))
    workflow.add_node("generate_script", lambda state: generate_script_node(state, db))
    workflow.add_node("execute_test", lambda state: execute_test_node(state, db))
    workflow.add_node("monitor_execution", lambda state: monitor_execution_node(state, db))
    workflow.add_node("heal_failure", lambda state: heal_failure_node(state, db))
    workflow.add_node("retry_execution", lambda state: retry_execution_node(state, db))
    
    # Define edges
    workflow.set_entry_point("plan_test")
    workflow.add_edge("plan_test", "generate_script")
    workflow.add_edge("generate_script", "execute_test")
    workflow.add_edge("execute_test", "monitor_execution")
    
    # Conditional edge: monitor → heal or end
    workflow.add_conditional_edges(
        "monitor_execution",
        lambda state: state.get('current_step'),
        {
            "heal_failure": "heal_failure",
            "complete": END
        }
    )
    
    # heal_failure → retry_execution
    workflow.add_edge("heal_failure", "retry_execution")
    
    # Conditional edge: retry → monitor (loop back) or end
    workflow.add_conditional_edges(
        "retry_execution",
        lambda state: state.get('current_step'),
        {
            "monitor_execution": "monitor_execution",
            "complete": END
        }
    )
    
    # Compile
    app = workflow.compile()
    
    logger.info("✅ UI Automation Graph with self-healing loop compiled")
    
    return app


async def run_ui_automation_workflow(test_case: str, db: Session, max_healing_attempts: int = 3):
    """
    Execute the UI automation workflow with self-healing
    """
    logger.info("=" * 80)
    logger.info("🚀 STARTING UI AUTOMATION WORKFLOW")
    logger.info("=" * 80)
    
    # Create graph
    app = create_ui_automation_graph(db)
    
    # Initial state
    initial_state: UIAutomationState = {
        'test_case': test_case,
        'max_healing_attempts': max_healing_attempts,
        'structured_plan': {},
        'playwright_script': "",
        'execution_status': 'pending',
        'healing_attempts': 0,
        'healed': False,
        'healing_history': [],
        'error': None,
        'last_error_locator': None,
        'current_step': 'plan_test',
        'thread_id': None,
        'testcase_id': None
    }
    
    # Run workflow
    try:
        result = await app.ainvoke(initial_state)
        
        execution_status = result.get('execution_status')
        healing_attempts = result.get('healing_attempts', 0)
        
        if execution_status == 'passed':
            logger.info("=" * 80)
            logger.info("✅ WORKFLOW COMPLETED - TEST PASSED")
            logger.info("=" * 80)
            
            return {
                'status': 'passed',
                'testcase_id': result.get('testcase_id'),
                'healing_attempts': healing_attempts,
                'healing_history': result.get('healing_history', []),
                'script': result.get('playwright_script')
            }
        else:
            logger.error("=" * 80)
            logger.error("❌ WORKFLOW FAILED - TEST FAILED")
            logger.error("=" * 80)
            
            return {
                'status': 'failed',
                'error': result.get('error'),
                'healing_attempts': healing_attempts,
                'healing_history': result.get('healing_history', [])
            }
        
    except Exception as e:
        logger.error(f"❌ Workflow error: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }
