"""
Base component – wraps Playwright page with domain actions.
"""
from abc import ABC
from typing import Any, Optional
import re


class PageComponent(ABC):
    """Base for all page-type components."""

    def __init__(self, page: Any):
        self.page = page

    async def click_search_icon(self) -> bool:
        """Open search (click search icon/link)."""
        try:
            loc = self.page.get_by_role("link", name=re.compile("search", re.I)).first
            await loc.wait_for(state="visible", timeout=5000)
            await loc.click(timeout=10000)
            await self.page.wait_for_timeout(1000)
            return True
        except Exception:
            pass
        try:
            loc = self.page.get_by_role("button", name=re.compile("search", re.I)).first
            await loc.click(timeout=10000)
            await self.page.wait_for_timeout(1000)
            return True
        except Exception:
            pass
        return False
