"""Generic navigation component for any website - clicks links, menus, categories."""
from typing import Optional, List
import re
import logging

from .base import PageComponent

logger = logging.getLogger(__name__)


class NavigationComponent(PageComponent):
    """Universal navigation - handles menus, links, categories, dropdowns."""

    async def click_navigation_item(self, text: str, exact: bool = False) -> bool:
        """
        Click any navigation item by text (link, button, menu item).
        Works for: main menu, sub-menu, category links, dropdowns.
        
        Args:
            text: Text to search for (e.g., "Air Solutions", "TVs", "Products")
            exact: If True, requires exact match; if False, allows partial match
        """
        logger.info(f"🧭 Navigating to: '{text}' (exact={exact})")
        
        # Strategy 1: Try role="link" (most navigation items)
        try:
            if exact:
                loc = self.page.get_by_role("link", name=text, exact=True)
            else:
                loc = self.page.get_by_role("link", name=re.compile(re.escape(text), re.I))
            
            count = await loc.count()
            if count > 0:
                logger.debug(f"Found {count} link(s) matching '{text}'")
                await loc.first.scroll_into_view_if_needed(timeout=3000)
                await loc.first.click(timeout=8000)
                await self.page.wait_for_timeout(2000)
                logger.info(f"✅ Clicked link: {text}")
                return True
        except Exception as e:
            logger.debug(f"Link strategy failed: {e}")

        # Strategy 2: Try role="button"
        try:
            if exact:
                loc = self.page.get_by_role("button", name=text, exact=True)
            else:
                loc = self.page.get_by_role("button", name=re.compile(re.escape(text), re.I))
            
            count = await loc.count()
            if count > 0:
                logger.debug(f"Found {count} button(s) matching '{text}'")
                await loc.first.scroll_into_view_if_needed(timeout=3000)
                await loc.first.click(timeout=8000)
                await self.page.wait_for_timeout(2000)
                logger.info(f"✅ Clicked button: {text}")
                return True
        except Exception as e:
            logger.debug(f"Button strategy failed: {e}")

        # Strategy 3: Try text match (catches anything with text)
        try:
            if exact:
                loc = self.page.get_by_text(text, exact=True)
            else:
                loc = self.page.get_by_text(re.compile(re.escape(text), re.I))
            
            count = await loc.count()
            if count > 0:
                logger.debug(f"Found {count} text element(s) matching '{text}'")
                # Try first few matches
                for i in range(min(count, 3)):
                    try:
                        elem = loc.nth(i)
                        await elem.scroll_into_view_if_needed(timeout=2000)
                        await elem.click(timeout=8000)
                        await self.page.wait_for_timeout(2000)
                        logger.info(f"✅ Clicked text element: {text} [index={i}]")
                        return True
                    except Exception:
                        continue
        except Exception as e:
            logger.debug(f"Text strategy failed: {e}")

        # Strategy 4: CSS selectors for common navigation patterns
        nav_selectors = [
            f"nav a:has-text('{text}')",
            f"[class*='nav'] a:has-text('{text}')",
            f"[class*='menu'] a:has-text('{text}')",
            f"[role='navigation'] a:has-text('{text}')",
            f"header a:has-text('{text}')",
        ]
        
        for selector in nav_selectors:
            try:
                loc = self.page.locator(selector)
                if await loc.count() > 0:
                    await loc.first.scroll_into_view_if_needed(timeout=2000)
                    await loc.first.click(timeout=8000)
                    await self.page.wait_for_timeout(2000)
                    logger.info(f"✅ Clicked via selector: {selector}")
                    return True
            except Exception:
                continue

        logger.warning(f"❌ Could not find navigation item: '{text}'")
        return False

    async def click_category(self, category: str) -> bool:
        """Click product category (e.g., 'Televisions', 'Air Conditioners')."""
        return await self.click_navigation_item(category, exact=False)

    async def click_submenu(self, parent: str, child: str) -> bool:
        """
        Click hierarchical menu (hover parent, click child).
        E.g., parent="Products", child="TVs"
        """
        logger.info(f"🧭 Menu navigation: {parent} → {child}")
        
        try:
            # Hover parent to reveal submenu
            parent_loc = self.page.get_by_role("link", name=re.compile(re.escape(parent), re.I))
            if await parent_loc.count() == 0:
                parent_loc = self.page.get_by_text(re.compile(re.escape(parent), re.I))
            
            if await parent_loc.count() > 0:
                await parent_loc.first.hover(timeout=5000)
                await self.page.wait_for_timeout(1000)
                logger.debug(f"Hovered over: {parent}")
                
                # Now click child
                child_loc = self.page.get_by_role("link", name=re.compile(re.escape(child), re.I))
                if await child_loc.count() > 0:
                    await child_loc.first.click(timeout=8000)
                    await self.page.wait_for_timeout(2000)
                    logger.info(f"✅ Clicked submenu: {parent} → {child}")
                    return True
        except Exception as e:
            logger.warning(f"Submenu navigation failed: {e}")
        
        # Fallback: just try clicking child directly
        return await self.click_navigation_item(child, exact=False)

    async def navigate_breadcrumb(self, text: str) -> bool:
        """Click breadcrumb navigation."""
        logger.info(f"🍞 Breadcrumb navigation: {text}")
        
        try:
            # Look for breadcrumb navigation
            breadcrumb_selectors = [
                f"[aria-label*='breadcrumb'] a:has-text('{text}')",
                f"[class*='breadcrumb'] a:has-text('{text}')",
                f"nav[aria-label='Breadcrumb'] a:has-text('{text}')",
            ]
            
            for selector in breadcrumb_selectors:
                loc = self.page.locator(selector)
                if await loc.count() > 0:
                    await loc.first.click(timeout=8000)
                    await self.page.wait_for_timeout(2000)
                    logger.info(f"✅ Clicked breadcrumb: {text}")
                    return True
        except Exception as e:
            logger.debug(f"Breadcrumb navigation failed: {e}")
        
        return False

    async def click_any_visible_button(self, keywords: List[str]) -> bool:
        """
        Exploratory: click first visible button matching any keyword.
        Used for recovery when stuck.
        """
        logger.info(f"🔍 Looking for buttons: {keywords}")
        
        for keyword in keywords:
            try:
                loc = self.page.get_by_role("button", name=re.compile(re.escape(keyword), re.I))
                count = await loc.count()
                if count > 0:
                    for i in range(min(count, 3)):
                        try:
                            btn = loc.nth(i)
                            if await btn.is_visible(timeout=2000):
                                await btn.scroll_into_view_if_needed(timeout=2000)
                                await btn.click(timeout=8000)
                                await self.page.wait_for_timeout(1500)
                                logger.info(f"✅ Clicked button: {keyword} [index={i}]")
                                return True
                        except Exception:
                            continue
            except Exception:
                continue
        
        logger.warning("❌ No matching buttons found")
        return False
