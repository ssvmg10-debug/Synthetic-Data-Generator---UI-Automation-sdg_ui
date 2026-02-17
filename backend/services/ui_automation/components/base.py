"""
Base component – wraps Playwright page with domain actions.
"""
from abc import ABC
from typing import Any, Optional
import re
import logging

logger = logging.getLogger(__name__)


class PageComponent(ABC):
    """Base for all page-type components."""

    def __init__(self, page: Any):
        self.page = page

    async def click_search_icon(self) -> bool:
        """Open search (click search icon/link)."""
        # Try link with "search" text
        try:
            loc = self.page.get_by_role("link", name=re.compile("search", re.I)).first
            await loc.wait_for(state="visible", timeout=5000)
            await loc.click(timeout=10000)
            await self.page.wait_for_timeout(1000)
            logger.info("✅ Clicked search link")
            return True
        except Exception as e:
            logger.debug(f"Search link not found: {e}")
        
        # Try button with "search" text
        try:
            loc = self.page.get_by_role("button", name=re.compile("search", re.I)).first
            await loc.click(timeout=10000)
            await self.page.wait_for_timeout(1000)
            logger.info("✅ Clicked search button")
            return True
        except Exception as e:
            logger.debug(f"Search button not found: {e}")
        
        # Try CSS selector for search icon
        try:
            selectors = [
                "[data-analytics-title*='search']",
                "[aria-label*='search']",
                "button.search-button",
                ".search-icon",
                "[class*='search'][class*='icon']",
            ]
            for sel in selectors:
                try:
                    loc = self.page.locator(sel).first
                    if await loc.is_visible(timeout=2000):
                        await loc.click(timeout=8000)
                        await self.page.wait_for_timeout(1000)
                        logger.info(f"✅ Clicked search using selector: {sel}")
                        return True
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"CSS selector search failed: {e}")
        
        logger.warning("❌ Could not find search icon/button")
        return False
