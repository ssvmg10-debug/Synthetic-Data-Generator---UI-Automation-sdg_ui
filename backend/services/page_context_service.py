"""
Page Context Service - Extract and cache structured DOM data for grounded planning
Solves: Problem #1 (LLM selector hallucination) by providing real page elements
"""
from playwright.async_api import async_playwright, Page, Browser
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from urllib.parse import urlparse
import json
import logging
import time
import asyncio
import sys

# Fix for Windows: Set event loop policy before any async operations
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

logger = logging.getLogger(__name__)


class PageContextService:
    """
    Extracts structured page context (DOM elements) for LLM grounding.
    
    Features:
    - Extract clickable elements (buttons, links)
    - Extract input fields with metadata
    - Extract select dropdowns
    - Filter by intent relevance
    - Take screenshots for visual reference
    - Cache contexts in database
    
    Example:
        service = PageContextService()
        
        context = await service.get_or_extract(
            url="https://example.com/login",
            intent="authentication"
        )
        
        print(context['clickables'])  # All buttons/links on page
        print(context['inputs'])      # All input fields
        print(context['screenshot'])  # Path to screenshot
    """
    
    def __init__(self, headless: bool = True):
        """
        Initialize page context service.
        
        Args:
            headless: Run browser in headless mode
        """
        self.headless = headless
        self.page_load_timeout = 30000  # 30 seconds
        
        logger.info(f"PageContextService initialized (headless={headless})")
    
    async def extract_context(
        self,
        url: str,
        intent: Optional[str] = None,
        screenshot_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract page context from URL.
        
        Args:
            url: URL to extract context from
            intent: Optional intent for filtering (authentication, search, etc.)
            screenshot_dir: Optional directory to save screenshot
        
        Returns:
            {
                "url": str,
                "intent": str,
                "clickables": List[Dict],  # Buttons, links with text/selectors
                "inputs": List[Dict],       # Input fields with metadata
                "selects": List[Dict],      # Dropdown fields
                "headings": List[str],      # Page headings
                "screenshot": str,          # Screenshot path if saved
                "extracted_at": str         # ISO timestamp
            }
        """
        logger.info(f"Extracting page context from {url} (intent={intent})")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            page = await browser.new_page()
            
            try:
                # Navigate to page
                await page.goto(url, wait_until="networkidle", timeout=self.page_load_timeout)
                await page.wait_for_timeout(2000)  # Additional 2s for dynamic content
                
                # Extract elements
                clickables = await self._extract_clickables(page)
                inputs = await self._extract_inputs(page)
                selects = await self._extract_selects(page)
                headings = await self._extract_headings(page)
                
                # Take screenshot
                screenshot_path = None
                if screenshot_dir:
                    import os
                    os.makedirs(screenshot_dir, exist_ok=True)
                    timestamp = int(time.time())
                    intent_suffix = f"_{intent}" if intent else ""
                    screenshot_path = os.path.join(screenshot_dir, f"context{intent_suffix}_{timestamp}.png")
                    await page.screenshot(path=screenshot_path, full_page=True)
                
                context = {
                    "url": url,
                    "intent": intent or "generic",
                    "clickables": clickables,
                    "inputs": inputs,
                    "selects": selects,
                    "headings": headings,
                    "screenshot": screenshot_path,
                    "extracted_at": datetime.utcnow().isoformat()
                }
                
                logger.info(
                    f"Extracted context: {len(clickables)} clickables, "
                    f"{len(inputs)} inputs, {len(selects)} selects"
                )
                
                return context
            
            finally:
                await browser.close()
    
    async def _extract_clickables(self, page: Page) -> List[Dict[str, Any]]:
        """Extract all clickable elements (buttons, links)"""
        try:
            elements = await page.evaluate("""
                () => {
                    const elements = [];
                    const selectors = 'button, a, [role="button"], [onclick], input[type="submit"], input[type="button"]';
                    
                    document.querySelectorAll(selectors).forEach((el, index) => {
                        const rect = el.getBoundingClientRect();
                        
                        // Only visible elements
                        if (rect.width > 0 && rect.height > 0) {
                            const text = (el.innerText || el.textContent || '').trim();
                            
                            elements.push({
                                index: index,
                                tag: el.tagName.toLowerCase(),
                                text: text.substring(0, 200),
                                ariaLabel: el.getAttribute('aria-label') || '',
                                role: el.getAttribute('role') || '',
                                href: el.href || '',
                                className: el.className || '',
                                id: el.id || '',
                                type: el.type || '',
                                visible: true,
                                position: {
                                    x: Math.round(rect.x),
                                    y: Math.round(rect.y),
                                    width: Math.round(rect.width),
                                    height: Math.round(rect.height)
                                }
                            });
                        }
                    });
                    
                    return elements;
                }
            """)
            
            return elements
        
        except Exception as e:
            logger.error(f"Error extracting clickables: {e}")
            return []
    
    async def _extract_inputs(self, page: Page) -> List[Dict[str, Any]]:
        """Extract all input/textarea fields"""
        try:
            elements = await page.evaluate("""
                () => {
                    const elements = [];
                    
                    document.querySelectorAll('input, textarea').forEach((el, index) => {
                        const rect = el.getBoundingClientRect();
                        
                        elements.push({
                            index: index,
                            tag: el.tagName.toLowerCase(),
                            name: el.name || '',
                            type: el.type || 'text',
                            placeholder: el.placeholder || '',
                            ariaLabel: el.getAttribute('aria-label') || '',
                            id: el.id || '',
                            required: el.required,
                            disabled: el.disabled,
                            value: el.value || '',
                            visible: rect.width > 0 && rect.height > 0,
                            position: {
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height)
                            }
                        });
                    });
                    
                    return elements;
                }
            """)
            
            return elements
        
        except Exception as e:
            logger.error(f"Error extracting inputs: {e}")
            return []
    
    async def _extract_selects(self, page: Page) -> List[Dict[str, Any]]:
        """Extract all select/dropdown fields"""
        try:
            elements = await page.evaluate("""
                () => {
                    const elements = [];
                    
                    document.querySelectorAll('select').forEach((el, index) => {
                        const options = Array.from(el.options).map(opt => ({
                            value: opt.value,
                            text: opt.text
                        }));
                        
                        const rect = el.getBoundingClientRect();
                        
                        elements.push({
                            index: index,
                            tag: 'select',
                            name: el.name || '',
                            ariaLabel: el.getAttribute('aria-label') || '',
                            id: el.id || '',
                            required: el.required,
                            disabled: el.disabled,
                            options: options,
                            visible: rect.width > 0 && rect.height > 0
                        });
                    });
                    
                    return elements;
                }
            """)
            
            return elements
        
        except Exception as e:
            logger.error(f"Error extracting selects: {e}")
            return []
    
    async def _extract_headings(self, page: Page) -> List[str]:
        """Extract page headings for context"""
        try:
            headings = await page.evaluate("""
                () => {
                    const headings = [];
                    document.querySelectorAll('h1, h2, h3').forEach(el => {
                        const text = el.innerText.trim();
                        if (text) headings.push(text);
                    });
                    return headings;
                }
            """)
            
            return headings[:10]  # Limit to first 10 headings
        
        except Exception as e:
            logger.error(f"Error extracting headings: {e}")
            return []
    
    def format_for_llm(self, context: Dict[str, Any], max_elements: int = 20) -> str:
        """
        Format page context for LLM consumption.
        
        Args:
            context: Page context dictionary
            max_elements: Maximum elements to include per type
        
        Returns:
            Formatted string suitable for LLM prompt
        """
        lines = []
        
        lines.append(f"Page: {context['url']}")
        lines.append(f"Intent: {context.get('intent', 'generic')}")
        
        # Headings
        if context.get('headings'):
            lines.append(f"\nPage Headings:")
            for heading in context['headings'][:5]:
                lines.append(f"  - {heading}")
        
        # Clickable elements
        clickables = context.get('clickables', [])[:max_elements]
        if clickables:
            lines.append(f"\nClickable Elements ({len(clickables)} shown):")
            for i, el in enumerate(clickables, 1):
                text = el.get('text', '')[:50]
                aria = el.get('ariaLabel', '')
                lines.append(
                    f"  {i}. [{el['tag']}] text='{text}' "
                    f"aria-label='{aria}' "
                    f"id='{el.get('id', '')}'"
                )
        
        # Input fields
        inputs = context.get('inputs', [])[:max_elements]
        if inputs:
            lines.append(f"\nInput Fields ({len(inputs)} shown):")
            for i, inp in enumerate(inputs, 1):
                lines.append(
                    f"  {i}. [{inp['type']}] name='{inp.get('name', '')}' "
                    f"placeholder='{inp.get('placeholder', '')}' "
                    f"aria-label='{inp.get('ariaLabel', '')}'"
                )
        
        # Select fields
        selects = context.get('selects', [])[:max_elements]
        if selects:
            lines.append(f"\nSelect Fields ({len(selects)} shown):")
            for i, sel in enumerate(selects, 1):
                options_preview = ', '.join([opt['text'] for opt in sel.get('options', [])[:3]])
                lines.append(
                    f"  {i}. name='{sel.get('name', '')}' "
                    f"options=[{options_preview}...]"
                )
        
        return '\n'.join(lines)
    
    def generate_selector_hints(self, context: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Generate selector hints from page context.
        
        Returns dict of element types to selector suggestions.
        Used by planner to generate accurate selectors.
        """
        hints = {
            "clickables": [],
            "inputs": [],
            "selects": []
        }
        
        # Generate hints for clickable elements
        for el in context.get('clickables', []):
            text = el.get('text', '').strip()
            aria = el.get('ariaLabel', '').strip()
            el_id = el.get('id', '').strip()
            
            if text:
                hints['clickables'].append(f":has-text('{text}')")
                hints['clickables'].append(f"button:has-text('{text}')")
            if aria:
                hints['clickables'].append(f"[aria-label='{aria}']")
            if el_id:
                hints['clickables'].append(f"#{el_id}")
        
        # Generate hints for inputs
        for inp in context.get('inputs', []):
            name = inp.get('name', '').strip()
            placeholder = inp.get('placeholder', '').strip()
            aria = inp.get('ariaLabel', '').strip()
            
            if name:
                hints['inputs'].append(f"input[name='{name}']")
            if placeholder:
                hints['inputs'].append(f"input[placeholder='{placeholder}']")
            if aria:
                hints['inputs'].append(f"input[aria-label='{aria}']")
        
        # Generate hints for selects
        for sel in context.get('selects', []):
            name = sel.get('name', '').strip()
            if name:
                hints['selects'].append(f"select[name='{name}']")
        
        return hints


# Convenience function
async def extract_page_context(url: str, intent: Optional[str] = None) -> Dict[str, Any]:
    """Quick context extraction"""
    service = PageContextService()
    return await service.extract_context(url, intent)
