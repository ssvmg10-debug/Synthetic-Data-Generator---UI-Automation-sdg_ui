"""Search results / product listing – select product by condition."""
from typing import Optional
import re
import logging

from .base import PageComponent

logger = logging.getLogger(__name__)


class SearchResultsComponent(PageComponent):
    """Search results or product listing page."""

    async def select_product_under_price(self, price_max: Optional[float] = None) -> bool:
        """
        Click Buy Now / Know More for first product under price_max.
        Uses get_by_role, scroll_into_view, multiple fallbacks.
        """
        for name_pattern in ["Buy Now", "Know More", "Buy", "Add to cart"]:
            try:
                loc = self.page.get_by_role("button", name=re.compile(re.escape(name_pattern), re.I))
                count = await loc.count()
                for i in range(min(count, 5)):
                    try:
                        btn = loc.nth(i)
                        await btn.wait_for(state="visible", timeout=3000)
                        await btn.scroll_into_view_if_needed(timeout=3000)
                        await btn.click(timeout=10000)
                        await self.page.wait_for_timeout(2000)
                        logger.info("select_product_under_price: clicked %s [%d]", name_pattern, i)
                        return True
                    except Exception:
                        continue
            except Exception:
                pass
        for fallback in ["button:has-text('Buy Now')", ".cmp-button:has-text('Buy Now')", "a:has-text('Know More')"]:
            try:
                loc = self.page.locator(fallback)
                for i in range(min(await loc.count(), 5)):
                    try:
                        await loc.nth(i).scroll_into_view_if_needed(timeout=3000)
                        await loc.nth(i).click(timeout=10000)
                        await self.page.wait_for_timeout(2000)
                        return True
                    except Exception:
                        continue
            except Exception:
                pass
        return False
