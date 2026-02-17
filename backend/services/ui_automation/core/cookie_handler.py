"""
Global Cookie Banner Handler
Environment-level logic - NOT part of test steps
"""
import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def handle_cookie_banner(page: Page) -> bool:
    """
    Enterprise-grade cookie banner handling.
    
    Strategy:
    - Try multiple common variations
    - Check main DOM and iframes
    - Non-blocking (returns True even if not found)
    - Fast timeout (don't waste time)
    
    This is environment setup, not a test step.
    """
    logger.info("🍪 Checking for cookie banner...")
    
    # Common cookie banner labels (order matters - most specific first)
    labels = [
        "Accept all",
        "Accept All",
        "ACCEPT ALL",
        "Accept all cookies",
        "Allow all",
        "Allow All",
        "I Agree",
        "Agree",
        "OK",
        "Got it",
        "Continue"
    ]
    
    # Strategy 1: Check main DOM
    for label in labels:
        try:
            btn = page.get_by_role("button", name=label)
            count = await btn.count()
            if count > 0:
                await btn.first.click(timeout=3000)
                logger.info(f"✅ Cookie banner accepted: '{label}'")
                await page.wait_for_timeout(1000)  # Let banner dismiss
                return True
        except Exception as e:
            logger.debug(f"Label '{label}' not found: {e}")
            continue
    
    # Strategy 2: Check iframes
    for frame in page.frames:
        for label in labels:
            try:
                btn = frame.get_by_role("button", name=label)
                count = await btn.count()
                if count > 0:
                    await btn.first.click(timeout=3000)
                    logger.info(f"✅ Cookie banner accepted in iframe: '{label}'")
                    await page.wait_for_timeout(1000)
                    return True
            except:
                continue
    
    # No cookie banner found - this is OK
    logger.info("ℹ️ No cookie banner detected (may be already dismissed)")
    return True
