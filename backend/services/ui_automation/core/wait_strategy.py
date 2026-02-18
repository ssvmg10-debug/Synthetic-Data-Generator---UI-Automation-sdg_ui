"""
Production Wait Strategy — Remove Random Timing Instability

Use deterministic waits after:
- Navigation
- Major CTA (Buy Now, Checkout)
- Guest / Delivery / Key steps

Sequence: networkidle → readyState complete → 600ms fixed.
"""
import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def wait_after_navigation(page: Page, timeout_ms: int = 10000) -> None:
    """After page.goto or navigation: network idle, DOM complete, then 600ms."""
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception as e:
        logger.debug(f"networkidle timeout: {e}")
    try:
        await page.wait_for_function("() => document.readyState === 'complete'", timeout=timeout_ms)
    except Exception as e:
        logger.debug(f"readyState complete timeout: {e}")
    await page.wait_for_timeout(600)


async def wait_after_major_action(page: Page, timeout_ms: int = 8000) -> None:
    """After major CTA (Buy Now, Checkout, Guest, Delivery): same sequence."""
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception as e:
        logger.debug(f"networkidle timeout: {e}")
    try:
        await page.wait_for_function("() => document.readyState === 'complete'", timeout=timeout_ms)
    except Exception as e:
        logger.debug(f"readyState complete timeout: {e}")
    await page.wait_for_timeout(600)


async def wait_for_stable_dom(page: Page, timeout_ms: int = 5000) -> None:
    """DOM content loaded then short stabilization."""
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    except Exception as e:
        logger.debug(f"domcontentloaded timeout: {e}")
    await page.wait_for_timeout(600)
