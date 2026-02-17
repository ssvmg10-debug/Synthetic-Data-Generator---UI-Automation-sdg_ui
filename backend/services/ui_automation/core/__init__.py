"""
Core deterministic execution kernel
Phase 1: Text-based automation (legacy)
Phase 2: Intent-based automation (new production-grade architecture)
"""

# Legacy exports (Phase 1)
from services.ui_automation.core.executor import execute_instructions
from services.ui_automation.core.navigator import safe_navigate
from services.ui_automation.core.element_resolver import smart_click, smart_type

# New intent-based system (Phase 2)
from services.ui_automation.core.intent_system import (
    Intent,
    IntentType,
    IntentExecutor,
    execute_test_case_with_intents,
    FlowRouter,
    StateValidator,
    CTAClassifier,
)

__all__ = [
    # Legacy
    "execute_instructions",
    "safe_navigate",
    "smart_click",
    "smart_type",
    
    # Intent system
    "Intent",
    "IntentType",
    "IntentExecutor",
    "execute_test_case_with_intents",
    "FlowRouter",
    "StateValidator",
    "CTAClassifier",
]

