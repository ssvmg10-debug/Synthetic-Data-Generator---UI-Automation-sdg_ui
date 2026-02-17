"""
Goal Validator - Validates expected outcomes after action execution.

Ensures actions actually achieved their intended goal, not just executed mechanically.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Callable
from enum import Enum
import logging
import re

from .page_state_extractor import PageState

logger = logging.getLogger(__name__)


class GoalType(Enum):
    """Types of goals to validate."""
    URL_CHANGED = "url_changed"
    CART_UPDATED = "cart_updated"
    RESULTS_VISIBLE = "results_visible"
    MODAL_OPENED = "modal_opened"
    MODAL_CLOSED = "modal_closed"
    PAGE_LOADED = "page_loaded"
    ELEMENT_VISIBLE = "element_visible"
    TEXT_APPEARED = "text_appeared"
    NAVIGATION_OCCURRED = "navigation_occurred"
    FORM_SUBMITTED = "form_submitted"
    PRODUCT_SELECTED = "product_selected"
    CHECKOUT_STARTED = "checkout_started"
    NO_CHANGE = "no_change"


@dataclass
class Goal:
    """Represents an expected outcome."""
    goal_type: GoalType
    description: str
    validation_fn: Optional[Callable] = None
    expected_value: Optional[any] = None
    timeout_ms: int = 5000


@dataclass
class ValidationResult:
    """Result of goal validation."""
    success: bool
    goal: Goal
    message: str
    actual_value: Optional[any] = None
    confidence: float = 1.0  # 0.0 to 1.0


class GoalValidator:
    """
    Validates that actions achieved their intended goals.
    
    Prevents blind progression - ensures each step actually worked.
    """
    
    def __init__(self):
        self.validation_history: List[ValidationResult] = []
        
    async def validate(
        self, 
        goal: Goal, 
        before_state: PageState, 
        after_state: PageState
    ) -> ValidationResult:
        """
        Validate that a goal was achieved.
        
        Args:
            goal: The expected outcome
            before_state: Page state before action
            after_state: Page state after action
            
        Returns:
            ValidationResult with success/failure
        """
        logger.info(f"🎯 Validating goal: {goal.description}")
        
        try:
            # Route to specific validator
            if goal.goal_type == GoalType.URL_CHANGED:
                result = self._validate_url_changed(goal, before_state, after_state)
            elif goal.goal_type == GoalType.CART_UPDATED:
                result = self._validate_cart_updated(goal, before_state, after_state)
            elif goal.goal_type == GoalType.RESULTS_VISIBLE:
                result = self._validate_results_visible(goal, after_state)
            elif goal.goal_type == GoalType.MODAL_OPENED:
                result = self._validate_modal_opened(goal, before_state, after_state)
            elif goal.goal_type == GoalType.MODAL_CLOSED:
                result = self._validate_modal_closed(goal, before_state, after_state)
            elif goal.goal_type == GoalType.PAGE_LOADED:
                result = self._validate_page_loaded(goal, after_state)
            elif goal.goal_type == GoalType.TEXT_APPEARED:
                result = self._validate_text_appeared(goal, before_state, after_state)
            elif goal.goal_type == GoalType.NAVIGATION_OCCURRED:
                result = self._validate_navigation(goal, before_state, after_state)
            elif goal.goal_type == GoalType.PRODUCT_SELECTED:
                result = self._validate_product_selected(goal, before_state, after_state)
            elif goal.goal_type == GoalType.CHECKOUT_STARTED:
                result = self._validate_checkout_started(goal, after_state)
            elif goal.goal_type == GoalType.NO_CHANGE:
                result = ValidationResult(
                    success=True,
                    goal=goal,
                    message="No change expected (wait/delay)",
                    confidence=1.0
                )
            else:
                # Custom validation function
                if goal.validation_fn:
                    custom_result = await goal.validation_fn(before_state, after_state)
                    result = ValidationResult(
                        success=custom_result,
                        goal=goal,
                        message="Custom validation " + ("passed" if custom_result else "failed"),
                        confidence=0.8
                    )
                else:
                    result = ValidationResult(
                        success=False,
                        goal=goal,
                        message=f"Unsupported goal type: {goal.goal_type}",
                        confidence=0.0
                    )
            
            # Log result
            if result.success:
                logger.info(f"✅ Goal validated: {result.message}")
            else:
                logger.warning(f"❌ Goal validation failed: {result.message}")
            
            # Store in history
            self.validation_history.append(result)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Validation error: {e}")
            result = ValidationResult(
                success=False,
                goal=goal,
                message=f"Validation exception: {str(e)}",
                confidence=0.0
            )
            self.validation_history.append(result)
            return result
    
    def _validate_url_changed(self, goal: Goal, before: PageState, after: PageState) -> ValidationResult:
        """Validate that URL changed."""
        if before.url != after.url:
            return ValidationResult(
                success=True,
                goal=goal,
                message=f"URL changed: {before.url} → {after.url}",
                actual_value=after.url,
                confidence=1.0
            )
        else:
            return ValidationResult(
                success=False,
                goal=goal,
                message="URL did not change",
                actual_value=after.url,
                confidence=1.0
            )
    
    def _validate_cart_updated(self, goal: Goal, before: PageState, after: PageState) -> ValidationResult:
        """Validate that cart count increased."""
        if after.cart_count > before.cart_count:
            return ValidationResult(
                success=True,
                goal=goal,
                message=f"Cart updated: {before.cart_count} → {after.cart_count}",
                actual_value=after.cart_count,
                confidence=1.0
            )
        elif after.cart_count == before.cart_count and after.cart_count > 0:
            # Cart might already contain item
            return ValidationResult(
                success=True,
                goal=goal,
                message=f"Cart unchanged but not empty: {after.cart_count}",
                actual_value=after.cart_count,
                confidence=0.7
            )
        else:
            return ValidationResult(
                success=False,
                goal=goal,
                message=f"Cart not updated: {before.cart_count} → {after.cart_count}",
                actual_value=after.cart_count,
                confidence=1.0
            )
    
    def _validate_results_visible(self, goal: Goal, after: PageState) -> ValidationResult:
        """Validate that search results are visible."""
        if after.has_search_results:
            return ValidationResult(
                success=True,
                goal=goal,
                message="Search results visible",
                confidence=0.9
            )
        elif after.product_count > 0:
            return ValidationResult(
                success=True,
                goal=goal,
                message=f"Products visible: {after.product_count}",
                actual_value=after.product_count,
                confidence=0.8
            )
        else:
            return ValidationResult(
                success=False,
                goal=goal,
                message="No search results visible",
                confidence=1.0
            )
    
    def _validate_modal_opened(self, goal: Goal, before: PageState, after: PageState) -> ValidationResult:
        """Validate that modal opened."""
        if not before.has_modal and after.has_modal:
            return ValidationResult(
                success=True,
                goal=goal,
                message="Modal opened",
                confidence=1.0
            )
        elif after.has_modal:
            return ValidationResult(
                success=True,
                goal=goal,
                message="Modal is open (may have been open before)",
                confidence=0.8
            )
        else:
            return ValidationResult(
                success=False,
                goal=goal,
                message="Modal did not open",
                confidence=1.0
            )
    
    def _validate_modal_closed(self, goal: Goal, before: PageState, after: PageState) -> ValidationResult:
        """Validate that modal closed."""
        if before.has_modal and not after.has_modal:
            return ValidationResult(
                success=True,
                goal=goal,
                message="Modal closed",
                confidence=1.0
            )
        elif not after.has_modal:
            return ValidationResult(
                success=True,
                goal=goal,
                message="Modal is closed (may have been closed before)",
                confidence=0.8
            )
        else:
            return ValidationResult(
                success=False,
                goal=goal,
                message="Modal did not close",
                confidence=1.0
            )
    
    def _validate_page_loaded(self, goal: Goal, after: PageState) -> ValidationResult:
        """Validate that page loaded successfully."""
        # Check if we have content
        if len(after.interactive_elements) > 0:
            return ValidationResult(
                success=True,
                goal=goal,
                message=f"Page loaded: {len(after.interactive_elements)} elements",
                actual_value=len(after.interactive_elements),
                confidence=0.9
            )
        else:
            return ValidationResult(
                success=False,
                goal=goal,
                message="Page appears not loaded (no elements)",
                confidence=0.8
            )
    
    def _validate_text_appeared(self, goal: Goal, before: PageState, after: PageState) -> ValidationResult:
        """Validate that specific text appeared."""
        expected_text = goal.expected_value
        if not expected_text:
            return ValidationResult(
                success=False,
                goal=goal,
                message="No expected text specified",
                confidence=1.0
            )
        
        # Check visible text blocks
        for text_block in after.visible_text_blocks:
            if expected_text.lower() in text_block.lower():
                return ValidationResult(
                    success=True,
                    goal=goal,
                    message=f"Text found: '{expected_text}'",
                    confidence=1.0
                )
        
        return ValidationResult(
            success=False,
            goal=goal,
            message=f"Text not found: '{expected_text}'",
            confidence=1.0
        )
    
    def _validate_navigation(self, goal: Goal, before: PageState, after: PageState) -> ValidationResult:
        """Validate that navigation occurred (page type changed)."""
        if before.page_type_hint != after.page_type_hint:
            return ValidationResult(
                success=True,
                goal=goal,
                message=f"Navigation: {before.page_type_hint} → {after.page_type_hint}",
                actual_value=after.page_type_hint,
                confidence=0.9
            )
        elif before.url != after.url:
            return ValidationResult(
                success=True,
                goal=goal,
                message=f"URL changed (navigation likely occurred)",
                confidence=0.8
            )
        else:
            return ValidationResult(
                success=False,
                goal=goal,
                message="No navigation detected",
                confidence=0.9
            )
    
    def _validate_product_selected(self, goal: Goal, before: PageState, after: PageState) -> ValidationResult:
        """Validate that we navigated to product detail page."""
        if after.page_type_hint == 'detail':
            return ValidationResult(
                success=True,
                goal=goal,
                message="On product detail page",
                confidence=0.9
            )
        elif 'product' in after.url.lower() or 'item' in after.url.lower():
            return ValidationResult(
                success=True,
                goal=goal,
                message="URL suggests product page",
                confidence=0.7
            )
        else:
            return ValidationResult(
                success=False,
                goal=goal,
                message=f"Not on product page (type: {after.page_type_hint})",
                confidence=0.9
            )
    
    def _validate_checkout_started(self, goal: Goal, after: PageState) -> ValidationResult:
        """Validate that we're on checkout page."""
        if after.page_type_hint == 'checkout':
            return ValidationResult(
                success=True,
                goal=goal,
                message="On checkout page",
                confidence=0.9
            )
        elif 'checkout' in after.url.lower() or 'payment' in after.url.lower():
            return ValidationResult(
                success=True,
                goal=goal,
                message="URL suggests checkout",
                confidence=0.8
            )
        else:
            return ValidationResult(
                success=False,
                goal=goal,
                message=f"Not on checkout page (type: {after.page_type_hint})",
                confidence=0.9
            )
    
    def create_goal_for_action(self, action: str, target: str, value: Optional[str] = None) -> Goal:
        """
        Create appropriate goal based on action type.
        
        Args:
            action: Action type (CLICK, TYPE, etc.)
            target: Target element description
            value: Value for TYPE actions
            
        Returns:
            Goal object
        """
        action_upper = action.upper()
        target_lower = target.lower()
        
        # Map actions to goals
        if action_upper == 'GOTO':
            return Goal(
                goal_type=GoalType.PAGE_LOADED,
                description=f"Page should load: {target}"
            )
        
        elif action_upper == 'CLICK':
            # Determine expected outcome based on target
            if any(word in target_lower for word in ['search', 'find', 'query']):
                if 'button' in target_lower or 'submit' in target_lower:
                    return Goal(
                        goal_type=GoalType.RESULTS_VISIBLE,
                        description="Search results should appear"
                    )
                else:
                    return Goal(
                        goal_type=GoalType.MODAL_OPENED,
                        description="Search modal should open"
                    )
            
            elif any(word in target_lower for word in ['add to cart', 'add cart', 'addto cart']):
                return Goal(
                    goal_type=GoalType.CART_UPDATED,
                    description="Cart should update"
                )
            
            elif any(word in target_lower for word in ['buy', 'purchase']):
                return Goal(
                    goal_type=GoalType.NAVIGATION_OCCURRED,
                    description="Should navigate to product/cart"
                )
            
            elif any(word in target_lower for word in ['checkout', 'proceed']):
                return Goal(
                    goal_type=GoalType.CHECKOUT_STARTED,
                    description="Should navigate to checkout"
                )
            
            elif any(word in target_lower for word in ['close', 'dismiss', 'cancel']):
                return Goal(
                    goal_type=GoalType.MODAL_CLOSED,
                    description="Modal should close"
                )
            
            else:
                # Generic click - expect navigation or state change
                return Goal(
                    goal_type=GoalType.NAVIGATION_OCCURRED,
                    description=f"Should navigate after clicking: {target}"
                )
        
        elif action_upper == 'TYPE':
            # Typing usually doesn't change page state immediately
            return Goal(
                goal_type=GoalType.NO_CHANGE,
                description=f"Text entered into: {target}"
            )
        
        elif action_upper == 'WAIT':
            return Goal(
                goal_type=GoalType.NO_CHANGE,
                description="Wait completed"
            )
        
        else:
            # Unknown action
            return Goal(
                goal_type=GoalType.NO_CHANGE,
                description=f"Action completed: {action}"
            )
    
    def get_validation_summary(self) -> Dict[str, any]:
        """Get summary of all validations."""
        total = len(self.validation_history)
        if total == 0:
            return {'total': 0, 'success_rate': 0.0}
        
        successful = sum(1 for v in self.validation_history if v.success)
        
        return {
            'total': total,
            'successful': successful,
            'failed': total - successful,
            'success_rate': successful / total,
            'avg_confidence': sum(v.confidence for v in self.validation_history) / total
        }
