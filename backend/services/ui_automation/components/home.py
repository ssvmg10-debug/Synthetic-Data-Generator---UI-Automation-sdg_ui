"""Home page component – search, cookie accept."""
from typing import Optional
import re

from .base import PageComponent


class HomePageComponent(PageComponent):
    """Home / landing page actions."""

    async def accept_cookies(self) -> bool:
        """Accept cookie consent banner."""
        try:
            loc = self.page.get_by_role("button", name=re.compile("accept all|accept", re.I)).first
            await loc.wait_for(state="visible", timeout=5000)
            await loc.click(timeout=10000)
            await self.page.wait_for_timeout(1000)
            return True
        except Exception:
            pass
        return False

    async def search(self, query: str) -> bool:
        """Type in search box and submit."""
        try:
            # Click search icon first (opens search bar)
            if not await self.click_search_icon():
                return False
            await self.page.wait_for_timeout(1500)
            # Fill search
            loc = self.page.get_by_role("searchbox")
            await loc.first.wait_for(state="visible", timeout=5000)
            await loc.first.fill(query, timeout=10000)
            await self.page.wait_for_timeout(500)
            # Submit (Enter or search button)
            await self.page.keyboard.press("Enter")
            await self.page.wait_for_timeout(3000)
            return True
        except Exception:
            pass
        return False
