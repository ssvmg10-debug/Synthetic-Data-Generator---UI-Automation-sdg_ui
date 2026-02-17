"""
Page State Extractor - Comprehensive page state capture for autonomous execution.

This module extracts complete page state including:
- URL, title, breadcrumbs
- Interactive elements (buttons, links, inputs)
- Visible text blocks
- Forms and their fields
- Cart state, product info
- DOM structure summary

Used by autonomous loop and smart scoring engine.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from playwright.async_api import Page, Locator
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class InteractiveElement:
    """Represents an interactive element on the page."""
    tag: str
    text: str
    aria_label: Optional[str]
    role: Optional[str]
    element_type: str  # button, link, input, select
    visible: bool
    position: Dict[str, float]  # x, y, width, height
    attributes: Dict[str, str]
    selector: str
    confidence_score: float = 0.0


@dataclass
class FormInfo:
    """Represents a form on the page."""
    name: Optional[str]
    action: Optional[str]
    inputs: List[Dict[str, Any]]
    submit_buttons: List[str]


@dataclass
class PageState:
    """Complete page state snapshot."""
    url: str
    title: str
    breadcrumbs: List[str]
    interactive_elements: List[InteractiveElement]
    visible_text_blocks: List[str]
    forms: List[FormInfo]
    cart_count: int
    product_count: int
    has_modal: bool
    has_search_results: bool
    page_type_hint: str  # home, listing, detail, cart, checkout
    metadata: Dict[str, Any]


class PageStateExtractor:
    """Extracts comprehensive page state for autonomous execution."""
    
    def __init__(self, page: Page):
        self.page = page
        
    async def extract_state(self) -> PageState:
        """
        Extract complete page state.
        
        Returns:
            PageState object with all captured information
        """
        logger.info("📸 Extracting comprehensive page state...")
        
        try:
            # Basic page info
            url = self.page.url
            title = await self.page.title()
            
            # Extract components in parallel
            breadcrumbs = await self._extract_breadcrumbs()
            interactive_elements = await self._extract_interactive_elements()
            visible_text = await self._extract_visible_text()
            forms = await self._extract_forms()
            
            # E-commerce specific
            cart_count = await self._extract_cart_count()
            product_count = await self._extract_product_count()
            
            # Page context
            has_modal = await self._detect_modal()
            has_search_results = await self._detect_search_results()
            page_type = await self._infer_page_type()
            
            # Metadata
            metadata = await self._extract_metadata()
            
            state = PageState(
                url=url,
                title=title,
                breadcrumbs=breadcrumbs,
                interactive_elements=interactive_elements,
                visible_text_blocks=visible_text,
                forms=forms,
                cart_count=cart_count,
                product_count=product_count,
                has_modal=has_modal,
                has_search_results=has_search_results,
                page_type_hint=page_type,
                metadata=metadata
            )
            
            logger.info(f"✅ Extracted state: {len(interactive_elements)} elements, "
                       f"page_type={page_type}, cart={cart_count}")
            return state
            
        except Exception as e:
            logger.error(f"❌ Failed to extract page state: {e}")
            # Return minimal state
            return PageState(
                url=self.page.url,
                title="",
                breadcrumbs=[],
                interactive_elements=[],
                visible_text_blocks=[],
                forms=[],
                cart_count=0,
                product_count=0,
                has_modal=False,
                has_search_results=False,
                page_type_hint="unknown",
                metadata={}
            )
    
    async def _extract_breadcrumbs(self) -> List[str]:
        """Extract breadcrumb navigation."""
        try:
            breadcrumb_selectors = [
                '[aria-label*="breadcrumb"]',
                '.breadcrumb',
                '[class*="breadcrumb"]',
                'nav ol',
            ]
            
            for selector in breadcrumb_selectors:
                try:
                    breadcrumb = self.page.locator(selector).first
                    if await breadcrumb.count() > 0:
                        text = await breadcrumb.inner_text()
                        # Split by common separators
                        items = re.split(r'[>›/]', text)
                        return [item.strip() for item in items if item.strip()]
                except:
                    continue
            
            return []
        except Exception as e:
            logger.debug(f"Breadcrumb extraction failed: {e}")
            return []
    
    async def _extract_interactive_elements(self) -> List[InteractiveElement]:
        """Extract all interactive elements with metadata."""
        elements = []
        
        # Selectors for interactive elements
        selectors = {
            'button': 'button:visible',
            'link': 'a:visible',
            'input': 'input:visible',
            'select': 'select:visible',
        }
        
        for elem_type, selector in selectors.items():
            try:
                locators = self.page.locator(selector)
                count = await locators.count()
                
                # Limit to first 100 elements per type to avoid performance issues
                for i in range(min(count, 100)):
                    try:
                        elem = locators.nth(i)
                        
                        # Extract metadata
                        text = (await elem.inner_text()).strip()[:200]  # Limit text length
                        aria_label = await elem.get_attribute('aria-label')
                        role = await elem.get_attribute('role')
                        tag = await elem.evaluate('el => el.tagName.toLowerCase()')
                        
                        # Get position
                        box = await elem.bounding_box()
                        position = box if box else {'x': 0, 'y': 0, 'width': 0, 'height': 0}
                        
                        # Get key attributes
                        attributes = {}
                        for attr in ['class', 'id', 'name', 'type', 'href']:
                            val = await elem.get_attribute(attr)
                            if val:
                                attributes[attr] = val
                        
                        # Generate selector
                        elem_selector = await self._generate_selector(elem, tag, attributes)
                        
                        elements.append(InteractiveElement(
                            tag=tag,
                            text=text,
                            aria_label=aria_label,
                            role=role,
                            element_type=elem_type,
                            visible=True,
                            position=position,
                            attributes=attributes,
                            selector=elem_selector
                        ))
                        
                    except Exception as e:
                        logger.debug(f"Failed to extract element {i}: {e}")
                        continue
                        
            except Exception as e:
                logger.debug(f"Failed to extract {elem_type} elements: {e}")
                continue
        
        logger.debug(f"Extracted {len(elements)} interactive elements")
        return elements
    
    async def _generate_selector(self, elem: Locator, tag: str, attributes: Dict[str, str]) -> str:
        """Generate a reasonable selector for the element."""
        # Prefer ID
        if 'id' in attributes:
            return f"#{attributes['id']}"
        
        # Then name
        if 'name' in attributes:
            return f"{tag}[name='{attributes['name']}']"
        
        # Then class
        if 'class' in attributes:
            classes = attributes['class'].split()
            if classes:
                return f"{tag}.{classes[0]}"
        
        # Fallback to tag
        return tag
    
    async def _extract_visible_text(self) -> List[str]:
        """Extract visible text blocks from the page."""
        try:
            # Get all text content
            text_elements = self.page.locator('p:visible, h1:visible, h2:visible, h3:visible, div:visible span:visible')
            count = await text_elements.count()
            
            text_blocks = []
            for i in range(min(count, 50)):  # Limit to 50 text blocks
                try:
                    text = await text_elements.nth(i).inner_text()
                    text = text.strip()
                    if text and len(text) > 5:  # Meaningful text only
                        text_blocks.append(text[:200])  # Limit length
                except:
                    continue
            
            return text_blocks
        except Exception as e:
            logger.debug(f"Text extraction failed: {e}")
            return []
    
    async def _extract_forms(self) -> List[FormInfo]:
        """Extract all forms on the page."""
        forms = []
        
        try:
            form_locators = self.page.locator('form')
            count = await form_locators.count()
            
            for i in range(count):
                try:
                    form = form_locators.nth(i)
                    
                    name = await form.get_attribute('name')
                    action = await form.get_attribute('action')
                    
                    # Extract inputs
                    inputs = []
                    input_locators = form.locator('input, textarea, select')
                    input_count = await input_locators.count()
                    
                    for j in range(input_count):
                        inp = input_locators.nth(j)
                        inputs.append({
                            'type': await inp.get_attribute('type'),
                            'name': await inp.get_attribute('name'),
                            'placeholder': await inp.get_attribute('placeholder'),
                        })
                    
                    # Extract submit buttons
                    submit_buttons = []
                    button_locators = form.locator('button[type="submit"], input[type="submit"]')
                    btn_count = await button_locators.count()
                    
                    for j in range(btn_count):
                        btn_text = await button_locators.nth(j).inner_text()
                        submit_buttons.append(btn_text.strip())
                    
                    forms.append(FormInfo(
                        name=name,
                        action=action,
                        inputs=inputs,
                        submit_buttons=submit_buttons
                    ))
                    
                except Exception as e:
                    logger.debug(f"Failed to extract form {i}: {e}")
                    continue
            
            return forms
        except Exception as e:
            logger.debug(f"Form extraction failed: {e}")
            return []
    
    async def _extract_cart_count(self) -> int:
        """Extract cart item count."""
        try:
            cart_selectors = [
                '[class*="cart"] [class*="count"]',
                '[class*="cart"] [class*="badge"]',
                '[aria-label*="cart"]',
                '.cart-count',
                '#cart-count',
            ]
            
            for selector in cart_selectors:
                try:
                    elem = self.page.locator(selector).first
                    if await elem.count() > 0:
                        text = await elem.inner_text()
                        # Extract number
                        match = re.search(r'\d+', text)
                        if match:
                            return int(match.group())
                except:
                    continue
            
            return 0
        except Exception as e:
            logger.debug(f"Cart count extraction failed: {e}")
            return 0
    
    async def _extract_product_count(self) -> int:
        """Extract number of products visible on page."""
        try:
            product_selectors = [
                '[class*="product-card"]',
                '[class*="product-item"]',
                '[data-testid*="product"]',
                '.product',
            ]
            
            for selector in product_selectors:
                try:
                    count = await self.page.locator(selector).count()
                    if count > 0:
                        return count
                except:
                    continue
            
            return 0
        except Exception as e:
            logger.debug(f"Product count extraction failed: {e}")
            return 0
    
    async def _detect_modal(self) -> bool:
        """Detect if modal/dialog is open."""
        try:
            modal_selectors = [
                '[role="dialog"]:visible',
                '[role="alertdialog"]:visible',
                '.modal:visible',
                '[class*="modal"]:visible',
            ]
            
            for selector in modal_selectors:
                if await self.page.locator(selector).count() > 0:
                    return True
            
            return False
        except:
            return False
    
    async def _detect_search_results(self) -> bool:
        """Detect if page shows search results."""
        try:
            # Check URL
            if 'search' in self.page.url.lower() or 'query' in self.page.url.lower():
                return True
            
            # Check for results container
            results_selectors = [
                '[class*="search-results"]',
                '[class*="results"]',
                '[role="search"]',
            ]
            
            for selector in results_selectors:
                if await self.page.locator(selector).count() > 0:
                    return True
            
            # Check for "results" text
            page_text = await self.page.inner_text('body')
            if re.search(r'\d+\s+results?', page_text.lower()):
                return True
            
            return False
        except:
            return False
    
    async def _infer_page_type(self) -> str:
        """Infer page type from URL and content."""
        url = self.page.url.lower()
        
        # Check URL patterns
        if '/cart' in url or '/basket' in url:
            return 'cart'
        elif '/checkout' in url or '/payment' in url:
            return 'checkout'
        elif '/product/' in url or '/item/' in url or '/p/' in url:
            return 'detail'
        elif '/search' in url or '/results' in url:
            return 'search_results'
        elif '/category' in url or '/browse' in url:
            return 'listing'
        elif url.endswith('/') or url.count('/') <= 3:
            return 'home'
        
        # Check content
        try:
            # Product detail indicators
            if await self.page.locator('button:has-text("Add to cart"), button:has-text("Buy now")').count() > 0:
                if await self.page.locator('[class*="product-detail"], [class*="product-info"]').count() > 0:
                    return 'detail'
            
            # Listing indicators
            if await self._extract_product_count() > 3:
                return 'listing'
            
            # Cart indicators
            if 'cart' in (await self.page.title()).lower():
                return 'cart'
            
        except:
            pass
        
        return 'unknown'
    
    async def _extract_metadata(self) -> Dict[str, Any]:
        """Extract additional metadata."""
        metadata = {}
        
        try:
            # Page load state
            metadata['load_state'] = 'complete'
            
            # Viewport size
            viewport = self.page.viewport_size
            metadata['viewport'] = viewport
            
            # Number of iframes
            metadata['iframe_count'] = len(self.page.frames)
            
        except Exception as e:
            logger.debug(f"Metadata extraction failed: {e}")
        
        return metadata
