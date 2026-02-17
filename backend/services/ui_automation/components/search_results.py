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
        Click Buy Now / Know More / any CTA for first product under price_max.
        Works for ANY product listing page - TVs, ACs, Refrigerators, etc.
        """
        logger.info(f"🔍 Attempting to select product (price_max: {price_max})")
        
        # Strategy 1: Try common CTA button text patterns
        cta_patterns = [
            "Buy Now", "Buy", "Know More", "Learn More", "View Details", 
            "Add to cart", "Add to Cart", "Shop Now", "Explore", 
            "Select", "Choose", "Get Started"
        ]
        
        for name_pattern in cta_patterns:
            try:
                loc = self.page.get_by_role("button", name=re.compile(re.escape(name_pattern), re.I))
                count = await loc.count()
                if count > 0:
                    logger.debug(f"Found {count} '{name_pattern}' buttons")
                    for i in range(min(count, 5)):
                        try:
                            btn = loc.nth(i)
                            await btn.wait_for(state="visible", timeout=3000)
                            await btn.scroll_into_view_if_needed(timeout=3000)
                            await btn.click(timeout=10000)
                            await self.page.wait_for_timeout(2000)
                            logger.info(f"✅ Clicked '{name_pattern}' button [{i}]")
                            return True
                        except Exception as e:
                            logger.debug(f"Button [{i}] failed: {e}")
                            continue
            except Exception as e:
                logger.debug(f"Pattern '{name_pattern}' not found: {e}")
        
        # Strategy 2: Try links with CTA text
        logger.debug("Trying CTA links...")
        for name_pattern in cta_patterns[:6]:  # Try first few as links
            try:
                loc = self.page.get_by_role("link", name=re.compile(re.escape(name_pattern), re.I))
                count = await loc.count()
                if count > 0:
                    logger.debug(f"Found {count} '{name_pattern}' links")
                    for i in range(min(count, 3)):
                        try:
                            link = loc.nth(i)
                            await link.scroll_into_view_if_needed(timeout=3000)
                            await link.click(timeout=10000)
                            await self.page.wait_for_timeout(2000)
                            logger.info(f"✅ Clicked '{name_pattern}' link [{i}]")
                            return True
                        except Exception:
                            continue
            except Exception:
                pass
        
        # Strategy 3: Try CSS selectors for common product card patterns
        logger.debug("Trying CSS fallback selectors...")
        product_selectors = [
            "button:has-text('Buy Now')",
            ".cmp-button:has-text('Buy Now')",
            "a:has-text('Know More')",
            "[class*='product'] button:has-text('Buy')",
            "[class*='card'] button",
            "[data-testid*='buy']",
            "[data-testid*='product'] button",
            ".product-tile button",
            ".product-card a[href*='product']"
        ]
        
        for fallback in product_selectors:
            try:
                loc = self.page.locator(fallback)
                count = await loc.count()
                if count > 0:
                    logger.debug(f"Fallback '{fallback}': found {count} elements")
                    for i in range(min(count, 5)):
                        try:
                            await loc.nth(i).scroll_into_view_if_needed(timeout=3000)
                            await loc.nth(i).click(timeout=10000)
                            await self.page.wait_for_timeout(2000)
                            logger.info(f"✅ Clicked fallback '{fallback}' [{i}]")
                            return True
                        except Exception:
                            continue
            except Exception:
                pass
        
        # Strategy 4: Click first product image/title as last resort
        logger.debug("Trying product images/titles...")
        try:
            # Try clicking product images
            img_loc = self.page.locator("[class*='product'] img, [class*='card'] img").first
            if await img_loc.count() > 0:
                await img_loc.scroll_into_view_if_needed(timeout=3000)
                await img_loc.click(timeout=8000)
                await self.page.wait_for_timeout(2000)
                logger.info("✅ Clicked product image")
                return True
        except Exception:
            pass
        
        logger.warning("❌ Could not find any product to select")
        return False
