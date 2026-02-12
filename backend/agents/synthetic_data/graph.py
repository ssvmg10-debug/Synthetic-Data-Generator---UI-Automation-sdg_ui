"""
Synthetic Data LangGraph Workflow
Linear workflow: parse → crawl → merge → generate
"""
import logging
from langgraph.graph import StateGraph, END
from agents.synthetic_data.state import SyntheticDataState
from agents.synthetic_data.nodes import (
    parse_test_case_node,
    crawl_pages_node,
    merge_schemas_node,
    generate_data_node
)
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def create_synthetic_data_graph(db: Session):
    """
    Create the synthetic data generation workflow graph
    
    Workflow:
    START → parse_test_case → crawl_pages → merge_schemas → generate_data → END
    """
    
    # Create graph
    workflow = StateGraph(SyntheticDataState)
    
    # Add nodes
    workflow.add_node("parse_test_case", lambda state: parse_test_case_node(state, db))
    workflow.add_node("crawl_pages", lambda state: crawl_pages_node(state, db))
    workflow.add_node("merge_schemas", lambda state: merge_schemas_node(state, db))
    workflow.add_node("generate_data", lambda state: generate_data_node(state, db))
    
    # Define edges (linear flow)
    workflow.set_entry_point("parse_test_case")
    workflow.add_edge("parse_test_case", "crawl_pages")
    workflow.add_edge("crawl_pages", "merge_schemas")
    workflow.add_edge("merge_schemas", "generate_data")
    workflow.add_edge("generate_data", END)
    
    # Compile
    app = workflow.compile()
    
    logger.info("✅ Synthetic Data Graph compiled")
    
    return app


async def run_synthetic_data_workflow(test_case: str, num_rows: int, db: Session):
    """
    Execute the synthetic data generation workflow
    """
    logger.info("=" * 80)
    logger.info("🚀 STARTING SYNTHETIC DATA WORKFLOW")
    logger.info("=" * 80)
    
    # Create graph
    app = create_synthetic_data_graph(db)
    
    # Initial state
    initial_state: SyntheticDataState = {
        'test_case': test_case,
        'num_rows': num_rows,
        'urls': [],
        'crawled_schemas': {},
        'merged_schema': {},
        'generated_data': [],
        'schema_id': None,
        'run_id': None,
        'error': None,
        'current_step': 'parse_test_case',
        'thread_id': None
    }
    
    # Run workflow
    try:
        result = await app.ainvoke(initial_state)
        
        if result.get('error'):
            logger.error(f"❌ Workflow failed: {result['error']}")
            return {
                'status': 'failed',
                'error': result['error']
            }
        
        logger.info("=" * 80)
        logger.info("✅ WORKFLOW COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        
        return {
            'status': 'success',
            'run_id': result.get('run_id'),
            'schema_id': result.get('schema_id'),
            'generated_data': result.get('generated_data', [])
        }
        
    except Exception as e:
        logger.error(f"❌ Workflow error: {str(e)}")
        return {
            'status': 'error',
            'error': str(e)
        }
