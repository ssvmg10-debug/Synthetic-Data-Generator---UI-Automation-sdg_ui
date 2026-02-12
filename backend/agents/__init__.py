"""
Base Agent Module
Common utilities for all LangGraph agents
"""
from typing import TypedDict, Optional, List, Dict, Any
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph
import logging

logger = logging.getLogger(__name__)


class BaseAgentState(TypedDict):
    """Base state for all agents"""
    messages: List[BaseMessage]
    error: Optional[str]
    metadata: Dict[str, Any]


def log_node_entry(node_name: str, state: Dict[str, Any]):
    """Log when entering a node"""
    logger.info(f"🔹 Entering node: {node_name}")
    logger.debug(f"State keys: {list(state.keys())}")


def log_node_exit(node_name: str, result: Any):
    """Log when exiting a node"""
    logger.info(f"✅ Exiting node: {node_name}")
    if isinstance(result, dict) and 'error' in result:
        logger.error(f"❌ Error in {node_name}: {result['error']}")


# Export workflow runners
from agents.synthetic_data.graph import run_synthetic_data_workflow
from agents.ui_automation.graph import run_ui_automation_workflow

__all__ = [
    'BaseAgentState',
    'log_node_entry',
    'log_node_exit',
    'run_synthetic_data_workflow',
    'run_ui_automation_workflow'
]
