"""
Flow Router
Routes intents to appropriate flow executors or resolvers
"""
import logging
import time
from playwright.async_api import Page
from typing import Optional
from services.ui_automation.core.intent_models import Intent, IntentType, IntentResult, PageState
from services.ui_automation.core.state_validation import StateValidator
from services.ui_automation.core.flow_search import SearchFlowExecutor
from services.ui_automation.core.flow_product import ProductFlowExecutor
from services.ui_automation.core.flow_checkout import CheckoutFlowExecutor
from services.ui_automation.core.controlled_resolver import ControlledSmartResolver
from services.ui_automation.core.navigator import safe_navigate

logger = logging.getLogger(__name__)


class FlowRouter:
    """
    Routes intents to specialized flow executors.
    
    Architecture:
    Intent → Flow Executor → State Validation → Retry (if needed) → Result
    
    Flow executors:
    - SearchFlowExecutor: Search and filter
    - ProductFlowExecutor: Product selection, add to cart
    - CheckoutFlowExecutor: Checkout, pincode, delivery
    
    Fallback:
    - ControlledSmartResolver: Generic element resolution with limits
    """
    
    def __init__(self):
        self.state_validator = StateValidator()
        self.search_flow = SearchFlowExecutor()
        self.product_flow = ProductFlowExecutor()
        self.checkout_flow = CheckoutFlowExecutor()
        self.resolver = ControlledSmartResolver()
    
    async def execute_intent(self, page: Page, intent: Intent, retry_on_failure: bool = True) -> IntentResult:
        """
        Execute single intent with appropriate flow executor.
        
        Args:
            page: Playwright page
            intent: Intent to execute
            retry_on_failure: Whether to retry once on failure
        
        Returns:
            IntentResult with execution details
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🎯 Executing: {intent}")
        logger.info(f"{'='*60}")
        
        start_time = time.time()
        
        try:
            # Route to appropriate executor
            success = await self._route_intent(page, intent)
            
            if not success and retry_on_failure:
                logger.warning("⚠️  First attempt failed, retrying with alternate strategy...")
                success = await self._retry_with_alternate(page, intent)
            
            execution_time = time.time() - start_time
            
            # Validate state if expected_state provided
            state_validated = True
            if success and intent.expected_state:
                state_validated = await self.state_validator.validate_state(
                    page,
                    PageState[intent.expected_state]
                )
            
            result = IntentResult(
                success=success,
                intent=intent,
                execution_time=execution_time,
                state_validated=state_validated,
                retry_attempted=not success and retry_on_failure
            )
            
            if success:
                logger.info(f"✅ Intent succeeded ({execution_time:.2f}s)")
            else:
                logger.error(f"❌ Intent failed ({execution_time:.2f}s)")
                result.error = "Intent execution failed"
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"❌ Intent error: {e}")
            
            return IntentResult(
                success=False,
                intent=intent,
                execution_time=execution_time,
                state_validated=False,
                error=str(e)
            )
    
    async def _route_intent(self, page: Page, intent: Intent) -> bool:
        """
        Route intent to appropriate executor.
        
        Returns:
            True if succeeded
        """
        intent_type = intent.intent if isinstance(intent.intent, IntentType) else IntentType[intent.intent]
        
        # Navigation
        if intent_type == IntentType.NAVIGATE:
            await safe_navigate(page, intent.url)
            return True
        
        # Search flow
        elif intent_type == IntentType.SEARCH_PRODUCT:
            return await self.search_flow.execute_search(page, intent)
        
        elif intent_type == IntentType.FILTER_RESULTS:
            return await self.search_flow.execute_filter(page, intent)
        
        # Product flow
        elif intent_type == IntentType.SELECT_PRODUCT:
            return await self.product_flow.execute_select_product(page, intent)
        
        elif intent_type == IntentType.ADD_TO_CART:
            return await self.product_flow.execute_add_to_cart(page, intent)
        
        elif intent_type == IntentType.VIEW_CART:
            return await self.product_flow.execute_view_cart(page, intent)
        
        # Checkout flow
        elif intent_type == IntentType.PROCEED_TO_CHECKOUT:
            return await self.checkout_flow.execute_proceed_to_checkout(page, intent)
        
        elif intent_type == IntentType.SET_PINCODE:
            return await self.checkout_flow.execute_set_pincode(page, intent)
        
        elif intent_type == IntentType.SELECT_DELIVERY_OPTION:
            return await self.checkout_flow.execute_select_delivery_option(page, intent)
        
        elif intent_type == IntentType.SELECT_PAYMENT_METHOD:
            return await self.checkout_flow.execute_select_payment_method(page, intent)
        
        # Generic intents (fallback to resolver)
        elif intent_type == IntentType.CLICK_ELEMENT:
            return await self.resolver.resolve_click(page, intent.element_text or intent.value)
        
        elif intent_type == IntentType.TYPE_TEXT:
            return await self.resolver.resolve_type(page, intent.field_name, intent.value)
        
        else:
            logger.warning(f"No executor for intent type: {intent_type}")
            return False
    
    async def _retry_with_alternate(self, page: Page, intent: Intent) -> bool:
        """
        Retry intent with alternate strategy (controlled resolver).
        
        Returns:
            True if succeeded
        """
        intent_type = intent.intent if isinstance(intent.intent, IntentType) else IntentType[intent.intent]
        
        # For failed flow intents, try generic resolver
        if intent_type in [IntentType.ADD_TO_CART, IntentType.PROCEED_TO_CHECKOUT]:
            # Try clicking by text
            target_text = intent.element_text or "Buy Now" if intent_type == IntentType.ADD_TO_CART else "Checkout"
            return await self.resolver.resolve_click(page, target_text)
        
        elif intent_type == IntentType.SET_PINCODE:
            # Try typing into any visible input
            return await self.resolver.resolve_type(page, "pincode", intent.value)
        
        # No alternate strategy
        return False
