"""
Core deterministic execution kernel
Phase 1: Text-based automation (legacy)
Phase 2: Intent-based automation (production-grade architecture)
Phase 3: Deterministic execution (🔒 ENTERPRISE-GRADE - NEW!)
"""

# Legacy exports (Phase 1)
from services.ui_automation.core.executor import execute_instructions
from services.ui_automation.core.navigator import safe_navigate
from services.ui_automation.core.element_resolver import smart_click, smart_type

# Intent-based system (Phase 2)
from services.ui_automation.core.intent_system import (
    Intent,
    IntentType,
    IntentExecutor,
    execute_test_case_with_intents,
    FlowRouter,
    StateValidator,
    CTAClassifier,
)

# 🔒 DETERMINISTIC SYSTEM (Phase 3) - RECOMMENDED
from services.ui_automation.core.deterministic_api import (
    execute_deterministic_test,
    execute_deterministic_test_sync,
    DeterministicExecutor
)
from services.ui_automation.core.state_machine import (
    AppState,
    detect_state,
    validate_state_transition
)
from services.ui_automation.core.intent_dispatcher import IntentDispatcher

__all__ = [
    # Legacy
    "execute_instructions",
    "safe_navigate",
    "smart_click",
    "smart_type",
    
    # Intent system (Phase 2)
    "Intent",
    "IntentType",
    "IntentExecutor",
    "execute_test_case_with_intents",
    "FlowRouter",
    "StateValidator",
    "CTAClassifier",
    
    # 🔒 Deterministic system (Phase 3) - RECOMMENDED FOR NEW TESTS
    "execute_deterministic_test",
    "execute_deterministic_test_sync",
    "DeterministicExecutor",
    "AppState",
    "detect_state",
    "validate_state_transition",
    "IntentDispatcher",
]

