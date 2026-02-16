"""Cart page – pincode check, free delivery, proceed to checkout."""
import re
import logging
from .base import PageComponent

logger = logging.getLogger(__name__)


class CartPageComponent(PageComponent):
    """Cart / delivery check page actions."""

    async def fill_pincode_and_check(self, pincode: str) -> bool:
        """Fill pincode and click Check."""
        try:
            inp = self.page.get_by_placeholder(re.compile("incode|zip|postal", re.I)).or_(
                self.page.get_by_label(re.compile("incode|zip|postal", re.I))
            ).first
            await inp.wait_for(state="visible", timeout=5000)
            await inp.fill(pincode, timeout=5000)
            await self.page.wait_for_timeout(500)
            # Click Check
            btn = self.page.get_by_role("button", name=re.compile("check|verify|go", re.I)).first
            await btn.click(timeout=10000)
            await self.page.wait_for_timeout(2000)
            return True
        except Exception as e:
            logger.debug("fill_pincode_and_check failed: %s", e)
        return False

    async def select_free_delivery(self) -> bool:
        """Click free delivery option."""
        try:
            loc = self.page.get_by_text(re.compile("free delivery|free shipping", re.I)).first
            await loc.wait_for(state="visible", timeout=5000)
            await loc.click(timeout=10000)
            await self.page.wait_for_timeout(1500)
            return True
        except Exception:
            pass
        return False

    async def proceed_to_checkout(self) -> bool:
        """Click Checkout / Proceed to checkout."""
        for name in ["Checkout", "Proceed to checkout", "Check out"]:
            try:
                loc = self.page.get_by_role("button", name=re.compile(re.escape(name), re.I)).first
                await loc.wait_for(state="visible", timeout=5000)
                await loc.click(timeout=10000)
                await self.page.wait_for_timeout(2000)
                return True
            except Exception:
                pass
            try:
                loc = self.page.get_by_role("link", name=re.compile(re.escape(name), re.I)).first
                await loc.click(timeout=10000)
                await self.page.wait_for_timeout(2000)
                return True
            except Exception:
                pass
        return False
