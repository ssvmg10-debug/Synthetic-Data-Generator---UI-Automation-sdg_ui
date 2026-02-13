"""
UI Test Healer Agent – Enterprise-grade self-healing (testRigor-level)
Multi-strategy: registry, CSS alternatives, getByRole/getByLabel, XPath, text/aria fallbacks.
"""
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
import re
import json
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

def _js_esc(s: Optional[str]) -> str:
    """Escape like generator: for single-quoted JS strings in the script."""
    if s is None:
        return ""
    return str(s).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r")


class HealerAgent:
    def __init__(self, use_playwright_agents: bool = True):
        if use_playwright_agents:
            try:
                from services.ui_automation.agents.playwright_test_agents import PlaywrightTestAgents
                self.pw_agents = PlaywrightTestAgents()
                logger.info("Healer using Playwright Test Agents")
            except ImportError:
                self.pw_agents = None
        else:
            self.pw_agents = None

    def heal(
        self,
        script: str,
        error: str,
        db: Session,
        failed_locator: Optional[str] = None,
        *,
        test_case_context: Optional[Dict[str, Any]] = None,
        plan: Optional[Dict[str, Any]] = None,
        failed_step_index: Optional[int] = None,
        steps_before_failure: Optional[List[Dict[str, Any]]] = None,
        failure_url: Optional[str] = None,
        failure_page_elements: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Attempt to heal broken test script. Uses registry, then alternatives, then LLM (with full context when provided)."""
        from models import LocatorRegistry

        healed = False
        healed_script = script
        healing_actions: List[str] = []
        used_selector: Optional[str] = None
        strategy_used = "none"

        failed = failed_locator or self._extract_failed_selector(error)
        if not failed:
            return {
                "healed": False,
                "script": script,
                "actions": healing_actions,
                "original_selector": None,
                "healed_script": script,
                "healed_locator": None,
                "strategy": "none",
                "confidence": 0.0,
            }

        # Resolve intent and url_pattern for healing memory (enterprise)
        intent, url_pattern = self._get_intent_and_url_pattern(
            plan=plan, failed_step_index=failed_step_index, failure_url=failure_url, failed_selector=failed
        )

        def _replace(script_text: str, old_sel: str, new_sel: str) -> Optional[str]:
            """Replace selector in script, handling both raw and JS-escaped forms."""
            if not old_sel or not new_sel:
                return None
            if old_sel in script_text:
                return script_text.replace(old_sel, new_sel)
            old_esc = _js_esc(old_sel)
            new_esc = _js_esc(new_sel)
            if old_esc in script_text:
                return script_text.replace(old_esc, new_esc)
            return None

        # 0) Healing memory (url_pattern + intent) – use previously successful selector for this page + intent
        if url_pattern and intent:
            memory_key = f"{url_pattern}::{intent}"
            memory_entry = db.query(LocatorRegistry).filter(LocatorRegistry.element == memory_key).first()
            if memory_entry and memory_entry.primary_locator:
                replaced = _replace(script, failed, memory_entry.primary_locator)
                if replaced:
                    healed_script = replaced
                    healing_actions.append(f"Memory: '{failed}' -> '{memory_entry.primary_locator}'")
                    healed = True
                    used_selector = memory_entry.primary_locator
                    strategy_used = "memory"

        # 1) Registry (by failed locator)
        if not healed:
            registry_entry = db.query(LocatorRegistry).filter(
                LocatorRegistry.primary_locator == failed
            ).first()
            if registry_entry and registry_entry.healed_locators:
                for alt in registry_entry.healed_locators:
                    replaced = _replace(script, failed, alt)
                    if replaced:
                        healed_script = replaced
                        healing_actions.append(f"Registry: '{failed}' -> '{alt}'")
                        healed = True
                        used_selector = alt
                        strategy_used = "registry"
                        break

        # 2) Generate alternatives (multi-strategy)
        if not healed:
            alternatives = self._generate_alternative_selectors(failed)
            for alt in alternatives:
                replaced = _replace(script, failed, alt)
                if replaced:
                    healed_script = replaced
                    healing_actions.append(f"Alternative: '{failed}' -> '{alt}'")
                    healed = True
                    used_selector = alt
                    strategy_used = "alternative"
                    break
        # 3) LLM with full test-case context (or fallback to context-free LLM)
        if not healed and os.getenv("AZURE_API_KEY"):
            if test_case_context or plan or steps_before_failure is not None:
                llm_alternatives = self._llm_suggest_selectors_with_context(
                    failed, error,
                    test_case_context=test_case_context,
                    plan=plan,
                    failed_step_index=failed_step_index,
                    steps_before_failure=steps_before_failure,
                    failure_url=failure_url,
                    failure_page_elements=failure_page_elements,
                )
            else:
                llm_alternatives = self._llm_suggest_selectors(failed, error)
            for alt in (llm_alternatives or []):
                replaced = _replace(script, failed, alt)
                if replaced:
                    healed_script = replaced
                    healing_actions.append(f"LLM: '{failed}' -> '{alt}'")
                    healed = True
                    used_selector = alt
                    strategy_used = "llm"
                    break

        confidence = 0.95 if strategy_used == "memory" else 0.9 if strategy_used == "registry" else 0.8 if strategy_used == "llm" else 0.7 if healed else 0.0
        result = {
            "healed": healed,
            "script": healed_script,
            "healed_script": healed_script,
            "actions": healing_actions,
            "original_selector": failed,
            "healed_locator": used_selector,
            "strategy": strategy_used,
            "confidence": confidence,
        }
        # Persist to healing memory (url_pattern + intent) for future runs
        if healed and used_selector and url_pattern and intent:
            self._save_healing_memory(db, url_pattern, intent, used_selector)
            # Also save to semantic UIElement registry (Katalon-style) for Generator to use next run
            try:
                from services.ui_automation.registry import save_healed_selector
                full_url = failure_url or (plan.get("url") if plan else "") or ""
                if full_url:
                    save_healed_selector(db, full_url, intent, used_selector)
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
        return result

    def _get_intent_and_url_pattern(
        self,
        plan: Optional[Dict[str, Any]] = None,
        failed_step_index: Optional[int] = None,
        failure_url: Optional[str] = None,
        failed_selector: Optional[str] = None,
    ) -> tuple:
        """Return (intent, url_pattern) for healing memory. url_pattern is host + first path segment."""
        intent = "generic_click"
        if plan and plan.get("steps") and failed_step_index is not None and 1 <= failed_step_index <= len(plan["steps"]):
            step = plan["steps"][failed_step_index - 1]
            intent = step.get("intent") or "generic_click"
        url_pattern = ""
        if failure_url:
            try:
                from urllib.parse import urlparse
                p = urlparse(failure_url)
                host = (p.netloc or "").replace("www.", "")
                path = (p.path or "/").strip("/").split("/")
                url_pattern = host + ("/" + path[0] if path and path[0] else "")
            except Exception:
                url_pattern = (failure_url or "")[:80]
        elif plan and plan.get("url"):
            try:
                from urllib.parse import urlparse
                p = urlparse(plan["url"])
                url_pattern = (p.netloc or "").replace("www.", "")
            except Exception:
                url_pattern = str(plan.get("url", ""))[:80]
        return (intent, url_pattern)

    def _save_healing_memory(self, db: Session, url_pattern: str, intent: str, selector: str) -> None:
        """Store successful selector for (url_pattern, intent) for future runs."""
        from models import LocatorRegistry
        key = f"{url_pattern}::{intent}"
        entry = db.query(LocatorRegistry).filter(LocatorRegistry.element == key).first()
        if entry:
            entry.primary_locator = selector
            entry.updated_at = datetime.utcnow()
        else:
            db.add(LocatorRegistry(element=key, primary_locator=selector, healed_locators=[]))
        db.commit()

    def _extract_failed_selector(self, error: str) -> Optional[str]:
        """Extract failed selector from Playwright/Chromium error messages."""
        if not error:
            return None
        patterns = [
            r"Timeout\s+\d+ms\s+waiting\s+for\s+selector\s+[`\"']([^`\"']+)[`\"']",
            r"locator\(['\"]([^'\"]+)['\"]\)",
            r"selector\s+['\"]([^'\"]+)['\"]\s+not\s+found",
            r"waiting\s+for\s+selector\s+[`\"']([^`\"']+)[`\"']",
            r"Unknown\s+selector\s*:\s*['\"]?([^'\"]+)['\"]?",
            r"Error:\s+[\w\s]+selector\s+['\"]([^'\"]+)['\"]",
            r"strict\s+mode\s+violation.*selector\s+['\"]([^'\"]+)['\"]",
            r"[\"']([#\.\w\[\]=*^$\[\]():,\s\-]+)[\"']\s+resolved to",
        ]
        for pattern in patterns:
            match = re.search(pattern, error, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        return None

    def _llm_suggest_selectors_with_context(
        self,
        failed_selector: str,
        error: str,
        *,
        test_case_context: Optional[Dict[str, Any]] = None,
        plan: Optional[Dict[str, Any]] = None,
        failed_step_index: Optional[int] = None,
        steps_before_failure: Optional[List[Dict[str, Any]]] = None,
        failure_url: Optional[str] = None,
        failure_page_elements: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        """Use Azure OpenAI with full test-case context: steps that ran, failed step, URL, and page elements."""
        try:
            from utils.azure_openai import chat_completion, create_system_message, create_user_message
        except ImportError:
            return []
        failed_intent = "generic_click"
        if plan and plan.get("steps") and failed_step_index is not None and 1 <= failed_step_index <= len(plan["steps"]):
            failed_step = plan["steps"][failed_step_index - 1]
            failed_intent = failed_step.get("intent") or "generic_click"
        sys_msg = (
            "You are a UI test healer for enterprise UIs. You are given: the failed selector, error, and optionally "
            "the failed step intent, steps that ran, page URL, and page elements. Suggest up to 3 alternative Playwright "
            "selectors that match the INTENT of the failed step. Important: if intent is search_box or generic_type, "
            "suggest INPUT-like selectors (input[type=search], input[placeholder*='...'], [aria-label*='...'], getByLabel). "
            "If intent is search_submit or cookie_accept or generic_click, suggest BUTTON/link selectors. When elements "
            "are provided, prefer selectors that appear in the page elements list. Return only a JSON object with one "
            "key 'selectors' whose value is an array of strings. No markdown."
        )
        parts = [
            f"Failed selector: {failed_selector[:300]}",
            f"Error: {(error or '')[:500]}",
            f"Failed step intent: {failed_intent}",
        ]
        if test_case_context:
            parts.append(f"Test case: id={test_case_context.get('test_id')}, name={test_case_context.get('name')}")
            if test_case_context.get("steps"):
                parts.append("Test steps (full): " + "; ".join(str(s) for s in test_case_context["steps"][:15]))
        if failed_step_index is not None:
            parts.append(f"Failed at step index (1-based): {failed_step_index}")
        if steps_before_failure:
            before = [s.get("description", s.get("action", "")) for s in steps_before_failure[-5:]]
            parts.append("Steps that ran before failure: " + " | ".join(before))
        if plan and plan.get("steps") and failed_step_index is not None and 1 <= failed_step_index <= len(plan["steps"]):
            failed_step = plan["steps"][failed_step_index - 1]
            parts.append(f"Failed step description: {failed_step.get('description', failed_step.get('action', ''))} (element: {failed_step.get('element', '')})")
        if failure_url:
            parts.append(f"Page URL at failure: {failure_url[:400]}")
        if failure_page_elements:
            elems = failure_page_elements[:25]
            parts.append("Elements on page (tag, text, selector): " + json.dumps(elems)[:1500])
        user = "\n".join(parts)
        try:
            resp = chat_completion(
                messages=[create_system_message(sys_msg), create_user_message(user)],
                temperature=0.2,
                max_tokens=600,
            )
            text = (resp or "").strip()
            if "```" in text:
                text = re.sub(r"^.*?```(?:json)?\s*", "", text).strip()
                text = re.sub(r"```.*$", "", text).strip()
            out = json.loads(text)
            if isinstance(out, dict) and "selectors" in out:
                return [str(s).strip() for s in out["selectors"] if s and len(str(s)) < 500][:5]
            if isinstance(out, list):
                return [str(s).strip() for s in out if s and len(str(s)) < 500][:5]
        except Exception as e:
            logger.warning("LLM context-aware suggestion failed: %s", e)
        return []

    def _llm_suggest_selectors(self, failed_selector: str, error: str) -> List[str]:
        """Use Azure OpenAI to suggest alternative Playwright selectors for enterprise UIs (no context)."""
        try:
            from utils.azure_openai import chat_completion, create_system_message, create_user_message
        except ImportError:
            return []
        sys_msg = "You are a UI test expert. Given a failed Playwright locator/selector and the error, suggest 3 alternative selectors that could find the same or similar element on an enterprise e-commerce site. Use CSS, [aria-label], :has-text(), role, data attributes. Return only a JSON array of strings, e.g. [\"selector1\", \"selector2\", \"selector3\"]. No markdown or explanation."
        user = f"Failed selector: {failed_selector[:200]}\nError: {(error or '')[:300]}"
        try:
            resp = chat_completion(
                messages=[create_system_message(sys_msg), create_user_message(user)],
                temperature=0.2,
                max_tokens=400,
            )
            text = (resp or "").strip()
            if "```" in text:
                text = re.sub(r"^.*?```(?:json)?\s*", "", text).strip()
                text = re.sub(r"```.*$", "", text).strip()
            out = json.loads(text)
            if isinstance(out, list):
                return [str(s).strip() for s in out if s and len(str(s)) < 500][:5]
            if isinstance(out, dict) and "selectors" in out:
                return [str(s).strip() for s in out["selectors"] if s and len(str(s)) < 500][:5]
        except Exception as e:
            logger.warning("LLM selector suggestion failed: %s", e)
        return []

    def _generate_alternative_selectors(self, failed_selector: str) -> List[str]:
        """Generate multiple fallback selectors (CSS, role, label, placeholder, XPath, text)."""
        alternatives: List[str] = []
        if not failed_selector:
            return alternatives

        # Escape single quotes for use inside locator('...')
        def esc(s: str) -> str:
            return s.replace("\\", "\\\\").replace("'", "\\'")

        # ID -> data-testid, id contains
        if failed_selector.startswith("#"):
            id_val = failed_selector[1:].split()[0]
            alternatives.append(f"[data-testid='{id_val}']")
            alternatives.append(f"[id*='{id_val}']")
            alternatives.append(f"#{id_val}")

        # Class -> class contains, role + class
        elif failed_selector.startswith("."):
            class_val = failed_selector[1:].split()[0]
            alternatives.append(f"[class*='{esc(class_val)}']")
            alternatives.append(f".{class_val}")

        # Attribute selector
        elif failed_selector.startswith("["):
            m = re.search(r"\[(\w+)=[\"']([^\"']+)[\"']\]", failed_selector)
            if m:
                attr, val = m.group(1), m.group(2)
                alternatives.append(f"[{attr}*='{esc(val)}']")
                if attr == "name":
                    alternatives.append(f"input[name*='{esc(val)}']")
                    alternatives.append(f"[aria-label*='{esc(val)}']")
                elif attr == "data-testid":
                    alternatives.append(f"[id*='{esc(val)}']")

        # has-text / text=
        if "has-text" in failed_selector:
            m = re.search(r":has-text\(['\"]([^'\"]+)['\"]\)", failed_selector)
            if m:
                text = m.group(1)
                alternatives.append(f"text={esc(text)}")
                alternatives.append(f"text=/{re.escape(text)}/i")
                if len(text) > 3:
                    alternatives.append(f"text={esc(text[:len(text)//2])}")
        if failed_selector.strip().startswith("text="):
            text_val = failed_selector.replace("text=", "").strip().strip("'\"")
            if text_val:
                alternatives.append(f"text=/{re.escape(text_val)}/i")

        # getByRole-style: derive role and name from element description (if we had context)
        # Generic: try role button/link for short text
        for role in ["button", "link", "textbox"]:
            alternatives.append(f"role={role}")

        return alternatives

    def _extract_element_name(self, selector: str) -> str:
        if selector.startswith("#"):
            return selector[1:].split()[0]
        if selector.startswith("."):
            return selector[1:].split()[0]
        m = re.search(r":has-text\(['\"]([^'\"]+)['\"]\)", selector)
        if m:
            return m.group(1)
        return selector[:50]

    def update_registry(self, element: str, working_selector: str, db: Session) -> None:
        from models import LocatorRegistry
        entry = db.query(LocatorRegistry).filter(LocatorRegistry.element == element).first()
        if entry:
            if entry.healed_locators is None:
                entry.healed_locators = []
            if working_selector not in entry.healed_locators:
                entry.healed_locators.append(working_selector)
        else:
            db.add(LocatorRegistry(element=element, primary_locator=working_selector, healed_locators=[]))
        db.commit()
