"""
Intent System Initialization
Central module for importing all intent-based components
"""

# Intent models
from services.ui_automation.core.intent_models import (
    Intent,
    IntentType,
    IntentResult,
    PageState
)

# Planning
from services.ui_automation.core.intent_planner import IntentPlanner

# Execution
from services.ui_automation.core.intent_executor import (
    IntentExecutor,
    execute_test_case_with_intents
)

# Flow executors
from services.ui_automation.core.flow_router import FlowRouter
from services.ui_automation.core.flow_search import SearchFlowExecutor
from services.ui_automation.core.flow_product import ProductFlowExecutor
from services.ui_automation.core.flow_checkout import CheckoutFlowExecutor

# Supporting components
from services.ui_automation.core.state_validation import StateValidator
from services.ui_automation.core.cta_classifier import CTAClassifier
from services.ui_automation.core.controlled_resolver import ControlledSmartResolver

__all__ = [
    # Models
    "Intent",
    "IntentType",
    "IntentResult",
    "PageState",
    
    # Planning
    "IntentPlanner",
    
    # Execution
    "IntentExecutor",
    "execute_test_case_with_intents",
    
    # Flow routing
    "FlowRouter",
    "SearchFlowExecutor",
    "ProductFlowExecutor",
    "CheckoutFlowExecutor",
    
    # Supporting
    "StateValidator",
    "CTAClassifier",
    "ControlledSmartResolver",
]
