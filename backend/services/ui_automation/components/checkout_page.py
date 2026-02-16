"""Checkout page – guest checkout, address form."""
import re
from .base import PageComponent


class CheckoutPageComponent(PageComponent):
    """Checkout / guest / address form actions."""

    async def continue_as_guest(self) -> bool:
        """Click Continue as guest."""
        for name in ["Continue as guest", "Guest", "Checkout as guest"]:
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

    async def fill_billing_address(
        self,
        name: str = "Test User",
        address: str = "123 Test St",
        phone: str = "9876543210",
        city: str = "Hyderabad",
    ) -> bool:
        """Fill billing/shipping address form."""
        try:
            # Name
            name_inp = self.page.get_by_label(re.compile("name|full name", re.I)).or_(
                self.page.get_by_placeholder(re.compile("name", re.I))
            ).first
            await name_inp.fill(name, timeout=5000)
            await self.page.wait_for_timeout(200)
            # Phone
            phone_inp = self.page.get_by_label(re.compile("phone|mobile", re.I)).or_(
                self.page.get_by_placeholder(re.compile("phone|mobile", re.I))
            ).first
            await phone_inp.fill(phone, timeout=5000)
            await self.page.wait_for_timeout(200)
            # Address
            addr_inp = self.page.get_by_label(re.compile("address", re.I)).or_(
                self.page.get_by_placeholder(re.compile("address", re.I))
            ).first
            await addr_inp.fill(address, timeout=5000)
            await self.page.wait_for_timeout(200)
            return True
        except Exception:
            pass
        return False
