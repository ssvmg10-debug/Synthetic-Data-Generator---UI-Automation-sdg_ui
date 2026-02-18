"""
Phase 3 - Healing Agent
AI-powered recovery when all else fails.
Mem0: persistent memory for context (retrieve before heal, add after success). Use env MEM0_API_KEY.
"""
import json
import logging
import os
from typing import Optional, Dict, Any, List
from playwright.async_api import Page
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
            # Use common Azure OpenAI environment variable names
            # Support both older and newer variable naming conventions
            api_key = (
                os.getenv("AZURE_OPENAI_KEY")
                or os.getenv("AZURE_OPENAI_API_KEY")
                or os.getenv("AZURE_API_KEY")
            )
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_ENDPOINT")
            
            if not api_key or not endpoint:
                logger.warning(
                    "Healing agent disabled: Azure OpenAI credentials not fully configured "
                    "(expected AZURE_OPENAI_KEY / AZURE_OPENAI_API_KEY / AZURE_API_KEY and AZURE_ENDPOINT / AZURE_OPENAI_ENDPOINT)"
                )
                return
            
            self.client = AzureOpenAI(
                api_key=api_key,
                api_version=os.getenv("AZURE_API_VERSION", "2024-02-01"),
                azure_endpoint=endpoint
            )
            logger.info("✅ Healing agent LLM initialized")
        except Exception as e:
            logger.warning(f"Healing agent LLM not available: {e}")

        # Mem0: optional persistent memory (env MEM0_API_KEY)
        self._mem0 = None
        try:
            mem0_key = os.getenv("MEM0_API_KEY")
            if mem0_key:
                from mem0 import MemoryClient
                self._mem0 = MemoryClient(api_key=mem0_key)
                logger.info("✅ Mem0 memory layer initialized")
        except Exception as e:
            logger.debug("Mem0 not available: %s", e)

    def _mem0_user_id(self, page: Page) -> str:
        """Stable user_id for Mem0 (per-site)."""
        try:
            url = page.url if page else ""
            return (url or "default")[:200]
        except Exception:
            return "default"

    def _mem0_search(self, page: Page, failed_target: str) -> List[Dict[str, Any]]:
        """Retrieve relevant memories for healing context."""
        if not self._mem0:
            return []
        try:
            user_id = self._mem0_user_id(page)
            query = f"UI automation healing: click failed for target '{failed_target}'"
            results = self._mem0.search(query, filters={"user_id": user_id}, limit=5)
            if isinstance(results, list):
                return results
            if isinstance(results, dict):
                return results.get("results", results.get("data", []))
            return []
        except Exception as e:
            logger.debug("Mem0 search failed: %s", e)
            return []

    def _mem0_add(self, page: Page, failed_target: str, resolved_target: str) -> None:
        """Store successful healing for future context."""
        if not self._mem0:
            return
        try:
            user_id = self._mem0_user_id(page)
            messages = [
                {"role": "user", "content": f"Click failed for: {failed_target}"},
                {"role": "assistant", "content": f"Healing succeeded by clicking: {resolved_target}"},
            ]
            self._mem0.add(messages, user_id=user_id)
        except Exception as e:
            logger.debug("Mem0 add failed: %s", e)

    async def heal_click_failure(
        self, 
        page: Page, 
        failed_target: str,
        previous_steps: list,
        test_context: Optional[Dict[str, Any]] = None,
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

        # Guard: do not use page if it was closed (e.g. after long step timeout)
        try:
            _ = page.url
        except Exception as e:
            if "closed" in str(e).lower():
                logger.warning("Healing skipped: page/context/browser has been closed")
                return None
            raise

        logger.info(f"🏥 Phase 3: Healing click failure for '{failed_target}'")
        
        try:
            # Collect visible clickable elements (expanded for checkout/delivery flows)
            async def _collect_texts(locator, limit=40):
                texts = []
                for elem in (await locator.all())[:limit]:
                    try:
                        text = (await elem.inner_text(timeout=500)).strip()
                        if text and len(text) < 100 and text not in texts:
                            texts.append(text)
                    except:
                        continue
                return texts

            button_texts = await _collect_texts(page.locator("button:visible, [role='button']:visible"))
            link_texts = await _collect_texts(page.locator("a:visible"))
            # Also capture span/div with data-testid or common CTA classes (checkout, delivery)
            extra = await _collect_texts(
                page.locator("[data-testid]:visible, [data-test-id]:visible, .cmp-button:visible, [class*='checkout']:visible, [class*='delivery']:visible, [class*='guest']:visible")
            )
            all_clickables = list(dict.fromkeys(button_texts + link_texts + extra))

            # Semantic hints for common LG/e-commerce flows
            hints = ""
            fl = failed_target.lower()
            if "guest" in fl or "complete purchase" in fl:
                hints = "\nSemantic hint: For guest checkout, look for 'Continue as guest', 'Guest checkout', 'Checkout as guest', 'Proceed without account', or similar."
            elif "free" in fl and "delivery" in fl:
                hints = "\nSemantic hint: For free delivery, look for 'Standard delivery', 'Free delivery', 'Standard', 'Free shipping', or options with ₹0 / Rs.0."
            elif "product" in fl or "any" in fl:
                hints = "\nSemantic hint: For product selection, prefer product links/cards in the main content, not navigation (Shop, Home)."

            # Mem0: retrieve past healing context for this site
            memory_context = ""
            try:
                mem_results = self._mem0_search(page, failed_target)
                if mem_results:
                    memory_context = "\nRelevant past healing (use as hint):\n"
                    for m in mem_results[:3]:
                        if isinstance(m, dict):
                            text = m.get("memory") or m.get("content") or m.get("message") or str(m)
                        else:
                            text = str(m)
                        if text:
                            memory_context += f"  - {text[:300]}\n"
            except Exception as e:
                logger.debug("Mem0 context: %s", e)

            # Build healing prompt
            prompt = f"""You are a UI automation healing agent. A click/selection instruction failed.
{memory_context}

Failed Target: "{failed_target}"
{hints}

Previous Steps Completed:
{json.dumps(previous_steps, indent=2)}

Full Test Context (if available):
{json.dumps(test_context or {}, indent=2)}

Available Clickable Elements (buttons, links, CTAs):
{json.dumps(all_clickables, indent=2)}

Task: Find the most likely alternative element to click to achieve the same goal. Return the EXACT text as shown in the list. Prefer semantic match over generic options.

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
            
            # Resolve model/deployment name from environment for Azure OpenAI
            model_name = os.getenv("AZURE_DEPLOYMENT") or "gpt-4.1"
            
            response = self.client.chat.completions.create(
                model=model_name,
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
            if "closed" in str(e).lower() or "target page" in str(e).lower():
                logger.warning("Healing agent: page/context/browser was closed — skipping")
                return None
            logger.error(f"  Healing agent error: {e}")
            return None
    
    async def apply_healing_action(
        self, page: Page, healing_action: Dict[str, Any], failed_target: Optional[str] = None
    ) -> bool:
        """
        Execute the healing action suggested by LLM.
        If failed_target is provided and healing succeeds, Mem0 memory is updated.
        """
        try:
            action = healing_action.get("action")
            target = healing_action.get("target")
            
            if action == "click":
                logger.info(f"  Applying healing: click '{target}'")
                
                strategies = [
                    ("button (exact)", lambda: page.get_by_role("button", name=target)),
                    ("button (partial)", lambda: page.get_by_role("button", name=target, exact=False)),
                    ("link (exact)", lambda: page.get_by_role("link", name=target)),
                    ("link (partial)", lambda: page.get_by_role("link", name=target, exact=False)),
                    ("text (contains)", lambda: page.get_by_text(target, exact=False)),
                ]
                for name, loc_fn in strategies:
                    try:
                        loc = loc_fn()
                        if await loc.count() > 0:
                            await loc.first.scroll_into_view_if_needed(timeout=2000)
                            await loc.first.click(timeout=5000)
                            logger.info(f"  ✅ Healing successful (strategy: {name})!")
                            if failed_target and self._mem0:
                                self._mem0_add(page, failed_target, target)
                            return True
                    except Exception as e:
                        logger.debug(f"  Healing strategy '{name}' failed: {e}")
                        continue
                
                logger.warning(f"  ❌ Healing failed: could not find '{target}'")
                return False
            
            else:
                logger.warning(f"  Unknown healing action: {action}")
                return False
                
        except Exception as e:
            logger.error(f"  Healing application failed: {e}")
            return False
