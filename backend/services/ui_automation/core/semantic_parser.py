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

# Action verbs that start a new step after " then " or " and "
_ACTION_VERB_PATTERN = re.compile(
    r"\s+then\s+(?=click|search|fill|select|type|enter|choose|press|open|wait)",
    re.I,
)
_AND_ACTION_PATTERN = re.compile(
    r"\s+and\s+(?=search\s+for|search\s+|fill\s+|click\s+on|click\s+|select\s+|type\s+|enter\s+|choose\s+)",
    re.I,
)


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
            # Example: "then click on this product LG 5 Star (1.0) Split AC, AI Convertible 6-in-1 Cooling, Auto Clean, Diet Mode+, 100% Copper Tubes, 3.5 kW, 2025 Model"
            
            step_lower = raw_step.lower()
            
            # If line contains a click/select + "product" phrase and has multiple commas,
            # treat the ENTIRE line as a SINGLE product selection instruction.
            # This prevents splitting the long LG product name into separate pseudo-steps
            # like "AI Convertible 6-in-1 Cooling", "3.5 kW", etc.
            is_product_line = False
            
            # Case 1: Line starts directly with click/select/choose/this product
            if re.match(r'^(click|select|choose|this product)\b', step_lower, re.I) and raw_step.count(',') >= 2:
                is_product_line = True
            # Case 2: Line contains "...click on this product ..." anywhere
            elif "click on this product" in step_lower and raw_step.count(',') >= 2:
                is_product_line = True
            # Case 3: Line contains "...this product LG ..." style phrasing
            elif "this product" in step_lower and any(brand in step_lower for brand in ["lg", "samsung"]) and raw_step.count(',') >= 2:
                is_product_line = True
            
            if is_product_line:
                # Keep entire line as single step (don't split by commas)
                parsed_step = SemanticTestParser._parse_single_step(raw_step, step_id)
                if parsed_step:
                    steps.append(parsed_step)
                    step_id += 1
            else:
                # First split compound instructions: "click search and search for X and then click buynow" -> separate steps
                compound_chunks = SemanticTestParser._split_compound_instruction(raw_step)
                # Then split by commas within each chunk (e.g. "fill pincode 500032, then click check")
                sub_steps = []
                for chunk in compound_chunks:
                    sub_steps.extend([s.strip() for s in chunk.split(",") if s.strip()])
                for sub_step in sub_steps:
                    # Extract "wait for N seconds" (standalone or "after that wait for N seconds")
                    wait_match = re.search(r'(?:after that\s+)?wait for (\d+)\s*seconds?', sub_step, re.I)
                    main_text = sub_step
                    wait_seconds = None
                    if wait_match:
                        wait_seconds = int(wait_match.group(1))
                        main_text = re.sub(r'\s*after that\s+wait for \d+\s*seconds?\.?$', '', sub_step, flags=re.I).strip()
                        if not main_text:
                            main_text = None  # standalone "wait for N seconds" - let _parse_single_step handle it
                    parsed_step = SemanticTestParser._parse_single_step(main_text, step_id) if main_text else None
                    if parsed_step:
                        steps.append(parsed_step)
                        step_id += 1
                    # Append trailing wait only when we stripped it from a compound step (main step was not a wait)
                    if wait_seconds and (not parsed_step or parsed_step.type != StepType.WAIT):
                        steps.append(TestStep(
                            id=step_id,
                            type=StepType.WAIT,
                            intent=Intent.WAIT,
                            metadata={"duration_ms": wait_seconds * 1000}
                        ))
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
    def _split_compound_instruction(line: str) -> List[str]:
        """
        Split a line that contains multiple actions into separate step phrases.
        Handles: "click on search and search for X and then click on buynow" ->
          ["click on search", "search for X", "click on buynow"]
        Does not split product lines or "billing and shipping".
        """
        if not line or not line.strip():
            return [line] if line else []
        text = line.strip()
        # 1) Split by " and then " (clear separator of two actions)
        parts = re.split(r"\s+and\s+then\s+", text, flags=re.I)
        out: List[str] = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            # 2) Split by " then " when followed by an action verb
            sub_parts = _ACTION_VERB_PATTERN.split(p)
            for s in sub_parts:
                s = s.strip()
                if not s:
                    continue
                # 3) Split by " and " only when the part after " and " starts with an action phrase
                and_sub = _AND_ACTION_PATTERN.split(s)
                for a in and_sub:
                    a = a.strip()
                    if a:
                        out.append(a)
        return out if out else [text]

    @staticmethod
    def _extract_section_and_ordinal(target: str) -> tuple:
        """C1/C3: Extract section/container hint and ordinal from target. Returns (clean_target, metadata_dict or None)."""
        if not target or not isinstance(target, str):
            return target, None
        meta = {}
        t = target.strip()
        # " in product card" / " in checkout section" / " in the form"
        in_section = re.search(r'\s+in\s+(?:the\s+)?(product\s+card|checkout\s+section|form|main\s+section|delivery\s+section|content\s+area)\s*$', t, re.I)
        if in_section:
            section = in_section.group(1).replace(" ", "_").lower()
            meta["section"] = section
            meta["container_hint"] = section
            t = t[: in_section.start()].strip()
        # "second product", "first delivery option", "2nd product", "1st option"
        ord_match = re.search(r'\b(first|second|third|1st|2nd|3rd|fourth|4th|fifth|5th)\s+(product|delivery\s+option|option|item)\b', t, re.I)
        if ord_match:
            word = ord_match.group(1).lower()
            ord_map = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5}
            meta["ordinal"] = ord_map.get(word, 1)
            meta["target_type"] = ord_match.group(2).replace(" ", "_").lower()
            t = re.sub(r'\b(first|second|third|1st|2nd|3rd|fourth|4th|fifth|5th)\s+(product|delivery\s+option|option|item)\b', r"\2", t, flags=re.I).strip()
        return t, (meta if meta else None)

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
            r'^then\s+fill\s+(?:billing|shipping)\s*$',  # Incomplete: "then fill billing" without field details
        ]
        
        for pattern in product_spec_patterns:
            if re.match(pattern, step_lower, re.IGNORECASE):
                logger.debug(f"Filtered out product spec: '{step_text}'")
                return None

        # ==================== GENERIC NORMALIZATIONS / REDUNDANT STEPS ====================

        # Many test cases say "click on search option" immediately followed by
        # "search for X ...". The explicit click on the search icon is not
        # required for deterministic automation (the SEARCH step will locate
        # and type into the search box or overlay). To avoid fragile failures
        # on icon-only search controls, we treat this as redundant and skip it.
        if re.match(r'^(then\s+)?click\s+(on\s+)?search\s+(option|icon|button)s?\b', step_lower):
            logger.debug(f"Skipping redundant search icon step: '{step_text}'")
            return None
        
        # ==================== WAIT ====================
        wait_match = re.search(r'wait for (\d+)\s*(?:seconds?|secs?)?', step_lower)
        if wait_match and not ("click" in step_lower or "select" in step_lower):
            secs = int(wait_match.group(1))
            return TestStep(
                id=step_id,
                type=StepType.WAIT,
                intent=Intent.WAIT,
                metadata={"duration_ms": secs * 1000}
            )
        
        # ==================== NAVIGATION ====================
        # Only treat as GOTO when it's clearly a URL or "navigate/visit/go to [url or app]"
        nav_starts = step_lower.startswith(("navigate to", "go to", "visit"))
        if nav_starts or step_lower.startswith(("open ", "visit ")):
            url_match = re.search(r'https?://[^\s,]+', step_text)
            if url_match:
                url = url_match.group().strip()
                return TestStep(
                    id=step_id,
                    type=StepType.NAVIGATION,
                    intent=Intent.GOTO,
                    target=url,
                    expected_state=PageState.HOME
                )
            if nav_starts or re.match(r'^(open|visit)\s+(this\s+)?(application|app|site|website|page)\s', step_lower):
                url = re.sub(r'^(navigate to|go to|open|visit)\s+(this\s+)?(application|app|site|website|page)?\s*', '', step_text, flags=re.I).strip().rstrip('.,;:')
                # Only GOTO when it looks like a URL/domain (has a dot or is already http) — else "go to cart" stays as CLICK
                if url and (url.startswith(('http://', 'https://')) or '.' in url.split()[0]):
                    if not url.startswith(('http://', 'https://')):
                        url = f'https://{url}'
                    return TestStep(id=step_id, type=StepType.NAVIGATION, intent=Intent.GOTO, target=url, expected_state=PageState.HOME)
            # "go to cart", "open menu", "open settings" → CLICK (handled below)
        
        # ==================== ASSERTIONS (NOT ACTIONS!) ====================
        
        # "Verify", "Check that", "Ensure" → ASSERTION (exclude "click on check" which is a button)
        step_clean = re.sub(r'^(then|and)\s+', '', step_lower).strip()
        is_verification = (
            step_clean.startswith(("verify", "check that", "ensure", "validate", "confirm"))
            or re.match(r"^(verify|validate|ensure)\s+", step_clean)
        )
        is_click_action = "click" in step_lower and ("check" in step_lower or "button" in step_lower)
        if is_verification and not is_click_action:
            return SemanticTestParser._parse_assertion(step_text, step_id)
        
        # ==================== ACTIONS ====================
        
        # Click actions
        if "click" in step_lower or "tap" in step_lower or "this product" in step_lower:
            # Extract target - handle complex instructions like "on banner click on X"
            target = step_text
            # C1/C3: Extract section/container hint and ordinal ("in checkout section", "second product")
            target, context_meta = SemanticTestParser._extract_section_and_ordinal(target)
            
            # SPECIAL FIX: If user writes "X and then click on buynow",
            # treat ONLY "X" as the product target (do not include the trailing
            # "and then click on buynow" phrase).
            # Example raw step:
            #   "then click on lg tv 108cm and then click on buynow"
            # We want target = "lg tv 108cm"
            if "and then click on" in step_lower and "buy" in step_lower:
                before_buy = re.split(r'\band then click on\b', step_text, flags=re.I)[0]
                # Strip leading "then click on"/"click on"
                before_buy = re.sub(r'^(then\s+)?click\s+(on\s+)?', '', before_buy, flags=re.I).strip()
                if before_buy:
                    target = before_buy
            
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
            
            # Base metadata for click steps (C1/C3: section, ordinal)
            click_metadata = dict(context_meta) if context_meta else {}

            # Special case: category navigation
            if any(cat in step_lower for cat in ["air solutions", "category", "menu", "electronics"]):
                return TestStep(
                    id=step_id,
                    type=StepType.ACTION,
                    intent=Intent.CLICK,
                    target=target,
                    expected_state=PageState.CATEGORY,
                    metadata=click_metadata or None
                )
            
            # Special case: product list navigation
            if any(prod in step_lower for prod in ["split ac", "product type", "air conditioner", "audio"]):
                return TestStep(
                    id=step_id,
                    type=StepType.ACTION,
                    intent=Intent.CLICK,
                    target=target,
                    expected_state=PageState.PRODUCT_LIST,
                    metadata=click_metadata or None
                )
            
            # Guest checkout: "click on continue with this condition (complete purchase as guest)"
            if any(phrase in target.lower() for phrase in ["guest", "continue as guest", "complete purchase as guest"]):
                return TestStep(
                    id=step_id,
                    type=StepType.ACTION,
                    intent=Intent.CONTINUE_AS_GUEST,
                    target="guest",
                    expected_state=PageState.CHECKOUT
                )
            
            # Product selection (if contains product indicators and multiple commas)
            if ("this product" in step_lower or any(brand in step_lower for brand in ["lg", "samsung"])) and target.count(',') >= 2:
                md = {"is_product": True, "full_description": target}
                if click_metadata:
                    md.update(click_metadata)
                return TestStep(
                    id=step_id,
                    type=StepType.ACTION,
                    intent=Intent.SELECT,
                    target=target,
                    required_state=PageState.PRODUCT_LIST,
                    expected_state=PageState.PRODUCT_DETAIL,
                    metadata=md
                )
            
            return TestStep(
                id=step_id,
                type=StepType.ACTION,
                intent=Intent.CLICK,
                target=target,
                metadata=click_metadata or None
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
        
        # Pincode/ZIP (must be checked before generic "fill")
        if "pincode" in step_lower or "zip" in step_lower or "postal" in step_lower:
            pincode_match = re.search(r'\b\d{5,6}\b', step_text)
            pincode_val = pincode_match.group() if pincode_match else "560001"
            return TestStep(
                id=step_id,
                type=StepType.INPUT,
                intent=Intent.FILL_PINCODE,
                target="pincode",
                value=pincode_val
            )
        
        # Fill/Type operations (billing/shipping details)
        if ("fill" in step_lower or ("then" in step_lower and "details" in step_lower)) and ("billing" in step_lower or "shipping" in step_lower or "details" in step_lower):
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
            # Normalize long phrases like "then select free delivery option in delivery method"
            # down to just "free delivery" so resolvers match the real label text.
            if "free" in step_lower and "delivery" in step_lower:
                option = "free delivery"
            return TestStep(
                id=step_id,
                type=StepType.ACTION,
                intent=Intent.SELECT_OPTION,
                target=option
            )
        
        # Search
        if "search" in step_lower:
            cleaned = re.sub(r'^(then|and|also)\s+', '', step_text, flags=re.I).strip()
            query = re.sub(r'^search\s+(?:for\s+)?', '', cleaned, flags=re.I).strip()
            if not query:
                query = cleaned
            return TestStep(
                id=step_id,
                type=StepType.INPUT,
                intent=Intent.SEARCH,
                target="search",
                value=query
            )

        # Generic action phrases → CLICK so any site can be automated
        if step_lower.startswith(("open ", "press ", "hit ", "hit on ", "double-click ", "double click ")):
            target = re.sub(r'^(open|press|hit\s+on?|double-?click)\s+', '', step_text, flags=re.I).strip().rstrip('.,;:')
            if target:
                return TestStep(id=step_id, type=StepType.ACTION, intent=Intent.CLICK, target=target)
        if step_lower.startswith("go to ") and "." not in step_text.split()[-1]:
            # "go to cart", "go to checkout" → CLICK (not navigation)
            target = re.sub(r'^go to\s+', '', step_text, flags=re.I).strip().rstrip('.,;:')
            if target:
                return TestStep(id=step_id, type=StepType.ACTION, intent=Intent.CLICK, target=target)
        if re.match(r'^submit\s*(the\s+form)?\.?$', step_lower) or step_lower.strip() == "submit":
            return TestStep(id=step_id, type=StepType.ACTION, intent=Intent.CLICK, target="submit")

        # Fill/type generic: "fill X with Y", "enter Y in X"
        fill_match = re.search(r'^(?:fill|enter|type)\s+(.+?)\s+with\s+(.+)$', step_lower, re.I)
        if fill_match:
            return TestStep(id=step_id, type=StepType.INPUT, intent=Intent.TYPE, target=fill_match.group(1).strip(), value=fill_match.group(2).strip())
        enter_in = re.search(r'^(?:enter|type)\s+(.+?)\s+in(to)?\s+(.+)$', step_lower, re.I)
        if enter_in:
            return TestStep(id=step_id, type=StepType.INPUT, intent=Intent.TYPE, target=enter_in.group(3).strip(), value=enter_in.group(1).strip())

        # Generic fallback: treat as CLICK so resolution engine + healing can try (handles any test case)
        logger.info(f"Parsing as generic CLICK target: '{step_text[:80]}'")
        return TestStep(
            id=step_id,
            type=StepType.ACTION,
            intent=Intent.CLICK,
            target=step_text.strip()
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
