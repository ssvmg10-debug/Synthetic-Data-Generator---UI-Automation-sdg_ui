"""Home page component – search, cookie accept."""
from typing import Optional
import re
import logging

from .base import PageComponent

logger = logging.getLogger(__name__)


class HomePageComponent(PageComponent):
    """Home / landing page actions."""

    async def accept_cookies(self) -> bool:
        """Accept cookie consent banner."""
        try:
            loc = self.page.get_by_role("button", name=re.compile("accept all|accept", re.I)).first
            await loc.wait_for(state="visible", timeout=5000)
            await loc.click(timeout=10000)
            await self.page.wait_for_timeout(1000)
            logger.info("✅ Accepted cookies")
            return True
        except Exception as e:
            logger.debug(f"Cookie button not found: {e}")
        
        # Fallback: Try common cookie selector patterns
        try:
            selectors = [
                "button[id*='accept']",
                "button[class*='accept']",
                "[data-testid*='accept']",
                ".cookie-accept",
                "#cookie-accept",
            ]
            for sel in selectors:
                try:
                    loc = self.page.locator(sel).first
                    if await loc.is_visible(timeout=2000):
                        await loc.click(timeout=8000)
                        await self.page.wait_for_timeout(1000)
                        logger.info(f"✅ Accepted cookies using selector: {sel}")
                        return True
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Fallback cookie selectors failed: {e}")
        
        logger.warning("❌ Could not find cookie accept button (may not exist)")
        return False

    async def search(self, query: str) -> bool:
        """Type in search box and submit."""
        if not query:
            logger.warning("❌ Empty search query provided")
            return False
        
        logger.info(f"🔍 Attempting search for: '{query}'")
        
        # Step 1: Click search icon first (opens search bar)
        search_opened = await self.click_search_icon()
        if not search_opened:
            logger.warning("⚠️ Search icon not clicked, but trying searchbox anyway")
        
        await self.page.wait_for_timeout(1500)
        
        # Step 2: Try to find and fill search box
        try:
            # Try role="searchbox" first
            loc = self.page.get_by_role("searchbox")
            await loc.first.wait_for(state="visible", timeout=5000)
            await loc.first.fill(query, timeout=10000)
            await self.page.wait_for_timeout(500)
            logger.info("✅ Filled search box (role=searchbox)")
        except Exception as e:
            logger.debug(f"Searchbox role failed: {e}")
            # Fallback: Try input type=search
            try:
                loc = self.page.locator("input[type='search']").first
                await loc.wait_for(state="visible", timeout=5000)
                await loc.fill(query, timeout=10000)
                await self.page.wait_for_timeout(500)
                logger.info("✅ Filled search box (input[type=search])")
            except Exception as e2:
                logger.debug(f"Input type=search failed: {e2}")
                # Fallback: Try any input with placeholder containing "search"
                try:
                    loc = self.page.locator("input[placeholder*='earch' i]").first
                    await loc.wait_for(state="visible", timeout=5000)
                    await loc.fill(query, timeout=10000)
                    await self.page.wait_for_timeout(500)
                    logger.info("✅ Filled search box (placeholder)")
                except Exception as e3:
                    logger.error(f"❌ Could not find search input: {e3}")
                    return False
        
        # Step 3: Submit search (Enter or search button)
        try:
            await self.page.keyboard.press("Enter")
            await self.page.wait_for_timeout(3000)
            logger.info("✅ Search submitted successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Search submission failed: {e}")
            return False
