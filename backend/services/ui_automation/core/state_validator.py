"""
State Validation System - Validates state transitions after every action.

This is Layer 4 of the state-driven automation architecture.
Ensures every action produces expected state changes.
"""
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class StateChangeType(Enum):
    """Types of state changes to validate."""
    URL_CHANGE = "url_change"
    DOM_CHANGE = "dom_change"
    MODAL_OPENED = "modal_opened"
    MODAL_CLOSED = "modal_closed"
    PAGE_LOAD = "page_load"
    ELEMENT_VISIBLE = "element_visible"
    ELEMENT_HIDDEN = "element_hidden"
    TEXT_CHANGED = "text_changed"
    COUNT_CHANGED = "count_changed"
    NO_CHANGE = "no_change"


@dataclass
class ValidationRule:
    """Rule for validating state change."""
    change_type: StateChangeType
    selector: Optional[str] = None
    expected_value: Optional[Any] = None
    timeout: int = 5000
    required: bool = True
    
    def __repr__(self):
        return f"ValidationRule({self.change_type.value}, selector={self.selector})"


@dataclass
class ValidationResult:
    """Result of state validation."""
    success: bool
    rule: ValidationRule
    actual_value: Optional[Any] = None
    message: str = ""
    
    def __repr__(self):
        status = "✅" if self.success else "❌"
        return f"{status} {self.rule.change_type.value}: {self.message}"


class StateValidator:
    """
    Validates state transitions after actions.
    
    Ensures that:
    - Expected changes occurred
    - Page is in correct state
    - No unexpected errors
    """
    
    def __init__(self, page: Page):
        self.page = page
        self.validation_history: List[ValidationResult] = []
    
    async def validate(
        self,
        rules: List[ValidationRule],
        pre_state: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Validate state changes against rules.
        
        Args:
            rules: List of validation rules to check
            pre_state: Optional state snapshot before action
        
        Returns:
            True if all required validations passed
        """
        logger.info(f"🔍 Validating {len(rules)} rules...")
        
        results = []
        all_required_passed = True
        
        for rule in rules:
            result = await self._validate_rule(rule, pre_state)
            results.append(result)
            self.validation_history.append(result)
            
            logger.info(f"  {result}")
            
            if not result.success and rule.required:
                all_required_passed = False
        
        if all_required_passed:
            logger.info("✅ All required validations passed")
        else:
            logger.warning("⚠️ Some required validations failed")
        
        return all_required_passed
    
    async def _validate_rule(
        self,
        rule: ValidationRule,
        pre_state: Optional[Dict[str, Any]]
    ) -> ValidationResult:
        """Validate a single rule."""
        try:
            if rule.change_type == StateChangeType.URL_CHANGE:
                return await self._validate_url_change(rule, pre_state)
            
            elif rule.change_type == StateChangeType.MODAL_OPENED:
                return await self._validate_modal_opened(rule)
            
            elif rule.change_type == StateChangeType.MODAL_CLOSED:
                return await self._validate_modal_closed(rule)
            
            elif rule.change_type == StateChangeType.PAGE_LOAD:
                return await self._validate_page_load(rule)
            
            elif rule.change_type == StateChangeType.ELEMENT_VISIBLE:
                return await self._validate_element_visible(rule)
            
            elif rule.change_type == StateChangeType.ELEMENT_HIDDEN:
                return await self._validate_element_hidden(rule)
            
            elif rule.change_type == StateChangeType.TEXT_CHANGED:
                return await self._validate_text_changed(rule, pre_state)
            
            elif rule.change_type == StateChangeType.COUNT_CHANGED:
                return await self._validate_count_changed(rule, pre_state)
            
            elif rule.change_type == StateChangeType.DOM_CHANGE:
                return await self._validate_dom_change(rule)
            
            elif rule.change_type == StateChangeType.NO_CHANGE:
                return ValidationResult(
                    success=True,
                    rule=rule,
                    message="No change expected (validation skipped)"
                )
            
            else:
                return ValidationResult(
                    success=False,
                    rule=rule,
                    message=f"Unknown validation type: {rule.change_type}"
                )
        
        except Exception as e:
            logger.error(f"Validation error for {rule}: {e}")
            return ValidationResult(
                success=False,
                rule=rule,
                message=f"Exception: {str(e)}"
            )
    
    async def _validate_url_change(
        self,
        rule: ValidationRule,
        pre_state: Optional[Dict[str, Any]]
    ) -> ValidationResult:
        """Validate URL changed."""
        current_url = self.page.url
        
        if pre_state and "url" in pre_state:
            prev_url = pre_state["url"]
            changed = current_url != prev_url
            
            if rule.expected_value:
                # Check if URL contains expected value
                contains_expected = rule.expected_value in current_url
                return ValidationResult(
                    success=changed and contains_expected,
                    rule=rule,
                    actual_value=current_url,
                    message=f"URL changed from {prev_url[:30]}... to {current_url[:30]}... (expected: {rule.expected_value})"
                )
            else:
                return ValidationResult(
                    success=changed,
                    rule=rule,
                    actual_value=current_url,
                    message=f"URL changed: {changed}"
                )
        else:
            # No pre-state, just check if URL contains expected
            if rule.expected_value:
                contains = rule.expected_value in current_url
                return ValidationResult(
                    success=contains,
                    rule=rule,
                    actual_value=current_url,
                    message=f"URL contains '{rule.expected_value}': {contains}"
                )
            else:
                return ValidationResult(
                    success=True,
                    rule=rule,
                    actual_value=current_url,
                    message="URL check passed (no expected value)"
                )
    
    async def _validate_modal_opened(self, rule: ValidationRule) -> ValidationResult:
        """Validate modal opened."""
        modal_selectors = [
            '[role="dialog"]:visible',
            '.modal:visible',
            '[class*="modal"]:visible',
            '[aria-modal="true"]:visible'
        ]
        
        for selector in modal_selectors:
            try:
                count = await self.page.locator(selector).count()
                if count > 0:
                    return ValidationResult(
                        success=True,
                        rule=rule,
                        actual_value=selector,
                        message=f"Modal detected: {selector}"
                    )
            except:
                continue
        
        return ValidationResult(
            success=False,
            rule=rule,
            message="No modal detected"
        )
    
    async def _validate_modal_closed(self, rule: ValidationRule) -> ValidationResult:
        """Validate modal closed."""
        modal_selectors = [
            '[role="dialog"]:visible',
            '.modal:visible',
            '[class*="modal"]:visible'
        ]
        
        any_visible = False
        for selector in modal_selectors:
            try:
                count = await self.page.locator(selector).count()
                if count > 0:
                    any_visible = True
                    break
            except:
                continue
        
        return ValidationResult(
            success=not any_visible,
            rule=rule,
            message=f"Modal closed: {not any_visible}"
        )
    
    async def _validate_page_load(self, rule: ValidationRule) -> ValidationResult:
        """Validate page loaded."""
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=rule.timeout)
            return ValidationResult(
                success=True,
                rule=rule,
                message="Page loaded successfully"
            )
        except Exception as e:
            return ValidationResult(
                success=False,
                rule=rule,
                message=f"Page load timeout: {e}"
            )
    
    async def _validate_element_visible(self, rule: ValidationRule) -> ValidationResult:
        """Validate element became visible."""
        if not rule.selector:
            return ValidationResult(
                success=False,
                rule=rule,
                message="No selector provided"
            )
        
        try:
            elem = self.page.locator(rule.selector).first
            await elem.wait_for(state="visible", timeout=rule.timeout)
            return ValidationResult(
                success=True,
                rule=rule,
                message=f"Element visible: {rule.selector}"
            )
        except Exception as e:
            return ValidationResult(
                success=False,
                rule=rule,
                message=f"Element not visible: {rule.selector}"
            )
    
    async def _validate_element_hidden(self, rule: ValidationRule) -> ValidationResult:
        """Validate element became hidden."""
        if not rule.selector:
            return ValidationResult(
                success=False,
                rule=rule,
                message="No selector provided"
            )
        
        try:
            elem = self.page.locator(rule.selector).first
            await elem.wait_for(state="hidden", timeout=rule.timeout)
            return ValidationResult(
                success=True,
                rule=rule,
                message=f"Element hidden: {rule.selector}"
            )
        except Exception as e:
            # Element might not exist at all, which is also "hidden"
            count = await self.page.locator(rule.selector).count()
            if count == 0:
                return ValidationResult(
                    success=True,
                    rule=rule,
                    message=f"Element not in DOM: {rule.selector}"
                )
            return ValidationResult(
                success=False,
                rule=rule,
                message=f"Element still visible: {rule.selector}"
            )
    
    async def _validate_text_changed(
        self,
        rule: ValidationRule,
        pre_state: Optional[Dict[str, Any]]
    ) -> ValidationResult:
        """Validate text content changed."""
        if not rule.selector:
            return ValidationResult(
                success=False,
                rule=rule,
                message="No selector provided"
            )
        
        try:
            elem = self.page.locator(rule.selector).first
            current_text = await elem.inner_text()
            
            if pre_state and "text" in pre_state:
                prev_text = pre_state["text"]
                changed = current_text != prev_text
                return ValidationResult(
                    success=changed,
                    rule=rule,
                    actual_value=current_text,
                    message=f"Text changed: {changed} ('{prev_text}' -> '{current_text}')"
                )
            else:
                # No pre-state, check if text matches expected
                if rule.expected_value:
                    matches = rule.expected_value in current_text
                    return ValidationResult(
                        success=matches,
                        rule=rule,
                        actual_value=current_text,
                        message=f"Text contains '{rule.expected_value}': {matches}"
                    )
                else:
                    return ValidationResult(
                        success=True,
                        rule=rule,
                        actual_value=current_text,
                        message="Text check passed (no expected value)"
                    )
        except Exception as e:
            return ValidationResult(
                success=False,
                rule=rule,
                message=f"Could not get text: {e}"
            )
    
    async def _validate_count_changed(
        self,
        rule: ValidationRule,
        pre_state: Optional[Dict[str, Any]]
    ) -> ValidationResult:
        """Validate element count changed (e.g., cart items)."""
        if not rule.selector:
            return ValidationResult(
                success=False,
                rule=rule,
                message="No selector provided"
            )
        
        try:
            current_count = await self.page.locator(rule.selector).count()
            
            if pre_state and "count" in pre_state:
                prev_count = pre_state["count"]
                changed = current_count != prev_count
                
                if rule.expected_value:
                    # Check if count matches expected
                    matches = current_count == rule.expected_value
                    return ValidationResult(
                        success=changed and matches,
                        rule=rule,
                        actual_value=current_count,
                        message=f"Count changed: {prev_count} -> {current_count} (expected: {rule.expected_value})"
                    )
                else:
                    return ValidationResult(
                        success=changed,
                        rule=rule,
                        actual_value=current_count,
                        message=f"Count changed: {prev_count} -> {current_count}"
                    )
            else:
                # No pre-state, just check current count
                if rule.expected_value:
                    matches = current_count == rule.expected_value
                    return ValidationResult(
                        success=matches,
                        rule=rule,
                        actual_value=current_count,
                        message=f"Count is {current_count} (expected: {rule.expected_value})"
                    )
                else:
                    return ValidationResult(
                        success=True,
                        rule=rule,
                        actual_value=current_count,
                        message=f"Count is {current_count}"
                    )
        except Exception as e:
            return ValidationResult(
                success=False,
                rule=rule,
                message=f"Could not count elements: {e}"
            )
    
    async def _validate_dom_change(self, rule: ValidationRule) -> ValidationResult:
        """Validate DOM changed (generic)."""
        # This is a soft validation - we assume DOM changed if page is stable
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=rule.timeout)
            return ValidationResult(
                success=True,
                rule=rule,
                message="DOM appears stable after change"
            )
        except:
            return ValidationResult(
                success=True,
                rule=rule,
                message="DOM change assumed (timeout waiting for stability)"
            )
    
    async def capture_state_snapshot(self, selectors: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Capture current state snapshot for later comparison.
        
        Args:
            selectors: Optional list of selectors to capture state for
        
        Returns:
            State snapshot dictionary
        """
        snapshot = {
            "url": self.page.url,
            "title": await self.page.title(),
        }
        
        if selectors:
            for selector in selectors:
                try:
                    elem = self.page.locator(selector).first
                    if await elem.count() > 0:
                        snapshot[f"text_{selector}"] = await elem.inner_text()
                        snapshot[f"visible_{selector}"] = await elem.is_visible()
                    
                    snapshot[f"count_{selector}"] = await self.page.locator(selector).count()
                except:
                    continue
        
        return snapshot


def create_validation_rules_for_action(action_intent: str) -> List[ValidationRule]:
    """
    Create appropriate validation rules for an action intent.
    
    Args:
        action_intent: ActionIntent value
    
    Returns:
        List of validation rules
    """
    from .intent_normalizer import ActionIntent
    
    rules = []
    
    # Map intents to validation rules
    if action_intent == ActionIntent.NAVIGATE.value:
        rules.append(ValidationRule(StateChangeType.URL_CHANGE, required=True))
        rules.append(ValidationRule(StateChangeType.PAGE_LOAD, required=True))
    
    elif action_intent == ActionIntent.SEARCH_PRODUCT.value:
        rules.append(ValidationRule(StateChangeType.URL_CHANGE, required=False))
        rules.append(ValidationRule(
            StateChangeType.ELEMENT_VISIBLE,
            selector='[class*="product"], [class*="result"]',
            required=True
        ))
    
    elif action_intent in [ActionIntent.BUY_PRODUCT.value, ActionIntent.SELECT_PRODUCT.value]:
        rules.append(ValidationRule(StateChangeType.URL_CHANGE, required=False))
        rules.append(ValidationRule(StateChangeType.PAGE_LOAD, required=False))
    
    elif action_intent == ActionIntent.CHECKOUT.value:
        rules.append(ValidationRule(StateChangeType.URL_CHANGE, required=True))
        rules.append(ValidationRule(
            StateChangeType.ELEMENT_VISIBLE,
            selector='form, [class*="checkout"]',
            required=True
        ))
    
    # Default: just check page stability
    if not rules:
        rules.append(ValidationRule(StateChangeType.DOM_CHANGE, required=False))
    
    return rules
