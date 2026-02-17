"""
Intent Normalization Layer - Converts English steps to structured intents.

This is Layer 2 of the state-driven automation architecture.
Transforms natural language into domain-specific actions.
"""
import logging
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ActionIntent(Enum):
    """High-level action intents."""
    NAVIGATE = "navigate"
    SEARCH_PRODUCT = "search_product"
    FILTER_PRODUCTS = "filter_products"
    SELECT_PRODUCT = "select_product"
    BUY_PRODUCT = "buy_product"
    ADD_TO_CART = "add_to_cart"
    VIEW_CART = "view_cart"
    UPDATE_QUANTITY = "update_quantity"
    REMOVE_ITEM = "remove_item"
    APPLY_COUPON = "apply_coupon"
    CHECKOUT = "checkout"
    ENTER_SHIPPING_INFO = "enter_shipping_info"
    ENTER_BILLING_INFO = "enter_billing_info"
    SELECT_PAYMENT = "select_payment"
    LOGIN = "login"
    GUEST_CHECKOUT = "guest_checkout"
    VERIFY_DELIVERY = "verify_delivery"
    SELECT_DELIVERY_METHOD = "select_delivery_method"
    COMPARE_PRODUCTS = "compare_products"
    ADD_TO_WISHLIST = "add_to_wishlist"
    DOWNLOAD_DOCUMENT = "download_document"
    VIEW_WARRANTY = "view_warranty"
    CLICK_ELEMENT = "click_element"
    TYPE_TEXT = "type_text"
    SELECT_OPTION = "select_option"
    WAIT = "wait"


@dataclass
class NormalizedIntent:
    """Structured representation of user intent."""
    action: ActionIntent
    target: Optional[str] = None
    value: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None
    original_step: Optional[str] = None
    confidence: float = 1.0
    
    def __repr__(self):
        parts = [f"Intent({self.action.value}"]
        if self.target:
            parts.append(f"target='{self.target}'")
        if self.value:
            parts.append(f"value='{self.value}'")
        if self.constraints:
            parts.append(f"constraints={self.constraints}")
        return ", ".join(parts) + ")"


class IntentNormalizer:
    """
    Normalizes natural language steps into structured intents.
    
    This provides semantic understanding of what the user wants
    to accomplish, not just what to click.
    """
    
    # Intent patterns (regex patterns -> intent mapping)
    INTENT_PATTERNS = [
        # Navigation
        (r'(?:navigate|go|open|visit|browse)\s+(?:to|the)?\s*(.+)', ActionIntent.NAVIGATE),
        
        # Search
        (r'search\s+(?:for|product)?\s*["\']?([^"\']+)["\']?', ActionIntent.SEARCH_PRODUCT),
        (r'find\s+["\']?([^"\']+)["\']?', ActionIntent.SEARCH_PRODUCT),
        (r'look\s+for\s+["\']?([^"\']+)["\']?', ActionIntent.SEARCH_PRODUCT),
        
        # Product selection
        (r'(?:click|select|choose)\s+(?:on|the)?\s*product\s+["\']?([^"\']+)["\']?', ActionIntent.SELECT_PRODUCT),
        (r'select\s+["\']?([^"\']+)["\']?\s+(?:product|item)', ActionIntent.SELECT_PRODUCT),
        
        # Buy/Add to cart
        (r'(?:click|press)\s+(?:on\s+)?(?:buy\s*now|buynow)\s+(?:for|on)?\s*(?:product)?\s*["\']?([^"\']*)["\']?', ActionIntent.BUY_PRODUCT),
        (r'buy\s+(?:the\s+)?(?:product\s+)?["\']?([^"\']*)["\']?', ActionIntent.BUY_PRODUCT),
        (r'(?:add\s+to\s+cart|add\s+to\s+basket)\s+(?:for\s+)?["\']?([^"\']*)["\']?', ActionIntent.ADD_TO_CART),
        (r'purchase\s+["\']?([^"\']*)["\']?', ActionIntent.BUY_PRODUCT),
        
        # Cart operations
        (r'(?:view|open|go\s+to)\s+(?:the\s+)?cart', ActionIntent.VIEW_CART),
        (r'(?:change|update|set)\s+quantity\s+(?:to\s+)?(\d+)', ActionIntent.UPDATE_QUANTITY),
        (r'remove\s+(?:item|product)\s*["\']?([^"\']*)["\']?', ActionIntent.REMOVE_ITEM),
        
        # Coupon
        (r'(?:apply|enter|use)\s+(?:coupon|promo|discount)\s*["\']?([^"\']+)["\']?', ActionIntent.APPLY_COUPON),
        
        # Checkout
        (r'(?:checkout|proceed\s+to\s+checkout)', ActionIntent.CHECKOUT),
        (r'continue\s+as\s+guest', ActionIntent.GUEST_CHECKOUT),
        (r'(?:enter|fill|provide)\s+(?:shipping|delivery)\s+(?:address|info|details)', ActionIntent.ENTER_SHIPPING_INFO),
        (r'(?:enter|fill|provide)\s+billing\s+(?:address|info|details)', ActionIntent.ENTER_BILLING_INFO),
        
        # Delivery
        (r'(?:check|verify|enter)\s+(?:pincode|zipcode|postal\s*code)\s*["\']?([^"\']*)["\']?', ActionIntent.VERIFY_DELIVERY),
        (r'select\s+(?:free\s+)?delivery\s+(?:option|method)', ActionIntent.SELECT_DELIVERY_METHOD),
        
        # Filter
        (r'filter\s+by\s+(\w+)\s*["\']?([^"\']*)["\']?', ActionIntent.FILTER_PRODUCTS),
        (r'apply\s+filter\s+["\']?([^"\']+)["\']?', ActionIntent.FILTER_PRODUCTS),
        
        # Compare
        (r'compare\s+(?:products\s+)?["\']?([^"\']+)["\']?', ActionIntent.COMPARE_PRODUCTS),
        
        # Wishlist
        (r'(?:add\s+to\s+wishlist|wishlist)\s*["\']?([^"\']*)["\']?', ActionIntent.ADD_TO_WISHLIST),
        
        # Documents
        (r'download\s+(?:brochure|pdf|document|catalogue)\s*["\']?([^"\']*)["\']?', ActionIntent.DOWNLOAD_DOCUMENT),
        (r'(?:view|check)\s+warranty', ActionIntent.VIEW_WARRANTY),
        
        # Login
        (r'(?:login|log\s+in|sign\s+in)', ActionIntent.LOGIN),
        
        # Generic actions (fallback)
        (r'click\s+(?:on\s+)?["\']?([^"\']+)["\']?', ActionIntent.CLICK_ELEMENT),
        (r'type\s+["\']?([^"\']+)["\']?\s+(?:into|in)\s+["\']?([^"\']+)["\']?', ActionIntent.TYPE_TEXT),
        (r'enter\s+["\']?([^"\']+)["\']?\s+(?:into|in)\s+["\']?([^"\']+)["\']?', ActionIntent.TYPE_TEXT),
        (r'select\s+["\']?([^"\']+)["\']?', ActionIntent.SELECT_OPTION),
        (r'wait\s+(?:for\s+)?(\d+)?\s*(?:seconds?|ms)?', ActionIntent.WAIT),
    ]
    
    def __init__(self):
        self.compiled_patterns = [
            (re.compile(pattern, re.IGNORECASE), intent)
            for pattern, intent in self.INTENT_PATTERNS
        ]
    
    def normalize(self, step_description: str, step_data: Optional[Dict] = None) -> NormalizedIntent:
        """
        Normalize a natural language step into structured intent.
        
        Args:
            step_description: Natural language description of the step
            step_data: Optional structured data from planning phase
        
        Returns:
            NormalizedIntent with action, target, value, constraints
        """
        logger.info(f"🧠 Normalizing: '{step_description}'")
        
        step_clean = step_description.strip()
        
        # Try to match against known patterns
        for pattern, intent in self.compiled_patterns:
            match = pattern.search(step_clean)
            if match:
                normalized = self._build_intent(intent, match, step_data)
                normalized.original_step = step_description
                logger.info(f"✅ Normalized to: {normalized}")
                return normalized
        
        # Fallback: generic click
        logger.warning(f"⚠️ No pattern matched, using generic CLICK: {step_description}")
        return NormalizedIntent(
            action=ActionIntent.CLICK_ELEMENT,
            target=step_description,
            original_step=step_description,
            confidence=0.5
        )
    
    def _build_intent(
        self,
        action: ActionIntent,
        match: re.Match,
        step_data: Optional[Dict]
    ) -> NormalizedIntent:
        """Build intent from regex match and optional step data."""
        
        groups = match.groups()
        
        # Extract target and value based on action type
        target = None
        value = None
        constraints = {}
        
        if action == ActionIntent.NAVIGATE:
            target = groups[0] if groups else None
        
        elif action in [ActionIntent.SEARCH_PRODUCT, ActionIntent.SELECT_PRODUCT]:
            target = groups[0] if groups else None
        
        elif action in [ActionIntent.BUY_PRODUCT, ActionIntent.ADD_TO_CART]:
            target = groups[0] if groups and groups[0] else None
            # Extract product name from step data if available
            if step_data and "locator_hint" in step_data:
                hint = step_data["locator_hint"]
                if "product" in hint.lower():
                    target = hint
        
        elif action == ActionIntent.VERIFY_DELIVERY:
            value = groups[0] if groups else None
            target = "pincode"
        
        elif action == ActionIntent.UPDATE_QUANTITY:
            value = groups[0] if groups else None
            target = "quantity"
        
        elif action == ActionIntent.TYPE_TEXT:
            if len(groups) >= 2:
                value = groups[0]
                target = groups[1]
            elif len(groups) == 1:
                value = groups[0]
                # Try to extract from step_data
                if step_data and "locator_hint" in step_data:
                    target = step_data["locator_hint"]
        
        elif action == ActionIntent.CLICK_ELEMENT:
            target = groups[0] if groups else None
        
        elif action == ActionIntent.SELECT_OPTION:
            target = groups[0] if groups else None
        
        elif action == ActionIntent.FILTER_PRODUCTS:
            if len(groups) >= 2:
                constraints["filter_type"] = groups[0]
                constraints["filter_value"] = groups[1]
            elif len(groups) == 1:
                target = groups[0]
        
        elif action == ActionIntent.WAIT:
            value = groups[0] if groups else "2"
        
        # Merge with step_data if provided
        if step_data:
            if "action" in step_data and not target:
                target = step_data["action"]
            if "data" in step_data and not value:
                value = step_data.get("data")
            if "locator_hint" in step_data and not target:
                target = step_data["locator_hint"]
        
        return NormalizedIntent(
            action=action,
            target=target,
            value=value,
            constraints=constraints,
            confidence=0.9
        )
    
    def normalize_batch(self, steps: List[Dict]) -> List[NormalizedIntent]:
        """
        Normalize a batch of steps.
        
        Args:
            steps: List of step dictionaries with 'action' or 'description'
        
        Returns:
            List of normalized intents
        """
        intents = []
        for step in steps:
            description = step.get("action") or step.get("description", "")
            intent = self.normalize(description, step)
            intents.append(intent)
        
        logger.info(f"✅ Normalized {len(intents)} steps")
        return intents
    
    def should_scope_to_container(self, intent: NormalizedIntent) -> bool:
        """
        Determine if this intent should be scoped to a container.
        
        Returns:
            True if action should be scoped (e.g., product selection)
        """
        scoped_actions = [
            ActionIntent.SELECT_PRODUCT,
            ActionIntent.BUY_PRODUCT,
            ActionIntent.ADD_TO_CART,
            ActionIntent.REMOVE_ITEM,
            ActionIntent.COMPARE_PRODUCTS,
            ActionIntent.ADD_TO_WISHLIST,
        ]
        return intent.action in scoped_actions
    
    def get_expected_page_transition(self, intent: NormalizedIntent) -> Optional[str]:
        """
        Get expected page type after executing this intent.
        
        Returns:
            Expected PageType value or None
        """
        transitions = {
            ActionIntent.NAVIGATE: "HOME",
            ActionIntent.SEARCH_PRODUCT: "SEARCH_RESULTS",
            ActionIntent.SELECT_PRODUCT: "PRODUCT_DETAIL",
            ActionIntent.BUY_PRODUCT: "PRODUCT_DETAIL",  # Or CART
            ActionIntent.ADD_TO_CART: None,  # May stay on page or go to cart
            ActionIntent.VIEW_CART: "CART",
            ActionIntent.CHECKOUT: "CHECKOUT",
            ActionIntent.LOGIN: "LOGIN",
        }
        return transitions.get(intent.action)
