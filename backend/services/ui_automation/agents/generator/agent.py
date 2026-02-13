"""
UI Test Generator Agent
Generates Playwright test scripts with layered selectors (enterprise-grade).
Uses intent + selector_hints and optional AKE for robust selectors.
"""
from typing import Dict, Any, List, Optional
import json
import logging

logger = logging.getLogger(__name__)


def _js_esc(s: str) -> str:
    """Escape string for use inside single-quoted JavaScript string."""
    if s is None:
        return ""
    # Also escape '/' so names can be safely embedded in JS regex literals: /name/i
    return (
        str(s)
        .replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("/", "\\/")
    )


# Intent -> AKE map key for prepending AKE-derived selectors
_INTENT_TO_AKE_KEY = {
    "search_box": "search_fields",
    "search_submit": "search_submit",
    "cookie_accept": "cookie_accept",
    "login": "login",
    "add_to_cart": "add_to_cart",
    "cart": "cart",
}


def _get_selectors_list(
    step: Dict[str, Any],
    ake_map: Optional[Dict[str, Any]] = None,
    registry_list: Optional[List[str]] = None,
) -> List[str]:
    """Return ordered list of selectors to try: registry (Katalon-style) first, then AKE, then step selectors (layered)."""
    out: List[str] = []
    if registry_list:
        for s in registry_list[:10]:
            if s and isinstance(s, str) and s.strip():
                out.append(s.strip())
    intent = step.get("intent")
    if ake_map and intent and intent in _INTENT_TO_AKE_KEY:
        try:
            from services.ui_automation.ake import selector_list_from_ake
            ake_selectors = selector_list_from_ake(ake_map, intent)
            for s in (ake_selectors or [])[:5]:
                if s and isinstance(s, str) and s.strip():
                    out.append(s.strip())
        except Exception:
            pass
    selectors = step.get("selectors")
    if isinstance(selectors, list) and selectors:
        for s in selectors[:8]:
            if isinstance(s, str) and s.strip():
                out.append(s.strip())
            elif isinstance(s, dict) and s.get("selector"):
                out.append(str(s["selector"]).strip())
    single = step.get("selector")
    if single and isinstance(single, str) and single.strip() and single.strip() not in out:
        out.append(single.strip())
    hints = step.get("selector_hints")
    if isinstance(hints, list) and hints:
        for h in hints[:5]:
            if h and str(h).strip() and str(h).strip() not in out:
                out.append(str(h).strip())
    # Dedupe preserving order
    seen = set()
    deduped = []
    for x in out:
        if x not in seen:
            seen.add(x)
            deduped.append(x)
    return deduped[:12]


class GeneratorAgent:
    def __init__(self, use_playwright_agents: bool = True):
        """Initialize generator with optional Playwright Test Agents integration"""
        self.use_playwright_agents = use_playwright_agents
        if use_playwright_agents:
            from services.ui_automation.agents.playwright_test_agents import PlaywrightTestAgents
            self.pw_agents = PlaywrightTestAgents()
            logger.info("🎭 Generator using Playwright Test Agents")
    
    def generate(
        self,
        structured_plan: Dict[str, Any],
        synthetic_data: Optional[List[Dict[str, Any]]] = None,
        language: str = "javascript",
        capture_screenshots: bool = True,
        capture_failure_context: bool = True,
        ake_map: Optional[Dict[str, Any]] = None,
        ake_script: Optional[str] = None,
        db: Optional[Any] = None,
    ) -> str:
        """Generate Playwright test script from structured plan with layered selectors.
        When db is provided, semantic registry (UIElement) selectors are tried first (Katalon-style).
        When ake_map/ake_script is provided, AKE-derived selectors for each step intent are used next.
        """
        language_normalized = (language or "javascript").lower()
        if language_normalized not in ("javascript", "typescript"):
            language_normalized = "javascript"

        test_name = structured_plan.get('test_name', 'Generated Test')
        url = structured_plan.get('url', 'https://example.com')
        steps = structured_plan.get('steps', [])
        
        script = self._generate_header(_js_esc(test_name), language=language_normalized, capture_screenshots=capture_screenshots)
        
        step_index = 1
        # Initial navigation + dynamic wait (stability / network idle)
        script += f"    await page.goto('{_js_esc(url)}', {{ waitUntil: 'domcontentloaded', timeout: 30000 }});\n"
        script += "    await page.waitForLoadState('networkidle', { timeout: 12000 }).catch(() => {});\n"
        if ake_script:
            script += "    // AKE: Application Knowledge Engine (real-time page map)\n"
            script += "    const __akeMap = await page.evaluate((s) => eval('(' + s + ')()'), " + json.dumps(ake_script) + ");\n"
        if capture_screenshots:
            script += self._screenshot_line(step_index)
            step_index += 1
        script += "\n"
        
        data_index = 0
        for step in steps:
            action = step.get('action')
            registry_list: List[str] = []
            if db:
                try:
                    from services.ui_automation.registry import get_registry_selectors
                    registry_list = get_registry_selectors(db, url, step.get("intent")) or []
                except Exception:
                    try:
                        db.rollback()
                    except Exception:
                        pass
                    registry_list = []

            if action == 'comment':
                script += f"    // {step.get('description')}\n"
            
            elif action == 'navigate':
                url_value = step.get('value', url)
                script += f"    // Navigate\n"
                script += f"    try {{\n"
                script += f"        await page.goto('{_js_esc(url_value)}', {{ waitUntil: 'domcontentloaded', timeout: 30000 }});\n"
                script += f"        await page.waitForLoadState('networkidle', {{ timeout: 10000 }}).catch(() => {{}});\n"
                script += f"    }} catch (e) {{\n"
                if capture_failure_context:
                    script += self._failure_context_catch(step_index, "navigate", "page.goto")
                script += f"        throw e;\n"
                script += f"    }}\n"
                if capture_screenshots:
                    script += self._screenshot_line(step_index)
                    step_index += 1
            
            elif action == 'click':
                selectors_list = _get_selectors_list(step, ake_map, registry_list=registry_list)
                element_name = step.get('element', 'element')
                ake_key = _INTENT_TO_AKE_KEY.get(step.get("intent")) if step.get("intent") else None
                is_cookie_intent = step.get("intent") == "cookie_accept"
                script += f"    // Click on {element_name} (layered selectors)\n"
                if selectors_list or ake_script:
                    # Ensure we AWAIT the layered click block and capture failure context so healer can act.
                    script += "    try {\n"
                    script += "        await (async () => {\n"
                    if ake_script and ake_key:
                        script += "            const __akeSel = (typeof __akeMap !== 'undefined' && __akeMap && __akeMap['" + _js_esc(ake_key) + "']) ? __akeMap['" + _js_esc(ake_key) + "'].map(x => typeof x === 'string' ? x : (x && x.selector)) : [];\n"
                        script += "            const __selectors = (__akeSel || []).filter(Boolean).concat(" + json.dumps([_js_esc(s) for s in selectors_list]) + ");\n"
                    else:
                        script += "            const __selectors = " + json.dumps([_js_esc(s) for s in selectors_list]) + ";\n"
                    script += "            let __clicked = false;\n"
                    script += "            for (const sel of __selectors) {\n"
                    script += "                try { await page.locator(sel).first().click({ timeout: 8000 }); __clicked = true; break; } catch (_) {}\n"
                    script += "            }\n"
                    script += "            if (!__clicked) {\n"
                    script += "                try { await page.getByRole('button', { name: /" + _js_esc(element_name) + "/i }).first().click({ timeout: 5000 }); __clicked = true; } catch (_) {}\n"
                    script += "                if (!__clicked) { try { await page.getByRole('link', { name: /" + _js_esc(element_name) + "/i }).first().click({ timeout: 5000 }); __clicked = true; } catch (_) {} }\n"
                    script += "                if (!__clicked) { try { await page.click('text=" + _js_esc(element_name) + "', { timeout: 5000 }); __clicked = true; } catch (_) {} }\n"
                    script += "            }\n"
                    if is_cookie_intent:
                        # Cookie banner is best-effort; don't hard-fail the whole test if not found.
                        script += "            if (!__clicked) { console.log('Cookie/consent button not found – continuing without explicit accept'); }\n"
                    else:
                        script += "            if (!__clicked) throw new Error('Click failed for all selectors: ' + __selectors.join(', '));\n"
                    script += "        })();\n"
                    script += "    } catch (e) {\n"
                    if capture_failure_context:
                        script += self._failure_context_catch(step_index, "click", element_name)
                    script += "        throw e;\n"
                    script += "    }\n"
                else:
                    script += "    try {\n"
                    script += f"        await page.getByRole('button', {{ name: /{_js_esc(element_name)}/i }}).first().click({{ timeout: 10000 }});\n"
                    script += "    } catch (e) {\n"
                    if capture_failure_context:
                        script += self._failure_context_catch(step_index, "click", element_name)
                    script += "        throw e;\n"
                    script += "    }\n"
                script += "    await page.waitForLoadState('domcontentloaded', { timeout: 10000 }).catch(() => {});\n"
                script += "    await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});\n"
                if capture_screenshots:
                    script += self._screenshot_line(step_index)
                    step_index += 1
            
            elif action == 'type':
                selectors_list = _get_selectors_list(step, ake_map, registry_list=registry_list)
                ake_key = _INTENT_TO_AKE_KEY.get(step.get("intent")) if step.get("intent") else None
                value = step.get('value', '')
                element_name = step.get('element', 'field')
                
                # Use synthetic data if available
                if synthetic_data and data_index < len(synthetic_data):
                    element = step.get('element', '').lower()
                    for key, val in synthetic_data[data_index].items():
                        if key.lower() in element or element in key.lower():
                            value = str(val)
                            break
                
                script += f"    // Fill {element_name} (layered selectors)\n"
                if selectors_list or ake_script:
                    # Ensure we AWAIT the layered type/fill block and capture failure context.
                    script += "    try {\n"
                    script += "        await (async () => {\n"
                    if ake_script and ake_key:
                        script += "            const __akeSel = (typeof __akeMap !== 'undefined' && __akeMap && __akeMap['" + _js_esc(ake_key) + "']) ? __akeMap['" + _js_esc(ake_key) + "'].map(x => typeof x === 'string' ? x : (x && x.selector)) : [];\n"
                        script += "            const __selectors = (__akeSel || []).filter(Boolean).concat(" + json.dumps([_js_esc(s) for s in selectors_list]) + ");\n"
                    else:
                        script += "            const __selectors = " + json.dumps([_js_esc(s) for s in selectors_list]) + ";\n"
                    script += "            const __val = " + json.dumps(value) + ";\n"
                    script += "            let __filled = false;\n"
                    script += "            for (const sel of __selectors) {\n"
                    script += "                try { const f = page.locator(sel).first(); await f.waitFor({ state: 'visible', timeout: 5000 }); await f.fill(__val); __filled = true; break; } catch (_) {}\n"
                    script += "            }\n"
                    script += "            if (!__filled) {\n"
                    script += "                try { await page.getByLabel(/" + _js_esc(element_name) + "/i).first().fill(__val, { timeout: 5000 }); __filled = true; } catch (_) {}\n"
                    script += "                if (!__filled) { try { await page.getByPlaceholder(/" + _js_esc(element_name) + "/i).first().fill(__val, { timeout: 5000 }); __filled = true; } catch (_) {} }\n"
                    script += "            }\n"
                    script += "            if (!__filled) throw new Error('Fill failed for all selectors: ' + __selectors.join(', '));\n"
                    script += "        })();\n"
                    script += "    } catch (e) {\n"
                    if capture_failure_context:
                        script += self._failure_context_catch(step_index, "type", element_name)
                    script += "        throw e;\n"
                    script += "    }\n"
                else:
                    script += "    try {\n"
                    script += f"        await page.getByLabel(/{_js_esc(element_name)}/i).first().fill({json.dumps(value)}, {{ timeout: 10000 }});\n"
                    script += "    } catch (e) {\n"
                    if capture_failure_context:
                        script += self._failure_context_catch(step_index, "type", element_name)
                    script += "        throw e;\n"
                    script += "    }\n"
                if capture_screenshots:
                    script += self._screenshot_line(step_index)
                    step_index += 1
            
            elif action == 'select':
                selector = step.get('selector', '')
                value = step.get('value', '')
                script += f"    try {{\n"
                script += f"        await page.selectOption('{_js_esc(selector)}', '{_js_esc(value)}');\n"
                script += f"    }} catch (e) {{\n"
                if capture_failure_context:
                    script += self._failure_context_catch(step_index, "select", selector)
                script += f"        throw e;\n"
                script += f"    }}\n"
                if capture_screenshots:
                    script += self._screenshot_line(step_index)
                    step_index += 1
            
            elif action == 'verify':
                selector = step.get('selector', 'body')
                expected = step.get('expected', '')
                desc = (step.get('description') or '').lower()
                script += f"    try {{\n"
                if expected:
                    script += f"        await expect(page.locator('{_js_esc(selector)}').first()).toContainText('{_js_esc(expected[:100])}');\n"
                elif 'visible' in desc or 'reach' in desc or 'payment' in desc or 'shipping' in desc or 'address' in desc or 'cart' in desc:
                    script += f"        await page.locator('{_js_esc(selector)}').first().waitFor({{ state: 'visible', timeout: 15000 }});\n"
                    if 'payment' in desc or 'shipping' in desc or 'checkout' in desc or 'reach' in desc:
                        script += "        const u = await page.url(); if (!/checkout|payment|order|shipping|cart|address/i.test(u)) throw new Error('Expected checkout/payment/shipping page, got: ' + u);\n"
                else:
                    script += f"        await expect(page.locator('{_js_esc(selector)}').first()).toBeVisible();\n"
                script += f"    }} catch (e) {{\n"
                if capture_failure_context:
                    script += self._failure_context_catch(step_index, "verify", selector)
                script += f"        throw e;\n"
                script += f"    }}\n"
                if capture_screenshots:
                    script += self._screenshot_line(step_index)
                    step_index += 1
            
            elif action == 'wait':
                duration = step.get('duration', 1000)
                script += f"    await page.waitForTimeout({duration});\n"
                if capture_screenshots:
                    script += self._screenshot_line(step_index)
                    step_index += 1
        
        # Add footer
        script += self._generate_footer()
        
        return script
    
    def _screenshot_line(self, step_index: int) -> str:
        """Emit one line to capture screenshot for step (writes to SCREENSHOT_DIR/step_NN.png)."""
        num = str(step_index).zfill(2)
        return f"    await page.screenshot({{ path: (process.env.SCREENSHOT_DIR || '.') + '/step_{num}.png' }}).catch(() => {{}});\n"

    def _failure_context_catch(self, step_index: int, action: str, selector: str) -> str:
        """Emit JS to write failure context (step, url, page elements) for healer (Phase 2)."""
        sel_esc = _js_esc(selector)[:200]
        return f"""        if (process.env.FAILURE_CONTEXT_PATH) {{
            try {{
                const fs = require('fs');
                const url = await page.url();
                const elements = await page.evaluate(() => {{
                    const nodes = document.querySelectorAll('a, button, [role=button], input[type=submit], [onclick]');
                    return Array.from(nodes).slice(0, 35).map(n => ({{ tag: n.tagName.toLowerCase(), text: (n.innerText || n.value || n.getAttribute('aria-label') || '').substring(0, 60) }}));
                }});
                fs.writeFileSync(process.env.FAILURE_CONTEXT_PATH, JSON.stringify({{ failed_step_index: {step_index}, failure_url: url, failure_page_elements: elements, action: '{action}', failed_selector: '{sel_esc}' }}));
            }} catch (_) {{}}
        }}
"""

    def _generate_header(self, test_name: str, language: str = "javascript", capture_screenshots: bool = True) -> str:
        """Generate script header (JS or TS). Optionally ensure SCREENSHOT_DIR is used."""
        if language == "typescript":
            return f"""import {{ test, expect }} from '@playwright/test';

test('{test_name}', async ({{ page }}) => {{
    test.setTimeout(240000);
    
"""

        return f"""const {{ test, expect }} = require('@playwright/test');

test('{test_name}', async ({{ page }}) => {{
    test.setTimeout(240000);
    
"""
    
    def _generate_footer(self) -> str:
        """Generate script footer"""
        return """
    // Test completed
});
"""
    
    def generate_pom(self, structured_plan: Dict[str, Any]) -> Dict[str, str]:
        """Generate Page Object Model structure"""
        test_name = structured_plan.get('test_name', 'Generated Test')
        steps = structured_plan.get('steps', [])
        
        # Extract unique pages/elements
        elements = {}
        for step in steps:
            if 'selector' in step:
                element_name = step.get('element', 'unknown').replace(' ', '_')
                elements[element_name] = step['selector']
        
        # Generate POM class
        page_class = f"""class TestPage {{
    constructor(page) {{
        this.page = page;
"""
        
        for element_name, selector in elements.items():
            page_class += f"        this.{element_name} = page.locator('{selector}');\n"
        
        page_class += """    }
}

module.exports = { TestPage };
"""
        
        # Generate test using POM
        test_script = f"""const {{ test, expect }} = require('@playwright/test');
const {{ TestPage }} = require('./pages/TestPage');

test('{test_name}', async ({{ page }}) => {{
    const testPage = new TestPage(page);
    await page.goto('{structured_plan.get('url', 'https://example.com')}');
    
    // Test steps
"""
        
        for step in steps:
            action = step.get('action')
            element = step.get('element', 'unknown').replace(' ', '_')
            
            if action == 'click':
                test_script += f"    await testPage.{element}.click();\n"
            elif action == 'type':
                value = step.get('value', '')
                test_script += f"    await testPage.{element}.fill('{value}');\n"
        
        test_script += "});\n"
        
        return {
            "page_object": page_class,
            "test_script": test_script
        }
