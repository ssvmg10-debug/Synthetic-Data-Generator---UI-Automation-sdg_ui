"""
Synthetic Data Agent State Schema
"""
from typing import TypedDict, Optional, List, Dict, Any


class SyntheticDataState(TypedDict):
    """State for synthetic data generation workflow"""
    # Input
    test_case: str
    num_rows: int
    
    # Intermediate
    urls: List[str]
    crawled_schemas: Dict[str, Any]
    merged_schema: Dict[str, Any]
    
    # Output
    generated_data: List[Dict[str, Any]]
    run_id: Optional[int]
    schema_id: Optional[int]
    
    # Error handling
    error: Optional[str]
    
    # Metadata
    current_step: str
    thread_id: str
