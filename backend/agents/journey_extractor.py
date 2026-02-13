"""
Journey Extractor - Convert natural language test cases into structured journeys
Solves: Problem #6 (UI crawler random behavior) by identifying required pages upfront
"""
from typing import Dict, Any, Optional, List
from enum import Enum
import json
import logging
import re

logger = logging.getLogger(__name__)


class TestIntent(str, Enum):
    """Standardized test intent taxonomy"""
    NAVIGATION = "navigation"
    AUTHENTICATION = "authentication"
    SEARCH = "search"
    PRODUCT_SELECT = "product_select"
    ADD_TO_CART = "add_to_cart"
    CHECKOUT = "checkout"
    PAYMENT = "payment"
    FORM_FILL = "form_fill"
    VERIFICATION = "verification"


class JourneyExtractor:
    """
    Extracts structured user journey from natural language test cases.
    
    Features:
    - Intent classification
    - Step extraction
    - Required page identification
    - Journey validation
    
    Example:
        extractor = JourneyExtractor()
        
        test_case = "Login to the website, search for laptops, add first item to cart"
        journey = extractor.extract_journey(test_case)
        
        # Returns structured journey with steps and required pages
        print(journey['steps'])  # [{"intent": "authentication", ...}, {"intent": "search", ...}]
        print(journey['required_pages'])  # ["login", "search", "product", "cart"]
    """
    
    def __init__(self, use_llm: bool = True):
        """
        Initialize journey extractor.
        
        Args:
            use_llm: Use Azure OpenAI for extraction (recommended), fallback to rule-based
        """
        self.use_llm = use_llm
        
        # Keyword mappings for rule-based extraction
        self.intent_keywords = {
            TestIntent.NAVIGATION: ["go to", "navigate", "visit", "open"],
            TestIntent.AUTHENTICATION: ["login", "signin", "sign in", "log in", "register", "signup", "sign up"],
            TestIntent.SEARCH: ["search", "find", "look for", "query"],
            TestIntent.PRODUCT_SELECT: ["select", "choose", "click on", "view", "open product"],
            TestIntent.ADD_TO_CART: ["add to cart", "add to bag", "add item", "add product"],
            TestIntent.CHECKOUT: ["checkout", "proceed", "go to cart", "review order"],
            TestIntent.PAYMENT: ["pay", "payment", "enter card", "complete order", "place order"],
            TestIntent.FORM_FILL: ["fill", "enter", "type", "input"],
            TestIntent.VERIFICATION: ["verify", "check", "assert", "validate", "should see"],
        }
        
        # Page keywords for focused crawling
        self.page_keywords = {
            "login": ["login", "signin", "sign-in", "auth", "account"],
            "signup": ["signup", "register", "sign-up", "create account"],
            "search": ["search", "find", "query"],
            "product": ["product", "item", "shop", "catalog", "category"],
            "cart": ["cart", "bag", "basket"],
            "checkout": ["checkout", "order", "purchase"],
            "payment": ["payment", "billing", "card", "pay"],
            "profile": ["profile", "account", "settings", "user"],
        }
        
        logger.info(f"JourneyExtractor initialized (use_llm={use_llm})")
    
    def extract_journey(self, test_case: str, url: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract structured journey from test case.
        
        Args:
            test_case: Natural language test case description
            url: Optional target URL for context
        
        Returns:
            {
                "journey_name": str,
                "steps": List[Dict],  # Each with intent, action, target, description
                "required_pages": List[str],  # Pages needed for journey
                "estimated_duration": int  # seconds
            }
        """
        if self.use_llm:
            try:
                return self._extract_with_llm(test_case, url)
            except Exception as e:
                logger.warning(f"LLM extraction failed, falling back to rule-based: {e}")
                return self._extract_rule_based(test_case, url)
        else:
            return self._extract_rule_based(test_case, url)
    
    def _extract_with_llm(self, test_case: str, url: Optional[str] = None) -> Dict[str, Any]:
        """Use Azure OpenAI for structured extraction"""
        try:
            from utils.azure_openai import chat_completion
        except ImportError:
            raise ImportError("Azure OpenAI not available")
        
        system_prompt = """You are a test case analyzer. Extract structured journey from natural language test cases.

Return JSON with this EXACT structure:
{
  "journey_name": "descriptive name",
  "steps": [
    {
      "step_index": 1,
      "intent": "navigation|authentication|search|product_select|add_to_cart|checkout|payment|form_fill|verification",
      "action_type": "click|fill|select|verify|navigate",
      "target": "what element to interact with",
      "value": "value to enter (for fill actions)",
      "description": "human-readable step"
    }
  ],
  "required_pages": ["login", "search", "product", "cart", "checkout"],
  "estimated_duration": 60
}

Rules:
- Each step must have ONE intent from the allowed list
- Break complex actions into atomic steps
- Identify exact pages needed (login, search, product, cart, checkout, payment, profile)
- Estimate duration based on step complexity"""

        user_prompt = f"""Test Case:
{test_case}

{f'Target URL: {url}' if url else ''}

Extract the journey structure."""

        try:
            response = chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=1000,
            )
            
            # Clean response
            text = response.strip()
            if "```json" in text:
                text = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL).group(1)
            elif "```" in text:
                text = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL).group(1)
            
            journey = json.loads(text)
            
            # Validate structure
            if not isinstance(journey.get("steps"), list):
                raise ValueError("Invalid journey structure: steps must be a list")
            
            logger.info(f"LLM extracted journey: {journey.get('journey_name')} with {len(journey['steps'])} steps")
            
            return journey
        
        except Exception as e:
            logger.error(f"LLM extraction error: {e}")
            raise
    
    def _extract_rule_based(self, test_case: str, url: Optional[str] = None) -> Dict[str, Any]:
        """Rule-based extraction as fallback"""
        
        # Split into sentences
        sentences = re.split(r'[.;,]\s*|\n', test_case)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        steps = []
        required_pages = set()
        
        for idx, sentence in enumerate(sentences, 1):
            sentence_lower = sentence.lower()
            
            # Determine intent
            intent = TestIntent.NAVIGATION
            for test_intent, keywords in self.intent_keywords.items():
                if any(keyword in sentence_lower for keyword in keywords):
                    intent = test_intent
                    break
            
            # Determine action type
            action_type = "click"
            if any(word in sentence_lower for word in ["fill", "enter", "type", "input"]):
                action_type = "fill"
            elif any(word in sentence_lower for word in ["select", "choose"]):
                action_type = "select"
            elif any(word in sentence_lower for word in ["verify", "check", "assert", "should"]):
                action_type = "verify"
            elif any(word in sentence_lower for word in ["go to", "navigate", "visit"]):
                action_type = "navigate"
            
            # Extract target (simple heuristic)
            target = sentence
            for keyword in ["click on", "select", "fill", "enter", "type", "verify", "check"]:
                if keyword in sentence_lower:
                    target = sentence_lower.split(keyword, 1)[1].strip()
                    break
            
            steps.append({
                "step_index": idx,
                "intent": intent.value,
                "action_type": action_type,
                "target": target,
                "value": None,
                "description": sentence
            })
            
            # Identify required pages
            for page, keywords in self.page_keywords.items():
                if any(keyword in sentence_lower for keyword in keywords):
                    required_pages.add(page)
        
        # Add home page by default
        required_pages.add("home")
        
        journey = {
            "journey_name": f"Test: {test_case[:50]}...",
            "steps": steps,
            "required_pages": sorted(list(required_pages)),
            "estimated_duration": len(steps) * 10  # 10s per step
        }
        
        logger.info(f"Rule-based extracted journey: {len(steps)} steps, {len(required_pages)} pages")
        
        return journey
    
    def extract_keywords_for_crawling(self, test_case: str) -> List[str]:
        """
        Extract journey keywords for focused crawling.
        
        Returns list of keywords that should be found in URLs during crawling.
        Used by focused crawler to filter relevant pages.
        
        Example:
            test_case = "Login and add to cart"
            keywords = extractor.extract_keywords_for_crawling(test_case)
            # Returns: ["login", "signin", "auth", "cart", "bag", "basket", "product"]
        """
        test_case_lower = test_case.lower()
        keywords = set()
        
        for page, page_keywords in self.page_keywords.items():
            if any(kw in test_case_lower for kw in page_keywords):
                keywords.update(page_keywords)
        
        return list(keywords)
    
    def validate_journey(self, journey: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate journey structure.
        
        Returns:
            (is_valid, error_message)
        """
        if not journey.get("steps"):
            return False, "Journey has no steps"
        
        if not isinstance(journey["steps"], list):
            return False, "Steps must be a list"
        
        # Check step structure
        for idx, step in enumerate(journey["steps"]):
            if "intent" not in step:
                return False, f"Step {idx} missing intent"
            
            if step["intent"] not in [intent.value for intent in TestIntent]:
                return False, f"Step {idx} has invalid intent: {step['intent']}"
        
        return True, None


# Convenience function
def extract_journey(test_case: str, url: Optional[str] = None, use_llm: bool = True) -> Dict[str, Any]:
    """Quick journey extraction"""
    extractor = JourneyExtractor(use_llm=use_llm)
    return extractor.extract_journey(test_case, url)
