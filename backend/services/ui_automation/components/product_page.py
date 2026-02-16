"""Product detail page – add to cart."""
import re
from .base import PageComponent


class ProductPageComponent(PageComponent):
    """Product detail page actions."""

    async def add_to_cart(self) -> bool:
        """Click Add to Cart / Buy Now."""
        for name in ["Add to cart", "Buy Now", "Buy", "Add to bag"]:
            try:
                loc = self.page.get_by_role("button", name=re.compile(re.escape(name), re.I)).first
                await loc.wait_for(state="visible", timeout=5000)
                await loc.scroll_into_view_if_needed(timeout=3000)
                await loc.click(timeout=10000)
                await self.page.wait_for_timeout(2000)
                return True
            except Exception:
                pass
        return False
