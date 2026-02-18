"""
UI Automation Agent State Schema
"""
from typing import TypedDict, Optional, List, Dict, Any


class UIAutomationState(TypedDict):
    """State for UI automation workflow"""
    # Input
    test_case: str
    use_synthetic_data: bool
    synthetic_run_id: Optional[int]
    
    # Planning
    structured_plan: Dict[str, Any]
    test_case_id: Optional[int]
    testcase_id: Optional[int]  # DB id from generate_script (used by execute_test_node)

    # Script Generation
    playwright_script: str
    
    # Execution
    execution_status: str  # 'pending', 'running', 'success', 'failed'
    execution_result: Dict[str, Any]
    execution_id: Optional[int]
    
    # Self-Healing
    healing_attempts: int
    healed: bool
    healing_history: List[Dict[str, Any]]
    
    # Error handling
    error: Optional[str]
    last_error_locator: Optional[str]
    
    # Metadata
    current_step: str
    thread_id: str
