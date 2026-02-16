"""
UI Test Planner Agent
Converts raw test case into structured JSON plan with atomic steps and UI intents.
Works without any API key: splits on "then"/"and", parses actions (navigate, click, type, etc.),
and generates short step descriptions. Optional: when AZURE_API_KEY is set, LLM can decompose
or enrich the plan for better semantics.
"""
from typing import Dict, Any, List, Optional
import json
import re
import logging
import os

logger = logging.getLogger(__name__)

# Allowed step action types (constrained output – LLM cannot invent others)
ALLOWED_ACTIONS = {"navigate", "goto", "click", "fill", "type", "select", "press", "wait", "verify", "comment"}
# Actions that become click when executor runs
CLICK_LIKE = {"click", "verify"}
FILL_LIKE = {"fill", "type"}


def _shorten_description(line: str, prefix: str = "") -> str:
    """Turn a long user phrase into a short step description (no API key)."""
    line = (line or "").strip()
    if len(line) <= 55:
        return line if not prefix else (prefix + ": " + line) if line else prefix
    words = line.split()
    if len(words) <= 6:
        return line[:55].rstrip() + ("..." if len(line) > 55 else "")
    return " ".join(words[:6]) + "..."


def _sanitize_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Rule-based sanitization so LLM cannot invent impossible step types.
    Only allowed actions are kept; unknown actions are coerced to click or dropped.
    """
    steps = plan.get("steps") or []
    sanitized = []
    for s in steps:
        action = (s.get("action") or "click").strip().lower()
        if action not in ALLOWED_ACTIONS:
            action = "click"
        s["action"] = action
        if not s.get("description"):
            s["description"] = f"Step: {action}"
        sanitized.append(s)
    plan["steps"] = sanitized
    plan["total_steps"] = len(sanitized)
    return plan


def _inject_app_specific_steps(plan: Dict[str, Any]) -> None:
    """When app config says so (e.g. LG India), inject cookie_accept step after first navigate."""
    try:
        from config.app_config import get_app_config_for_url, should_inject_cookie_step
    except ImportError:
        return
    url = plan.get("url") or ""
    if not url or not should_inject_cookie_step(url):
        return
    steps = plan.get("steps") or []
    insert_at = None
    for i, s in enumerate(steps):
        if s.get("action") == "navigate":
            insert_at = i + 1
            break
    if insert_at is None:
        return
    cfg = get_app_config_for_url(url)
    hints = (cfg or {}).get("cookie_accept_selectors") or [
        "button:has-text('Accept all')",
        "button:has-text('Accept')",
        "a:has-text('Accept all')",
    ]
    try:
        from services.ui_automation.intent import get_locator_hint_for_intent
        cookie_hint = get_locator_hint_for_intent("cookie_accept")
    except Exception:
        cookie_hint = {"role": "button", "name": "Accept all"}
    cookie_step = {
        "action": "click",
        "element": "Accept all / cookie consent",
        "description": "Accept cookie consent banner (injected for this application)",
        "intent": "cookie_accept",
        "semantic_target": "button",
        "locator_hint": cookie_hint,
        "selector_hints": hints,
        "selectors": hints[:6],
        "selector": hints[0] if hints else "button:has-text('Accept all')",
    }
    steps.insert(insert_at, cookie_step)
    for j, s in enumerate(steps):
        s["step"] = j + 1
    plan["total_steps"] = len(steps)
    logger.info("Injected cookie_accept step after navigate for %s (%s steps)", url[:50], len(steps))


def _parse_price_condition(description: str, element: str) -> Optional[Dict[str, Any]]:
    """Detect numeric constraints (e.g. under 30000, below 30k) for select_product_with_condition."""
    text = f" {description or ''} {element or ''} ".lower()
    # under 30000, below 30k, under ₹30000, less than 25000, < 40000
    match = re.search(r"(?:under|below|less than|<)\s*[^\d]*(?:₹|rs\.?|inr)?\s*([0-9,]+)\s*(k|000)?", text, re.I)
    if match:
        raw = match.group(1).replace(",", "")
        try:
            n = int(raw)
            if match.lastindex >= 2 and match.group(2):
                n = n * 1000
            return {"price_max": n}
        except ValueError:
            pass
    m = re.search(r"\b(\d{4,6})\s*(?:and under|or less)\b", text)
    if m:
        try:
            return {"price_max": int(m.group(1))}
        except ValueError:
            pass
    return None


def _add_intents_to_steps(plan: Dict[str, Any]) -> None:
    """Add intent, semantic_target, condition (for select_product_with_condition), and locator_hint."""
    try:
        from services.ui_automation.intent import (
            classify_intent,
            get_intent_semantics,
            get_selector_hints_for_intent,
            get_locator_hint_for_intent,
        )
    except ImportError:
        return
    for step in plan.get("steps", []):
        # Preserve injected cookie_accept intent so it is not overwritten
        if step.get("intent") == "cookie_accept":
            hint = get_locator_hint_for_intent("cookie_accept")
            if hint:
                step["locator_hint"] = hint
            continue
        action = step.get("action", "")
        element = step.get("element", "")
        description = step.get("description", "")
        intent = classify_intent(action, element, description)
        # Enterprise: detect price condition for Buy Now / product select -> semantic action
        condition = _parse_price_condition(description, element)
        if condition and intent in ("product_select", "add_to_cart"):
            intent = "select_product_with_condition"
            step["condition"] = condition
            step["semantic_action"] = "select_product_with_condition"
        step["intent"] = intent
        semantics = get_intent_semantics(intent)
        step["semantic_target"] = semantics.get("semantic_target", "button/link")
        step["fallback_semantics"] = semantics.get("fallback_semantics", [])
        hints = get_selector_hints_for_intent(intent)
        step["selector_hints"] = hints
        locator_hint = get_locator_hint_for_intent(intent)
        if locator_hint:
            step["locator_hint"] = locator_hint
        if not step.get("selector") and hints:
            step["selector"] = hints[0] if isinstance(hints[0], str) else hints[0].get("selector", "")
        if hints and not step.get("selectors"):
            step["selectors"] = hints[:5]
    logger.info("Added UI intents (and locator_hint where available) to %s steps", len(plan.get("steps", [])))


def _decompose_raw_input_with_llm(raw_input: str) -> Optional[Dict[str, Any]]:
    """
    Use LLM to break down the user's natural-language scenario into atomic test steps.
    Each step is ONE action (navigate, click, type, etc.) with a short description.
    Returns a plan dict with url and steps, or None if LLM is unavailable or fails.
    """
    try:
        from utils.azure_openai import chat_completion, create_system_message, create_user_message
    except ImportError:
        return None
    if not os.getenv("AZURE_API_KEY"):
        return None
    sys_msg = """You are a UI test planner. Your job is to convert the user's test scenario into a list of ATOMIC steps.
Each step must be exactly ONE action: one navigate, one click, one type, one select, or one wait.
- Break compound instructions into separate steps. Example: "click on search and search for lg tv" must become:
  1) Click search icon/open search
  2) Type "lg tv" in search input
  3) Click search submit button
- Use SHORT descriptions (e.g. "Accept cookie banner", "Click search icon", "Type pincode 500032", "Click Buy Now for product under 30000").
- Extract the starting URL from the scenario (e.g. "navigate to https://www.lg.com/in" -> url: "https://www.lg.com/in", step 1: navigate to that URL).
- For "fill pincode as 500032" use one step: type 500032 in pincode field.
- For "click checkout then continue as guest" use two steps: click checkout, then click continue as guest.
Output ONLY a JSON object with keys:
- "url": string (the main URL to start on, or empty string)
- "steps": array of objects, each with: "step" (1-based number), "action" (navigate|click|type|select|verify|wait), "description" (short phrase), "element" (optional), "value" (optional, for type/navigate)
Return only valid JSON, no markdown or explanation."""
    user_content = "Test scenario:\n" + raw_input
    try:
        resp = chat_completion(
            messages=[create_system_message(sys_msg), create_user_message(user_content)],
            temperature=0.2,
            max_tokens=3000,
        )
        text = (resp or "").strip()
        if "```" in text:
            text = re.sub(r"^.*?```(?:json)?\s*", "", text).strip()
            text = re.sub(r"```.*$", "", text).strip()
        out = json.loads(text)
        if not isinstance(out, dict) or "steps" not in out or not isinstance(out["steps"], list):
            return None
        steps = out["steps"]
        if len(steps) == 0:
            return None
        url = out.get("url") or ""
        for i, s in enumerate(steps):
            if not isinstance(s, dict):
                continue
            s["step"] = i + 1
            if "action" in s and isinstance(s["action"], str):
                s["action"] = s["action"].lower().strip()
            if "description" not in s or not s["description"]:
                s["description"] = s.get("element") or ("Step %d" % (i + 1))
        if not url:
            for s in steps:
                if isinstance(s, dict) and (s.get("action") == "navigate" or s.get("action") == "goto") and s.get("value"):
                    url = s["value"]
                    break
        plan = {
            "test_name": "Generated Test",
            "url": url or "https://example.com",
            "steps": steps,
            "total_steps": len(steps),
        }
        logger.info("LLM decomposed scenario into %s atomic steps", len(steps))
        return plan
    except Exception as e:
        logger.warning("LLM decompose failed: %s", e)
        return None


def _enrich_plan_with_llm(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Use Azure OpenAI to expand/refine steps with intents and layered selectors (enterprise)."""
    try:
        from utils.azure_openai import chat_completion, create_system_message, create_user_message
    except ImportError:
        return plan
    if not os.getenv("AZURE_API_KEY"):
        return plan
    steps = plan.get("steps", [])
    if not steps:
        return plan
    sys_msg = """You are a UI test planner for enterprise e-commerce (LG, Hilti, SAP, Oracle). Output a JSON object with one key "steps": array of step objects. Each step MUST have:
- "action": navigate|click|type|verify|wait
- "element", "value", "description" as needed
- "intent": one of search_box, search_submit, cookie_accept, login, product_select, add_to_cart, cart, checkout, guest_checkout, email_field, pincode_zip, billing_shipping, pay_now, menu_shop, generic_click, generic_type
- "semantic_target": e.g. "input/search" for search box, "button" for cookie accept
- "selector": PRIMARY Playwright locator (prefer input[type=search], input[placeholder*='Search'], button:has-text('Accept'), NOT generic role=button for search/type steps)
- "selectors": array of 3-5 selectors to try in order (best first): e.g. ["input[type='search']", "input[placeholder*='Search']", "[aria-label*='Search']"]
For "search" / "type in search" use INPUT selectors only. For "click search" use search submit button. For cookie/privacy use button:has-text('Accept'). Expand high-level steps. Return only valid JSON, no markdown."""
    user_content = "Plan to refine:\n" + json.dumps({"test_name": plan.get("test_name"), "url": plan.get("url"), "steps": steps}, indent=2)
    try:
        resp = chat_completion(
            messages=[create_system_message(sys_msg), create_user_message(user_content)],
            temperature=0.2,
            max_tokens=2000,
        )
        text = (resp or "").strip()
        if "```" in text:
            text = re.sub(r"^.*?```(?:json)?\s*", "", text).strip()
            text = re.sub(r"```.*$", "", text).strip()
        out = json.loads(text)
        if isinstance(out, dict) and "steps" in out and isinstance(out["steps"], list) and len(out["steps"]) > 0:
            plan["steps"] = out["steps"]
            plan["total_steps"] = len(plan["steps"])
            logger.info("LLM enriched plan: %s steps", len(plan["steps"]))
    except Exception as e:
        logger.warning("LLM plan enrichment failed, using original: %s", e)
    _add_intents_to_steps(plan)
    return plan


class PlannerAgent:
    def __init__(self, use_playwright_agents: bool = True, use_llm: bool = True):
        """Initialize planner with optional Playwright Test Agents and LLM (Azure GPT) enrichment."""
        self.use_playwright_agents = use_playwright_agents
        self.use_llm = use_llm and bool(os.getenv("AZURE_API_KEY"))
        if use_playwright_agents:
            try:
                from services.ui_automation.agents.playwright_test_agents import PlaywrightTestAgents
                self.pw_agents = PlaywrightTestAgents()
                logger.info("🎭 Planner using Playwright Test Agents")
            except ImportError:
                logger.warning("⚠️  Playwright Test Agents not available, using fallback")
                self.use_playwright_agents = False
        
        self.action_keywords = {
            'navigate': ['go to', 'open', 'visit', 'navigate'],
            'click': ['click', 'press', 'tap'],
            'type': ['type', 'enter', 'input', 'fill'],
            'select': ['select', 'choose', 'pick'],
            'verify': ['verify', 'check', 'assert', 'validate'],
            'wait': ['wait', 'pause']
        }
    
    def _split_into_atomic_phrases(self, text: str) -> List[str]:
        """Split user scenario into smaller phrases so each can become one atomic step (no API key needed)."""
        text = (text or "").strip().strip(".,;")
        if not text:
            return []
        # First split on sentence-like boundaries
        parts = re.split(r"\s+then\s+|\s*\.\s+|\s*;\s+", text, flags=re.IGNORECASE)
        parts = [p.strip().strip(".,;") for p in parts if p.strip()]
        result = []
        for p in parts:
            # Within each part, split on " and " when it joins two actions (e.g. "click search and search for X" -> click search, search for X)
            if len(p) > 60 or (" and " in p.lower() and re.search(r"\b(click|type|fill|search|open|select|press)\b", p.lower())):
                sub = re.split(r"\s+and\s+", p, flags=re.IGNORECASE)
                sub = [s.strip().strip(".,") for s in sub if s.strip()]
                if len(sub) > 1:
                    result.extend(sub)
                    continue
            result.append(p)
        return result

    def plan(self, raw_input: str) -> Dict[str, Any]:
        """Convert raw test case to structured plan. Uses built-in splitting + short descriptions (no API key required). LLM is optional enhancement."""
        raw = (raw_input or "").strip()
        if not raw:
            return {"test_name": "Generated Test", "url": "https://example.com", "steps": [], "total_steps": 0}

        # Optional: use LLM for atomic steps when API key is set (better semantics)
        if self.use_llm and len(raw) > 60:
            llm_plan = _decompose_raw_input_with_llm(raw)
            if llm_plan and len(llm_plan.get("steps", [])) >= 2:
                _add_intents_to_steps(llm_plan)
                _inject_app_specific_steps(llm_plan)
                return _sanitize_plan(llm_plan)

        # Built-in path (no API key): split into atomic phrases and parse each with short descriptions
        lines = [line.strip() for line in raw.split('\n') if line.strip()]
        if len(lines) == 1:
            lines = self._split_into_atomic_phrases(lines[0]) or lines
        else:
            expanded = []
            for line in lines:
                if len(line) > 80:
                    expanded.extend(self._split_into_atomic_phrases(line))
                else:
                    expanded.append(line)
            lines = expanded if expanded else lines

        steps = []
        test_name = "Generated Test"
        url = None
        for i, line in enumerate(lines):
            if i == 0 and not any(kw in line.lower() for kws in self.action_keywords.values() for kw in kws):
                test_name = line
                continue
            step = self._parse_step(line, i + 1)
            if step:
                steps.append(step)
                if step.get('action') == 'navigate' and not url:
                    url = step.get('value')

        plan = {
            "test_name": test_name,
            "url": url or "https://example.com",
            "steps": steps,
            "total_steps": len(steps),
        }
        if self.use_llm and len(steps) > 3:
            plan = _enrich_plan_with_llm(plan)
        else:
            _add_intents_to_steps(plan)
        _inject_app_specific_steps(plan)
        plan = _sanitize_plan(plan)
        return plan
    
    def _parse_step(self, line: str, step_number: int) -> Dict[str, Any]:
        """Parse a single step line"""
        line_lower = line.lower()
        
        # Navigate action
        if any(kw in line_lower for kw in self.action_keywords['navigate']):
            url_match = re.search(r'https?://[^\s]+', line)
            url = url_match.group(0) if url_match else "https://example.com"
            return {
                "step": step_number,
                "action": "navigate",
                "value": url,
                "description": "Navigate to " + (url[:50] + "..." if len(url) > 50 else url),
            }
        
        # Click action
        elif any(kw in line_lower for kw in self.action_keywords['click']):
            element = self._extract_element(line)
            short = (element and element != "unknown") and ("Click " + element) or _shorten_description(line, "Click")
            return {
                "step": step_number,
                "action": "click",
                "element": element,
                "selector": self._generate_selector(element),
                "description": short,
            }
        
        # Type action
        elif any(kw in line_lower for kw in self.action_keywords['type']):
            element, value = self._extract_element_and_value(line)
            if value:
                short = "Type '%s' in %s" % (value[:40] + "..." if len(value) > 40 else value, element or "field")
            else:
                short = _shorten_description(line, "Fill")
            return {
                "step": step_number,
                "action": "type",
                "element": element,
                "selector": self._generate_selector(element),
                "value": value,
                "description": short,
            }
        
        # Select action
        elif any(kw in line_lower for kw in self.action_keywords['select']):
            element, value = self._extract_element_and_value(line)
            short = (value and ("Select %s" % value[:40])) or ("Select " + (element or "option"))
            return {
                "step": step_number,
                "action": "select",
                "element": element,
                "selector": self._generate_selector(element),
                "value": value,
                "description": short,
            }
        
        # Verify action
        elif any(kw in line_lower for kw in self.action_keywords['verify']):
            element = self._extract_element(line)
            expected = self._extract_expected_value(line)
            short = ("Verify %s" % (expected or element or "result")) or _shorten_description(line, "Verify")
            return {
                "step": step_number,
                "action": "verify",
                "element": element,
                "selector": self._generate_selector(element),
                "expected": expected,
                "description": short,
            }
        
        # Wait action
        elif any(kw in line_lower for kw in self.action_keywords['wait']):
            duration = self._extract_duration(line)
            return {
                "step": step_number,
                "action": "wait",
                "duration": duration,
                "description": "Wait %d ms" % duration,
            }
        
        # Default: short description from line
        return {
            "step": step_number,
            "action": "comment",
            "description": _shorten_description(line, "Step"),
        }
    
    def _extract_element(self, line: str) -> str:
        """Extract element identifier from line"""
        # Look for quoted strings
        matches = re.findall(r'"([^"]+)"', line)
        if matches:
            return matches[0]
        
        matches = re.findall(r"'([^']+)'", line)
        if matches:
            return matches[0]
        
        # Extract text after action keyword (better parsing)
        for keywords in self.action_keywords.values():
            for keyword in keywords:
                if keyword in line.lower():
                    parts = line.lower().split(keyword, 1)  # Split only once
                    if len(parts) > 1:
                        # Get everything after keyword, clean up
                        rest = parts[1].strip()
                        
                        # Remove common filler words at the start
                        filler_words = ['on ', 'the ', 'a ', 'an ']
                        for filler in filler_words:
                            if rest.startswith(filler):
                                rest = rest[len(filler):].strip()
                                break
                        
                        # Stop at certain words/phrases
                        stop_words = [' and ', ' then ', ',', ' don\'t', ' do not', ' dont']
                        for stop in stop_words:
                            if stop in rest:
                                rest = rest.split(stop)[0].strip()
                                break
                        
                        # Take up to first 4 words or until punctuation
                        words = rest.split()
                        if words:
                            # Smart word extraction (up to 4 words or until stop pattern)
                            element_words = []
                            for word in words[:4]:
                                if word in ['and', 'then', ',']:
                                    break
                                element_words.append(word)
                            
                            element = ' '.join(element_words) if element_words else "unknown"
                            return element
        
        return "unknown"
    
    def _extract_element_and_value(self, line: str) -> tuple:
        """Extract element and value from line"""
        # Look for pattern: action "element" with/as "value"
        matches = re.findall(r'"([^"]+)"', line)
        if len(matches) >= 2:
            return matches[0], matches[1]
        elif len(matches) == 1:
            return matches[0], ""
        
        element = self._extract_element(line)
        value = ""
        
        # Try to extract value after 'with', 'as', 'to'
        for separator in [' with ', ' as ', ' to ', ' value ']:
            if separator in line.lower():
                parts = line.lower().split(separator)
                if len(parts) > 1:
                    value = parts[1].strip()
                    break
        
        return element, value
    
    def _extract_expected_value(self, line: str) -> str:
        """Extract expected value for verification"""
        matches = re.findall(r'"([^"]+)"', line)
        if matches:
            return matches[-1]  # Last quoted string is usually expected value
        
        return ""
    
    def _extract_duration(self, line: str) -> int:
        """Extract wait duration in milliseconds"""
        # Look for numbers followed by 'seconds' or 'ms'
        match = re.search(r'(\d+)\s*(second|sec|ms|millisecond)', line.lower())
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            if 'ms' in unit or 'millisecond' in unit:
                return value
            else:
                return value * 1000
        
        return 1000  # Default 1 second
    
    def _generate_selector(self, element: str) -> str:
        """Generate intelligent CSS selector from element description"""
        # Try to identify selector type
        if element.startswith('#'):
            return element  # Already an ID selector
        elif element.startswith('.'):
            return element  # Already a class selector
        elif element.startswith('['):
            return element  # Already an attribute selector
        
        element_lower = element.lower()
        
        # Smarter patterns based on common UI elements
        if any(word in element_lower for word in ['cart', 'mycart', 'shopping cart']):
            return "a[href*='cart'], button:has-text('cart'), [aria-label*='cart']"
        elif any(word in element_lower for word in ['checkout', 'check out']):
            return "button:has-text('checkout'), a:has-text('checkout'), [name='checkout'], .checkout-button"
        elif any(word in element_lower for word in ['add to cart', 'add cart']):
            return "button:has-text('Add to cart'), button[name='add'], [id*='add-to-cart'], .add-to-cart"
        elif any(word in element_lower for word in ['continue as guest', 'guest', 'continue']):
            return "button:has-text('Continue as guest'), button:has-text('guest'), a:has-text('guest')"
        elif any(word in element_lower for word in ['sign', 'signin', 'sign in', 'login']):
            return "button:has-text('Sign'), a:has-text('Sign'), [aria-label*='sign']"
        elif any(word in element_lower for word in ['pay now', 'paynow', 'payment']):
            return "button:has-text('Pay now'), button[type='submit'], [name='paynow']"
        elif any(word in element_lower for word in ['shirt', 'tshirt', 't-shirt']):
            return "a:has-text('shirt'), [aria-label*='shirt'], .product:has-text('shirt')"
        elif 'button' in element_lower:
            button_text = element.replace('button', '').strip()
            return f"button:has-text('{button_text}'), [aria-label*='{button_text}']"
        elif 'link' in element_lower:
            link_text = element.replace('link', '').strip()
            return f"a:has-text('{link_text}')"
        elif any(word in element_lower for word in ['username', 'email', 'user']):
            return "input[name*='email'], input[type='email'], input[name*='username'], #email, #username"
        elif 'password' in element_lower:
            return "input[type='password'], input[name='password'], #password"
        elif any(word in element_lower for word in ['first name', 'firstname']):
            return "input[name*='first'], input[placeholder*='First'], #firstName, #first_name"
        elif any(word in element_lower for word in ['last name', 'lastname']):
            return "input[name*='last'], input[placeholder*='Last'], #lastName, #last_name"
        elif 'address' in element_lower:
            return "input[name*='address'], textarea[name*='address'], #address"
        elif 'city' in element_lower:
            return "input[name*='city'], #city"
        elif any(word in element_lower for word in ['zip', 'postal']):
            return "input[name*='zip'], input[name*='postal'], #zip, #postalCode"
        elif 'phone' in element_lower:
            return "input[name*='phone'], input[type='tel'], #phone"
        elif 'submit' in element_lower:
            return "button[type='submit'], input[type='submit']"
        # Enterprise / LG / Hilti style
        elif any(w in element_lower for w in ['search', 'search box']):
            return "input[type='search'], input[placeholder*='Search'], [aria-label*='search'], .search-input, #search"
        elif any(w in element_lower for w in ['menu', 'open menu', 'hamburger']):
            return "button[aria-label*='menu'], button[aria-label*='Menu'], .menu-toggle, .hamburger, [class*='menu']"
        elif any(w in element_lower for w in ['cookie', 'accept', 'accept all']):
            return "button:has-text('Accept'), button:has-text('Accept all'), a:has-text('Accept'), [id*='cookie'] button, .cookie-accept"
        elif any(w in element_lower for w in ['shop', 'store']):
            return "a:has-text('Shop'), a[href*='shop'], [aria-label*='shop']"
        elif any(w in element_lower for w in ['product', 'item', 'select product']):
            return "a[href*='product'], .product a, [data-product], article a, .card a"
        elif any(w in element_lower for w in ['my account', 'account', 'my lg', 'mylg']):
            return "a:has-text('My'), a:has-text('Account'), [aria-label*='account'], .account-link"
        elif any(w in element_lower for w in ['sign in', 'signin', 'login', 'log in']):
            return "a:has-text('Sign in'), a:has-text('Login'), button:has-text('Sign in'), [href*='login']"
        elif any(w in element_lower for w in ['register', 'join', 'sign up']):
            return "a:has-text('Register'), a:has-text('Join'), a:has-text('Sign up')"
        elif any(w in element_lower for w in ['cart', 'basket']):
            return "a[href*='cart'], a:has-text('Cart'), [aria-label*='cart'], .cart-icon"
        elif any(w in element_lower for w in ['support', 'contact', 'help']):
            return "a:has-text('Support'), a:has-text('Contact'), a:has-text('Help')"
        # Deep E2E: first product, checkout, payment, guest, verify
        elif any(w in element_lower for w in ['first product', 'first product link', 'first product in search', 'first result']):
            return "a[href*='product'], .product a, [data-product-id] a, .product-card a, article a, .list-item a"
        elif any(w in element_lower for w in ['first monitor product', 'first product']):
            return "a[href*='product'], .product a, .card a, article a, [data-product] a"
        elif any(w in element_lower for w in ['proceed to checkout', 'checkout', 'check out']):
            return "button:has-text('Checkout'), a:has-text('Checkout'), button:has-text('Proceed'), a:has-text('Proceed'), [data-action='checkout'], .checkout-btn"
        elif any(w in element_lower for w in ['continue as guest', 'guest', 'continue as guest or continue']):
            return "button:has-text('Guest'), a:has-text('Guest'), button:has-text('Continue'), a:has-text('Continue as guest')"
        elif any(w in element_lower for w in ['email', 'email field']):
            return "input[type='email'], input[name*='email'], input[placeholder*='Email'], #email"
        elif any(w in element_lower for w in ['view cart', 'cart or view cart', 'open cart']):
            return "a:has-text('Cart'), a:has-text('View cart'), [aria-label*='cart'], a[href*='cart']"
        elif 'verify' in element_lower or 'reach' in element_lower:
            return "body"  # verification step target
        else:
            element_clean = element.lower().replace(' ', '-')
            return f"text={element}, [aria-label*='{element}'], [placeholder*='{element}'], #{element_clean}"
