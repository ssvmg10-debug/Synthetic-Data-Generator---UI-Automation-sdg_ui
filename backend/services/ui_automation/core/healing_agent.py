"""
Phase 3 - Healing Agent
AI-powered recovery when all else fails
"""
import logging
from playwright.async_api import Page
from typing import Optional, Dict, Any
import json
import os
from openai import AzureOpenAI

logger = logging.getLogger(__name__)


class HealingAgent:
    """
    Phase 3: AI-powered healing.
    
    Only activated when:
    - Phase 1 (deterministic) fails
    - Phase 2 (smart resolver) fails
    
    Strategy:
    - Capture DOM snapshot
    - Send to LLM with context
    - Get alternative action
    - Retry ONCE
    """
    
    def __init__(self):
        self.client = None
        try:
            # Use same env vars as planner agent
            api_key = os.getenv("AZURE_OPENAI_KEY") or os.getenv("AZURE_OPENAI_API_KEY")
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_ENDPOINT")
            
            if not api_key or not endpoint:
                logger.warning("Healing agent disabled: AZURE_OPENAI_KEY and AZURE_OPENAI_ENDPOINT not set")
                return
            
            self.client = AzureOpenAI(
                api_key=api_key,
                api_version="2024-02-01",
                azure_endpoint=endpoint
            )
            logger.info("✅ Healing agent LLM initialized")
        except Exception as e:
            logger.warning(f"Healing agent LLM not available: {e}")
    
    async def heal_click_failure(
        self, 
        page: Page, 
        failed_target: str,
        previous_steps: list
    ) -> Optional[Dict[str, Any]]:
        """
        Ask LLM for alternative action when click fails.
        
        Returns:
            {"action": "click", "target": "alternative button text"}
            or None if healing not possible
        """
        if not self.client:
            logger.warning("Healing agent not available (LLM not configured)")
            return None
        
        logger.info(f"🏥 Phase 3: Healing click failure for '{failed_target}'")
        
        try:
            # Get visible clickable elements
            buttons = await page.locator("button").all()
            button_texts = []
            for btn in buttons[:20]:  # Limit to first 20
                try:
                    text = await btn.inner_text(timeout=500)
                    if text and len(text) < 50:
                        button_texts.append(text)
                except:
                    continue
            
            links = await page.locator("a").all()
            link_texts = []
            for link in links[:20]:
                try:
                    text = await link.inner_text(timeout=500)
                    if text and len(text) < 50:
                        link_texts.append(text)
                except:
                    continue
            
            # Build healing prompt
            prompt = f"""You are a UI automation healing agent. A click instruction failed.

Failed Target: "{failed_target}"

Previous Steps Completed:
{json.dumps(previous_steps, indent=2)}

Available Buttons:
{json.dumps(button_texts, indent=2)}

Available Links:
{json.dumps(link_texts, indent=2)}

Task: Find the most likely alternative element to click to achieve the same goal.

Return ONLY valid JSON in this format:
{{
  "action": "click",
  "target": "exact button or link text",
  "confidence": 0.8,
  "reasoning": "brief explanation"
}}

If no good alternative exists, return:
{{
  "action": "abort",
  "reasoning": "explanation"
}}
"""
            
            response = self.client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": "You are a UI automation healing expert. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            # Remove markdown code blocks if present
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(result_text)
            
            if result.get("action") == "abort":
                logger.info(f"  Healing agent recommends abort: {result.get('reasoning')}")
                return None
            
            logger.info(f"  Healing agent suggests: {result.get('action')} '{result.get('target')}' (confidence: {result.get('confidence')})")
            logger.info(f"  Reasoning: {result.get('reasoning')}")
            
            return result
            
        except Exception as e:
            logger.error(f"  Healing agent error: {e}")
            return None
    
    async def apply_healing_action(self, page: Page, healing_action: Dict[str, Any]) -> bool:
        """
        Execute the healing action suggested by LLM.
        """
        try:
            action = healing_action.get("action")
            target = healing_action.get("target")
            
            if action == "click":
                logger.info(f"  Applying healing: click '{target}'")
                
                # Try button first
                btn = page.get_by_role("button", name=target)
                if await btn.count() > 0:
                    await btn.first.click(timeout=5000)
                    logger.info(f"  ✅ Healing successful!")
                    return True
                
                # Try link
                link = page.get_by_role("link", name=target)
                if await link.count() > 0:
                    await link.first.click(timeout=5000)
                    logger.info(f"  ✅ Healing successful!")
                    return True
                
                # Try text match
                elem = page.get_by_text(target, exact=False)
                if await elem.count() > 0:
                    await elem.first.click(timeout=5000)
                    logger.info(f"  ✅ Healing successful!")
                    return True
                
                logger.warning(f"  ❌ Healing failed: could not find '{target}'")
                return False
            
            else:
                logger.warning(f"  Unknown healing action: {action}")
                return False
                
        except Exception as e:
            logger.error(f"  Healing application failed: {e}")
            return False
