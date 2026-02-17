"""
🚀 PHASE 1 — SEMANTIC TEST PARSER
Converts English/Enterprise Specs to Normalized Test Model

CRITICAL: "Verify" statements → ASSERTION (not ACTION)
"""
import logging
import re
from typing import List, Dict, Any, Optional
from .test_model import TestStep, TestCase, StepType, Intent, PageState

logger = logging.getLogger(__name__)


class SemanticTestParser:
    """
    Converts natural language or enterprise test specs to normalized DSL
    
    ✅ Converts "Verify homepage loaded" → ASSERTION
    ❌ Never converts it to CLICK
    """
    
    @staticmethod
    def parse_natural_language(test_case_text: str, start_url: str = None) -> TestCase:
        """
        Parse simple natural language test case
        
        Example:
            Input: "Navigate to lg.com, click Air Solutions, verify page loaded, select LG AC"
            
            Output: TestCase with normalized steps:
                1. NAVIGATION:GOTO
                2. ACTION:CLICK  
                3. ASSERTION:PAGE_LOADED
                4. ACTION:SELECT
        """
        steps = []
        step_id = 1
        
        # Split by newlines ONLY (don't split by commas - they may be part of product names)
        raw_steps = [s.strip() for s in test_case_text.split('\n') if s.strip()]
        
        for raw_step in raw_steps:
            # Check if this line contains a product description with multiple comma-separated features
            # Pattern: "click/select [product name], [feature1], [feature2], ..."
            # Example: "this product LG 5 Star (1.0) Split AC, AI Convertible 6-in-1 Cooling, Auto Clean, Diet Mode+, 100% Copper Tubes, 3.5 kW, 2025 Model"
            
            # If line starts with action verb and has multiple commas, treat as single product selection
            is_product_line = False
            action_match = re.match(r'^(click|select|choose|this product)\s+(.+)', raw_step, re.I)
            if action_match and raw_step.count(',') >= 2:
                # This looks like a product with comma-separated features
                is_product_line = True
            
            if is_product_line:
                # Keep entire line as single step (don't split by commas)
                parsed_step = SemanticTestParser._parse_single_step(raw_step, step_id)
                if parsed_step:
                    steps.append(parsed_step)
                    step_id += 1
            else:
                # Split by commas for regular steps (non-product descriptions)
                sub_steps = [s.strip() for s in raw_step.split(',') if s.strip()]
                for sub_step in sub_steps:
                    parsed_step = SemanticTestParser._parse_single_step(sub_step, step_id)
                    if parsed_step:
                        steps.append(parsed_step)
                        step_id += 1
        
        return TestCase(
            id="auto_generated",
            title=test_case_text[:50],
            steps=steps
        )
    
    @staticmethod
    def parse_enterprise_format(spec: Dict[str, Any]) -> TestCase:
        """
        Parse enterprise test case format
        
        Example Input:
        {
            "Test Case ID": "TC001",
            "Objective": "Verify checkout flow",
            "Preconditions": ["User logged in"],
            "Test Data": {"pincode": "560001"},
            "Steps": [
                {
                    "Step": "Navigate to homepage",
                    "Expected Result": "Homepage loaded successfully"
                },
                {
                    "Step": "Click product",
                    "Expected Result": "Product detail page displayed"
                }
            ]
        }
        
        Output: TestCase with normalized steps
        """
        test_id = spec.get("Test Case ID", "unknown")
        objective = spec.get("Objective", "")
        preconditions = spec.get("Preconditions", [])
        test_data = spec.get("Test Data", {})
        raw_steps = spec.get("Steps", [])
        
        steps = []
        step_id = 1
        
        for raw_step_obj in raw_steps:
            step_text = raw_step_obj.get("Step", "")
            expected_result = raw_step_obj.get("Expected Result", "")
            
            # Parse action step
            action_step = SemanticTestParser._parse_single_step(step_text, step_id)
            if action_step:
                steps.append(action_step)
                step_id += 1
            
            # Parse expected result as ASSERTION
            if expected_result:
                assertion_step = SemanticTestParser._parse_assertion(expected_result, step_id)
                if assertion_step:
                    steps.append(assertion_step)
                    step_id += 1
        
        return TestCase(
            id=test_id,
            title=objective,
            objective=objective,
            preconditions=preconditions,
            test_data=test_data,
            steps=steps
        )
    
    @staticmethod
    def _parse_single_step(step_text: str, step_id: int) -> Optional[TestStep]:
        """Parse single step into normalized TestStep"""
        step_lower = step_text.lower().strip()
        
        # Filter out product specs/features (not test steps)
        product_spec_patterns = [
            r'^\d+\s*(kw|star|ton|hp|inch|gb|tb|mp|mah)\b',  # Technical specs: 3.5 kW, 5 Star, 1.5 Ton
            r'^(ai|auto|diet|eco|turbo|smart|quick|super)\s+\w+$',  # Feature names: AI Convertible, Auto Clean
            r'^\d+%\s+\w+',  # Percentages: 100% Copper
            r'^\d{4}\s+model$',  # Year model: 2025 Model
            r'^[\w\s]+\+$',  # Feature with +: Diet Mode+
            r'^then\s+fill\s+',  # Partial instruction: then fill billing/shipping
        ]
        
        for pattern in product_spec_patterns:
            if re.match(pattern, step_lower, re.IGNORECASE):
                logger.debug(f"Filtered out product spec: '{step_text}'")
                return None
        
        # ==================== NAVIGATION ====================
        if step_lower.startswith(("navigate to", "go to", "open", "visit")):
            # Extract URL from text - look for http/https URLs first
            url_match = re.search(r'https?://[^\s,]+', step_text)
            if url_match:
                url = url_match.group().strip()
            else:
                # Fallback: remove navigation keywords and clean up
                url = re.sub(r'^(navigate to|go to|open|visit)\s+(this\s+)?(application|app|site|website|page)?\s*', '', step_text, flags=re.I).strip()
                # Remove trailing punctuation
                url = url.rstrip('.,;:')
                # Add https if no protocol
                if url and not url.startswith(('http://', 'https://')):
                    url = f'https://{url}'
            
            return TestStep(
                id=step_id,
                type=StepType.NAVIGATION,
                intent=Intent.GOTO,
                target=url,
                expected_state=PageState.HOME
            )
        
        # ==================== ASSERTIONS (NOT ACTIONS!) ====================
        
        # "Verify", "Check", "Ensure", "Validate" → ASSERTION
        if any(keyword in step_lower for keyword in ["verify", "check", "ensure", "validate", "confirm"]):
            return SemanticTestParser._parse_assertion(step_text, step_id)
        
        # ==================== ACTIONS ====================
        
        # Click actions
        if "click" in step_lower or "tap" in step_lower or "this product" in step_lower:
            # Extract target - handle complex instructions like "on banner click on X"
            target = step_text
            
            # Pattern 1: "...banner click on X" -> extract X
            banner_match = re.search(r'banner\s+click\s+on\s+(.+)', step_text, re.I)
            if banner_match:
                target = banner_match.group(1).strip()
            # Pattern 2: "this product XYZ" -> extract XYZ (full product name with all features)
            elif "this product" in step_lower:
                product_match = re.search(r'this product\s+(.+)', step_text, re.I)
                if product_match:
                    target = product_match.group(1).strip()
            else:
                # Pattern 3: "click on X" -> extract X
                click_match = re.search(r'click\s+(?:on\s+)?(.+)', step_text, re.I)
                if click_match:
                    target = click_match.group(1).strip()
            
            # Special case: category navigation
            if any(cat in step_lower for cat in ["air solutions", "category", "menu", "electronics"]):
                return TestStep(
                    id=step_id,
                    type=StepType.ACTION,
                    intent=Intent.CLICK,
                    target=target,
                    expected_state=PageState.CATEGORY
                )
            
            # Special case: product list navigation
            if any(prod in step_lower for prod in ["split ac", "product type", "air conditioner", "audio"]):
                return TestStep(
                    id=step_id,
                    type=StepType.ACTION,
                    intent=Intent.CLICK,
                    target=target,
                    expected_state=PageState.PRODUCT_LIST
                )
            
            # Product selection (if contains product indicators and multiple commas)
            if ("this product" in step_lower or any(brand in step_lower for brand in ["lg", "samsung"])) and target.count(',') >= 2:
                return TestStep(
                    id=step_id,
                    type=StepType.ACTION,
                    intent=Intent.SELECT,
                    target=target,
                    required_state=PageState.PRODUCT_LIST,
                    expected_state=PageState.PRODUCT_DETAIL,
                    metadata={"is_product": True, "full_description": target}
                )
            
            return TestStep(
                id=step_id,
                type=StepType.ACTION,
                intent=Intent.CLICK,
                target=target
            )
        
        # Select/Choose actions (products)
        if ("select" in step_lower or "choose" in step_lower) and any(brand in step_lower for brand in ["lg", "samsung", "product"]):
            product_name = re.sub(r'^(select|choose)\s+', '', step_text, flags=re.I).strip()
            return TestStep(
                id=step_id,
                type=StepType.ACTION,
                intent=Intent.SELECT,
                target=product_name,
                required_state=PageState.PRODUCT_LIST,
                expected_state=PageState.PRODUCT_DETAIL,
                metadata={"is_product": True}
            )
        
        # Add to cart
        if "add to cart" in step_lower or "add to bag" in step_lower:
            return TestStep(
                id=step_id,
                type=StepType.ACTION,
                intent=Intent.ADD_TO_CART,
                required_state=PageState.PRODUCT_DETAIL,
                expected_state=PageState.CART
            )
        
        # Buy now
        if "buy now" in step_lower or "buy" in step_lower:
            return TestStep(
                id=step_id,
                type=StepType.ACTION,
                intent=Intent.BUY_NOW,
                required_state=PageState.PRODUCT_DETAIL,
                expected_state=PageState.CART
            )
        
        # Fill/Type operations
        if "fill" in step_lower or ("then" in step_lower and "details" in step_lower):
            # Extract what to fill
            target = "billing and shipping details"
            if "billing" in step_lower or "shipping" in step_lower:
                target = "billing/shipping details"
            return TestStep(
                id=step_id,
                type=StepType.ACTION,
                intent=Intent.FILL_FORM,
                target=target,
                metadata={"form_type": "billing_shipping"}
            )
        
        # Checkout
        if "checkout" in step_lower and "guest" not in step_lower:
            return TestStep(
                id=step_id,
                type=StepType.ACTION,
                intent=Intent.CHECKOUT,
                required_state=PageState.CART,
                expected_state=PageState.CHECKOUT
            )
        
        # Guest checkout
        if "guest" in step_lower or "continue as guest" in step_lower:
            return TestStep(
                id=step_id,
                type=StepType.ACTION,
                intent=Intent.CONTINUE_AS_GUEST,
                expected_state=PageState.CHECKOUT
            )
        
        # ==================== INPUT ====================
        
        # Pincode/ZIP
        if "pincode" in step_lower or "zip" in step_lower or "postal" in step_lower:
            pincode_match = re.search(r'\b\d{5,6}\b', step_text)
            pincode = pincode_match.group() if pincode_match else "560001"
            return TestStep(
                id=step_id,
                type=StepType.INPUT,
                intent=Intent.FILL_PINCODE,
                target="pincode",
                value=pincode
            )
        
        # Email
        if "email" in step_lower:
            email_match = re.search(r'[\w\.-]+@[\w\.-]+', step_text)
            email = email_match.group() if email_match else None
            return TestStep(
                id=step_id,
                type=StepType.INPUT,
                intent=Intent.FILL_EMAIL,
                target="email",
                value=email
            )
        
        # Phone
        if "phone" in step_lower or "mobile" in step_lower:
            phone_match = re.search(r'\b\d{10}\b', step_text)
            phone = phone_match.group() if phone_match else None
            return TestStep(
                id=step_id,
                type=StepType.INPUT,
                intent=Intent.FILL_PHONE,
                target="phone",
                value=phone
            )
        
        # Type/Enter
        if "type" in step_lower or "enter" in step_lower:
            parts = step_text.split(maxsplit=2)
            if len(parts) >= 3:
                return TestStep(
                    id=step_id,
                    type=StepType.INPUT,
                    intent=Intent.TYPE,
                    target=parts[1],
                    value=parts[2] if len(parts) > 2 else None
                )
        
        # Select option (delivery, payment)
        if "select" in step_lower and any(opt in step_lower for opt in ["delivery", "shipping", "payment", "option"]):
            option = re.sub(r'^select\s+', '', step_text, flags=re.I).strip()
            return TestStep(
                id=step_id,
                type=StepType.ACTION,
                intent=Intent.SELECT_OPTION,
                target=option
            )
        
        # Search
        if "search" in step_lower:
            query = re.sub(r'^search\s+(for\s+)?', '', step_text, flags=re.I).strip()
            return TestStep(
                id=step_id,
                type=StepType.INPUT,
                intent=Intent.SEARCH,
                target="search",
                value=query
            )
        
        # Generic fallback
        logger.warning(f"Could not parse step: '{step_text}', treating as generic CLICK")
        return TestStep(
            id=step_id,
            type=StepType.ACTION,
            intent=Intent.CLICK,
            target=step_text
        )
    
    @staticmethod
    def _parse_assertion(assertion_text: str, step_id: int) -> Optional[TestStep]:
        """
        Parse assertion (verify/check statement)
        
        ✅ Returns ASSERTION step (NO UI action)
        ❌ Never returns ACTION step
        """
        assertion_lower = assertion_text.lower().strip()
        
        # Remove assertion keywords
        clean_text = re.sub(
            r'^(verify|check|ensure|validate|confirm|expected result:?)\s+',
            '',
            assertion_text,
            flags=re.I
        ).strip()
        
        # Page loaded assertions
        if any(keyword in assertion_lower for keyword in ["loaded", "displayed", "shown", "appears", "visible"]):
            # Determine what page/element should be loaded
            if "home" in assertion_lower:
                return TestStep(
                    id=step_id,
                    type=StepType.ASSERTION,
                    intent=Intent.PAGE_LOADED,
                    value="home page",
                    required_state=PageState.HOME
                )
            elif any(cat in assertion_lower for cat in ["category", "air solutions"]):
                return TestStep(
                    id=step_id,
                    type=StepType.ASSERTION,
                    intent=Intent.PAGE_LOADED,
                    value="category page",
                    required_state=PageState.CATEGORY
                )
            elif "product" in assertion_lower and "detail" in assertion_lower:
                return TestStep(
                    id=step_id,
                    type=StepType.ASSERTION,
                    intent=Intent.PAGE_LOADED,
                    value="product detail page",
                    required_state=PageState.PRODUCT_DETAIL
                )
            elif "cart" in assertion_lower or "bag" in assertion_lower:
                return TestStep(
                    id=step_id,
                    type=StepType.ASSERTION,
                    intent=Intent.PAGE_LOADED,
                    value="cart page",
                    required_state=PageState.CART
                )
            elif "checkout" in assertion_lower or "billing" in assertion_lower:
                return TestStep(
                    id=step_id,
                    type=StepType.ASSERTION,
                    intent=Intent.PAGE_LOADED,
                    value="checkout page"
                )
            else:
                # Generic page loaded
                return TestStep(
                    id=step_id,
                    type=StepType.ASSERTION,
                    intent=Intent.PAGE_LOADED,
                    value=clean_text
                )
        
        # Element visible assertions
        if "visible" in assertion_lower or "appears" in assertion_lower:
            return TestStep(
                id=step_id,
                type=StepType.ASSERTION,
                intent=Intent.ELEMENT_VISIBLE,
                target=clean_text
            )
        
        # Filter applied assertions
        if "filter" in assertion_lower:
            return TestStep(
                id=step_id,
                type=StepType.ASSERTION,
                intent=Intent.FILTER_APPLIED,
                value=clean_text
            )
        
        # Delivery options assertions
        if "delivery" in assertion_lower or "shipping" in assertion_lower:
            return TestStep(
                id=step_id,
                type=StepType.ASSERTION,
                intent=Intent.DELIVERY_OPTIONS_LOADED,
                value=clean_text
            )
        
        # Button enabled assertions
        if "enabled" in assertion_lower or "clickable" in assertion_lower:
            return TestStep(
                id=step_id,
                type=StepType.ASSERTION,
                intent=Intent.BUTTON_ENABLED,
                target=clean_text
            )
        
        # Order confirmation
        if "order" in assertion_lower and ("confirm" in assertion_lower or "success" in assertion_lower):
            return TestStep(
                id=step_id,
                type=StepType.ASSERTION,
                intent=Intent.ORDER_CONFIRMED,
                value=clean_text,
                required_state=PageState.CONFIRMATION
            )
        
        # Text contains assertions
        if "contains" in assertion_lower or "includes" in assertion_lower:
            return TestStep(
                id=step_id,
                type=StepType.ASSERTION,
                intent=Intent.TEXT_CONTAINS,
                value=clean_text
            )
        
        # URL assertions
        if "url" in assertion_lower:
            return TestStep(
                id=step_id,
                type=StepType.ASSERTION,
                intent=Intent.URL_MATCHES,
                value=clean_text
            )
        
        # Generic assertion (page loaded)
        return TestStep(
            id=step_id,
            type=StepType.ASSERTION,
            intent=Intent.PAGE_LOADED,
            value=clean_text
        )
