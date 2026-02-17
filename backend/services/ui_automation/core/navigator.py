"""
Phase 1 - Safe Navigation
Production-grade with controlled networkidle + stabilization
"""
import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def safe_navigate(page: Page, url: str):
    """
    Production-grade navigation strategy optimized for enterprise sites.
    
    Strategy:
    1. domcontentloaded first (reliable baseline)
    2. networkidle with SHORT timeout (optional for heavy sites)
    3. Reduced stabilization buffer (2s is enough)
    4. Body check (ensure DOM ready)
    
    Key change: Network idle is OPTIONAL for heavy enterprise sites like LG.
    """
    logger.info(f"🌐 Navigating to {url}")
    
    # Step 1: Navigate with domcontentloaded (PRIMARY wait condition)
    await page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=60000
    )
    logger.info("  ✅ DOM content loaded")
    
    # Step 2: OPTIONAL network idle (short timeout, fail gracefully)
    # Do NOT block on this for heavy sites
    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
        logger.info("  ✅ Network idle")
    except Exception as e:
        logger.debug(f"Network idle timeout (OK for heavy sites): {e}")
    
    # Step 3: Reduced stabilization buffer (2s sufficient for most cases)
    await page.wait_for_timeout(2000)
    
    # Step 4: Ensure DOM is ready
    try:
        await page.locator("body").wait_for(state="attached", timeout=5000)
        logger.info("  ✅ Body attached")
    except Exception as e:
        logger.warning(f"Body check failed (may be OK): {e}")
    
    logger.info(f"✅ Navigation complete")
