"""
Intent-Based Planner
Converts natural language test cases into structured semantic intents
"""
import logging
from typing import List, Dict, Any, Optional
from openai import AsyncAzureOpenAI
import json
import os
import re
from services.ui_automation.core.intent_models import Intent, IntentType

logger = logging.getLogger(__name__)


class IntentPlanner:
    """
    Generates structured intents from natural language test cases.
    
    Key difference from old planner:
    - Outputs semantic intents, not text-based steps
    - Extracts entities (product names, pincodes)
    - Maps to domain-specific intents
    
    Example:
        Input: "Search for lg 108cm tv, click buy now for LG 4 Star AC, enter pincode 500032"
        
        Output:
        [
            Intent(intent=SEARCH_PRODUCT, query="lg 108cm tv"),
            Intent(intent=SELECT_PRODUCT, product_name="LG 4 Star AC"),
            Intent(intent=ADD_TO_CART),
            Intent(intent=SET_PINCODE, value="500032")
        ]
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_version: Optional[str] = None,
        azure_endpoint: Optional[str] = None,
        deployment_name: Optional[str] = None
    ):
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.api_version = api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        self.azure_endpoint = azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.deployment_name = deployment_name or os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4")
        
        if not all([self.api_key, self.azure_endpoint]):
            logger.warning("Azure OpenAI credentials not configured")
            self.client = None
        else:
            self.client = AsyncAzureOpenAI(
                api_key=self.api_key,
                api_version=self.api_version,
                azure_endpoint=self.azure_endpoint
            )
        
        logger.info(f"IntentPlanner initialized")
    
    async def plan(self, test_case: str, url: str) -> List[Intent]:
        """
        Generate intent-based plan from test case.
        
        Args:
            test_case: Natural language test case
            url: Starting URL
        
        Returns:
            List of Intent objects
        """
        logger.info(f"Planning intents for: {test_case[:100]}")
        
        if not self.client:
            logger.warning("No LLM client, using rule-based planner")
            return await self._rule_based_plan(test_case, url)
        
        try:
            # Build prompt
            prompt = self._build_intent_prompt(test_case, url)
            
            # Call LLM
            response = await self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=1500
            )
            
            # Parse response
            content = response.choices[0].message.content
            intents = self._parse_llm_intents(content)
            
            logger.info(f"Generated {len(intents)} intents")
            return intents
            
        except Exception as e:
            logger.error(f"LLM planning failed: {e}")
            return await self._rule_based_plan(test_case, url)
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for intent planning"""
        return """You are a test automation planner. Convert user test cases into structured semantic intents.

Do NOT output generic CLICK or TYPE instructions.
Use semantic intents that capture user goals.

Available intents:
- NAVIGATE: Navigate to URL
- SEARCH_PRODUCT: Search for product (requires query)
- SELECT_PRODUCT: Select specific product (requires product_name)
- ADD_TO_CART: Add product to cart
- VIEW_CART: View cart
- PROCEED_TO_CHECKOUT: Proceed to checkout
- SET_PINCODE: Set delivery pincode (requires value)
- SELECT_DELIVERY_OPTION: Select delivery option (requires option)
- SELECT_PAYMENT_METHOD: Select payment method (requires option)

Output format (JSON array):
[
  {"intent": "NAVIGATE", "url": "https://example.com"},
  {"intent": "SEARCH_PRODUCT", "query": "lg 108cm tv"},
  {"intent": "SELECT_PRODUCT", "product_name": "LG 4 Star Split AC"},
  {"intent": "ADD_TO_CART"},
  {"intent": "SET_PINCODE", "value": "500032"}
]

Rules:
1. Extract product names accurately
2. Map user actions to semantic intents
3. Include all required parameters
4. Do not hallucinate steps"""
    
    def _build_intent_prompt(self, test_case: str, url: str) -> str:
        """Build user prompt"""
        return f"""Convert this test case into semantic intents:

Test Case: {test_case}
Starting URL: {url}

Output JSON array of intents:"""
    
    def _parse_llm_intents(self, content: str) -> List[Intent]:
        """Parse LLM response into Intent objects"""
        try:
            # Extract JSON from response
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if not json_match:
                logger.error("No JSON array found in response")
                return []
            
            json_str = json_match.group(0)
            intent_dicts = json.loads(json_str)
            
            # Convert to Intent objects
            intents = []
            for intent_dict in intent_dicts:
                try:
                    intent = Intent(**intent_dict)
                    intents.append(intent)
                except Exception as e:
                    logger.warning(f"Invalid intent: {intent_dict} | {e}")
                    continue
            
            return intents
            
        except Exception as e:
            logger.error(f"Failed to parse intents: {e}")
            return []
    
    async def _rule_based_plan(self, test_case: str, url: str) -> List[Intent]:
        """
        Fallback rule-based planner using keyword matching.
        
        Used when LLM is not available.
        """
        logger.info("Using rule-based planner")
        
        intents = []
        test_lower = test_case.lower()
        
        # Navigate intent
        intents.append(Intent(intent=IntentType.NAVIGATE, url=url))
        
        # Search intent
        search_match = re.search(r'search for (.+?)(?:,|and|then|\.|$)', test_lower)
        if search_match:
            query = search_match.group(1).strip()
            intents.append(Intent(intent=IntentType.SEARCH_PRODUCT, query=query))
        
        # Select product intent
        product_patterns = [
            r'click buy now for (.+?)(?:,|and|then|\.|$)',
            r'select product (.+?)(?:,|and|then|\.|$)',
            r'choose (.+?)(?:,|and|then|\.|$)',
        ]
        
        for pattern in product_patterns:
            product_match = re.search(pattern, test_lower)
            if product_match:
                product_name = product_match.group(1).strip()
                intents.append(Intent(intent=IntentType.SELECT_PRODUCT, product_name=product_name))
                break
        
        # Add to cart intent
        if any(kw in test_lower for kw in ['buy now', 'add to cart', 'add to bag']):
            intents.append(Intent(intent=IntentType.ADD_TO_CART))
        
        # Pincode intent
        pincode_match = re.search(r'(?:enter|set|input) pincode (\d{5,6})', test_lower)
        if pincode_match:
            pincode = pincode_match.group(1)
            intents.append(Intent(intent=IntentType.SET_PINCODE, value=pincode))
        
        # Delivery option intent
        delivery_match = re.search(r'select delivery (?:option )?(.+?)(?:,|and|then|\.|$)', test_lower)
        if delivery_match:
            option = delivery_match.group(1).strip()
            intents.append(Intent(intent=IntentType.SELECT_DELIVERY_OPTION, option=option))
        
        # Checkout intent
        if any(kw in test_lower for kw in ['checkout', 'proceed']):
            intents.append(Intent(intent=IntentType.PROCEED_TO_CHECKOUT))
        
        logger.info(f"Rule-based planner generated {len(intents)} intents")
        return intents
