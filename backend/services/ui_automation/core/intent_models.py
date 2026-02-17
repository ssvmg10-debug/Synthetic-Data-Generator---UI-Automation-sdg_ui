"""
Intent-Based Semantic Models
Production-grade intent definitions for UI automation
"""
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class IntentType(str, Enum):
    """Semantic intent types - replacing text-based actions"""
    # Navigation
    NAVIGATE = "NAVIGATE"
    
    # Search intents
    SEARCH_PRODUCT = "SEARCH_PRODUCT"
    FILTER_RESULTS = "FILTER_RESULTS"
    
    # Product intents
    SELECT_PRODUCT = "SELECT_PRODUCT"
    VIEW_PRODUCT_DETAILS = "VIEW_PRODUCT_DETAILS"
    ADD_TO_CART = "ADD_TO_CART"
    
    # Cart intents
    VIEW_CART = "VIEW_CART"
    UPDATE_QUANTITY = "UPDATE_QUANTITY"
    REMOVE_FROM_CART = "REMOVE_FROM_CART"
    
    # Checkout intents
    PROCEED_TO_CHECKOUT = "PROCEED_TO_CHECKOUT"
    SET_DELIVERY_ADDRESS = "SET_DELIVERY_ADDRESS"
    SET_PINCODE = "SET_PINCODE"
    SELECT_DELIVERY_OPTION = "SELECT_DELIVERY_OPTION"
    SELECT_PAYMENT_METHOD = "SELECT_PAYMENT_METHOD"
    COMPLETE_PAYMENT = "COMPLETE_PAYMENT"
    
    # Form intents
    FILL_FORM_FIELD = "FILL_FORM_FIELD"
    SUBMIT_FORM = "SUBMIT_FORM"
    
    # Authentication intents
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    REGISTER = "REGISTER"
    
    # Generic intents
    CLICK_ELEMENT = "CLICK_ELEMENT"
    TYPE_TEXT = "TYPE_TEXT"
    SELECT_OPTION = "SELECT_OPTION"
    VERIFY_TEXT = "VERIFY_TEXT"
    WAIT_FOR_ELEMENT = "WAIT_FOR_ELEMENT"


class Intent(BaseModel):
    """
    Structured intent model replacing text-based instructions.
    
    Examples:
        Intent(intent=IntentType.SEARCH_PRODUCT, query="lg 108cm tv")
        Intent(intent=IntentType.SELECT_PRODUCT, product_name="LG 4 Star Split AC")
        Intent(intent=IntentType.SET_PINCODE, value="500032")
    """
    intent: IntentType = Field(..., description="Semantic intent type")
    
    # Common parameters
    query: Optional[str] = Field(None, description="Search query")
    value: Optional[str] = Field(None, description="Input value")
    product_name: Optional[str] = Field(None, description="Product name for matching")
    option: Optional[str] = Field(None, description="Option to select")
    url: Optional[str] = Field(None, description="URL for navigation")
    
    # Form field specifics
    field_name: Optional[str] = Field(None, description="Form field name")
    field_type: Optional[str] = Field(None, description="Field type (text, email, etc)")
    
    # Element targeting (fallback)
    element_text: Optional[str] = Field(None, description="Element text to find")
    selector: Optional[str] = Field(None, description="CSS/XPath selector (fallback)")
    
    # Validation
    expected_state: Optional[str] = Field(None, description="Expected state after intent")
    timeout: int = Field(10000, description="Timeout in milliseconds")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    
    class Config:
        use_enum_values = True
    
    def __str__(self) -> str:
        parts = [f"Intent: {self.intent}"]
        if self.query:
            parts.append(f"query='{self.query}'")
        if self.value:
            parts.append(f"value='{self.value}'")
        if self.product_name:
            parts.append(f"product='{self.product_name}'")
        if self.option:
            parts.append(f"option='{self.option}'")
        return " | ".join(parts)


class IntentResult(BaseModel):
    """Result of intent execution"""
    success: bool = Field(..., description="Whether intent succeeded")
    intent: Intent = Field(..., description="The executed intent")
    phase_used: Optional[str] = Field(None, description="Which phase succeeded (flow/resolver/healing)")
    execution_time: float = Field(..., description="Execution time in seconds")
    state_validated: bool = Field(False, description="Whether state validation passed")
    error: Optional[str] = Field(None, description="Error message if failed")
    retry_attempted: bool = Field(False, description="Whether retry was attempted")
    
    class Config:
        use_enum_values = True


class PageState(str, Enum):
    """Expected page states after intents"""
    SEARCH_RESULTS_LOADED = "SEARCH_RESULTS_LOADED"
    PRODUCT_PAGE_LOADED = "PRODUCT_PAGE_LOADED"
    CART_UPDATED = "CART_UPDATED"
    CHECKOUT_PAGE_LOADED = "CHECKOUT_PAGE_LOADED"
    PAYMENT_PAGE_LOADED = "PAYMENT_PAGE_LOADED"
    ORDER_CONFIRMED = "ORDER_CONFIRMED"
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    FORM_SUBMITTED = "FORM_SUBMITTED"
    MODAL_OPENED = "MODAL_OPENED"
    MODAL_CLOSED = "MODAL_CLOSED"
