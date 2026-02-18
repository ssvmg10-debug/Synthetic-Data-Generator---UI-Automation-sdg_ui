"""
🚀 PHASE 1 — NORMALIZED TEST MODEL (JSON DSL)
Internal representation - no raw English reaches executor
"""
from enum import Enum
from typing import Optional, Literal, Dict, Any, List
from pydantic import BaseModel, Field


class StepType(str, Enum):
    """Step types - NEVER confuse actions with assertions"""
    NAVIGATION = "NAVIGATION"      # Navigate to URLs/pages
    ACTION = "ACTION"              # Click, select, interact
    INPUT = "INPUT"                # Type, fill forms
    ASSERTION = "ASSERTION"        # Verify state (NO UI action)
    WAIT = "WAIT"                  # Explicit waits
    CONDITIONAL = "CONDITIONAL"    # If/else logic
    UNKNOWN = "UNKNOWN"            # Unparseable - no CLICK fallback (Module 1)


class Intent(str, Enum):
    """Supported intents - semantic actions"""
    
    # Navigation intents
    GOTO = "GOTO"
    
    # Action intents
    CLICK = "CLICK"
    SELECT = "SELECT"
    SEARCH = "SEARCH"
    ADD_TO_CART = "ADD_TO_CART"
    BUY_NOW = "BUY_NOW"
    CHECKOUT = "CHECKOUT"
    CONTINUE_AS_GUEST = "CONTINUE_AS_GUEST"
    SUBMIT = "SUBMIT"
    SCROLL = "SCROLL"
    HOVER = "HOVER"
    
    # Input intents
    TYPE = "TYPE"
    FILL_FORM = "FILL_FORM"
    FILL_PINCODE = "FILL_PINCODE"
    FILL_EMAIL = "FILL_EMAIL"
    FILL_PHONE = "FILL_PHONE"
    SELECT_OPTION = "SELECT_OPTION"
    
    # Wait intents
    WAIT = "WAIT"
    WAIT_FOR_ELEMENT = "WAIT_FOR_ELEMENT"
    WAIT_FOR_NAVIGATION = "WAIT_FOR_NAVIGATION"
    
    # Assertion intents (NO UI ACTION - just validation)
    PAGE_LOADED = "PAGE_LOADED"
    ELEMENT_VISIBLE = "ELEMENT_VISIBLE"
    FILTER_APPLIED = "FILTER_APPLIED"
    DELIVERY_OPTIONS_LOADED = "DELIVERY_OPTIONS_LOADED"
    BUTTON_ENABLED = "BUTTON_ENABLED"
    ORDER_CONFIRMED = "ORDER_CONFIRMED"
    TEXT_CONTAINS = "TEXT_CONTAINS"
    URL_MATCHES = "URL_MATCHES"
    STATE_IS = "STATE_IS"
    UNKNOWN = "UNKNOWN"            # Unparseable - do not treat as CLICK


class PageState(str, Enum):
    """Page states for state machine validation"""
    HOME = "HOME"
    CATEGORY = "CATEGORY"
    PRODUCT_LIST = "PRODUCT_LIST"
    PRODUCT_DETAIL = "PRODUCT_DETAIL"
    CART = "CART"
    CHECKOUT = "CHECKOUT"
    BILLING = "BILLING"
    PAYMENT = "PAYMENT"
    CONFIRMATION = "CONFIRMATION"
    UNKNOWN = "UNKNOWN"


class TestStep(BaseModel):
    """
    Normalized test step - internal DSL
    
    ✅ This is what executor receives
    ❌ Never raw English
    """
    id: int = Field(..., description="Step sequence number")
    type: StepType = Field(..., description="Step type")
    intent: Intent = Field(..., description="Semantic intent")
    target: Optional[str] = Field(None, description="Element identifier (for actions)")
    value: Optional[str] = Field(None, description="Value (for inputs/assertions)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")
    
    # State validation
    required_state: Optional[PageState] = Field(None, description="Required state before execution")
    expected_state: Optional[PageState] = Field(None, description="Expected state after execution")
    
    # Retry/wait config
    max_retries: int = Field(default=1, description="Max retry attempts")
    timeout: int = Field(default=5000, description="Timeout in ms")
    
    class Config:
        use_enum_values = True
    
    def __repr__(self):
        parts = [f"{self.type}:{self.intent}"]
        if self.target:
            parts.append(f"target='{self.target}'")
        if self.value:
            parts.append(f"value='{self.value}'")
        return f"TestStep({', '.join(parts)})"


class TestCase(BaseModel):
    """Complete test case model"""
    id: str = Field(..., description="Test case ID")
    title: str = Field(..., description="Test case title")
    objective: Optional[str] = Field(None, description="Test objective")
    preconditions: Optional[List[str]] = Field(default_factory=list, description="Preconditions")
    test_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Test data")
    steps: List[TestStep] = Field(..., description="Ordered test steps")
    
    class Config:
        use_enum_values = True


# State transition rules
STATE_TRANSITIONS = {
    PageState.HOME: [PageState.CATEGORY, PageState.PRODUCT_LIST, PageState.HOME],
    PageState.CATEGORY: [PageState.PRODUCT_LIST, PageState.HOME],
    PageState.PRODUCT_LIST: [PageState.PRODUCT_DETAIL, PageState.PRODUCT_LIST, PageState.CATEGORY],
    PageState.PRODUCT_DETAIL: [PageState.CART, PageState.PRODUCT_DETAIL, PageState.PRODUCT_LIST],
    PageState.CART: [PageState.CHECKOUT, PageState.CART, PageState.PRODUCT_DETAIL],
    PageState.CHECKOUT: [PageState.BILLING, PageState.PAYMENT, PageState.CHECKOUT, PageState.CART],
    PageState.BILLING: [PageState.PAYMENT, PageState.BILLING, PageState.CHECKOUT],
    PageState.PAYMENT: [PageState.CONFIRMATION, PageState.PAYMENT, PageState.BILLING],
    PageState.CONFIRMATION: [PageState.CONFIRMATION, PageState.HOME],
}


def is_valid_state_transition(from_state: PageState, to_state: PageState) -> bool:
    """Validate if state transition is allowed"""
    if from_state == PageState.UNKNOWN or to_state == PageState.UNKNOWN:
        return True  # Allow unknown states (discovery mode)
    
    valid_transitions = STATE_TRANSITIONS.get(from_state, [])
    return to_state in valid_transitions


# Example usage:
"""
# ❌ OLD (Raw English)
steps = [
    "Click Air Solutions",
    "Verify homepage loaded",
    "Click buy now"
]

# ✅ NEW (Normalized DSL)
steps = [
    TestStep(
        id=1,
        type=StepType.ACTION,
        intent=Intent.CLICK,
        target="Air Solutions",
        required_state=PageState.HOME,
        expected_state=PageState.CATEGORY
    ),
    TestStep(
        id=2,
        type=StepType.ASSERTION,
        intent=Intent.PAGE_LOADED,
        value="category page",
        required_state=PageState.CATEGORY
    ),
    TestStep(
        id=3,
        type=StepType.ACTION,
        intent=Intent.BUY_NOW,
        required_state=PageState.PRODUCT_DETAIL,
        expected_state=PageState.CART
    )
]
"""
