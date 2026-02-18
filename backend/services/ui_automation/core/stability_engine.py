"""
Module 7 — Stability Engine

Before each run:
- Clear cookies, clear localStorage
- Disable animations
- Wait for network idle
- Scroll to top
- Dismiss popups

After each major action:
- domcontentloaded + timeout
- force_layout_stabilization()

Eliminates random timing failures.
"""
import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def stabilize_before_run(page: Page, context=None) -> None:
    """
    Run before test execution to ensure clean, stable state.
    """
    try:
        # Clear storage (reduces session-dependent flakiness)
        try:
            await page.context.clear_cookies()
            logger.debug("  Cleared cookies")
        except Exception as e:
            logger.debug(f"  Clear cookies: {e}")

        try:
            await page.evaluate("""() => {
                try {
                    localStorage.clear();
                    sessionStorage.clear();
                } catch (e) {}
            }""")
            logger.debug("  Cleared localStorage/sessionStorage")
        except Exception as e:
            logger.debug(f"  Clear storage: {e}")

        # Disable animations (reduces timing flakiness) - init script applies on next load
        try:
            await page.add_init_script("""
                () => {
                    const style = document.createElement('style');
                    style.textContent = `
                        *, *::before, *::after {
                            animation-duration: 0.01ms !important;
                            animation-iteration-count: 1 !important;
                            transition-duration: 0.01ms !important;
                        }
                    `;
                    document.head.appendChild(style);
                }
            """)
        except Exception as e:
            logger.debug(f"  Add init script: {e}")
        try:
            if page.url and "about:blank" not in page.url:
                await page.reload(wait_until="domcontentloaded", timeout=10000)
        except Exception:
            pass
        logger.debug("  Animations disabled")

        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
        logger.debug("  Network idle / DOM ready")

        try:
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(300)
        except Exception:
            pass
        logger.debug("  Scrolled to top")

        # Dismiss any initial popups (consent/cookie)
        try:
            from .interrupt_handler import handle_interrupts
            n = await handle_interrupts(page, timeout_ms=2000)
            if n > 0:
                logger.info(f"  Dismissed {n} initial popup(s)")
        except Exception as e:
            logger.debug(f"  Initial popup dismiss: {e}")

    except Exception as e:
        logger.warning(f"Stability pre-run: {e}")


async def force_layout_stabilization(page: Page, timeout_ms: int = 500) -> None:
    """
    Force layout to settle after dynamic content (modals, SPA updates).
    """
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass
    await page.wait_for_timeout(timeout_ms)
    # Optional: wait for no pending network (lightweight)
    try:
        await page.wait_for_load_state("networkidle", timeout=min(timeout_ms + 1000, 3000))
    except Exception:
        pass


async def stabilize_after_major_action(page: Page) -> None:
    """
    Call after Buy Now, Checkout, Add to Cart, product selection, etc.
    """
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass
    try:
        await page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    await page.wait_for_timeout(500)
    await force_layout_stabilization(page, timeout_ms=500)
