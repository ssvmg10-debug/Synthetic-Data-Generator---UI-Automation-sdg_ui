"""
Generic Interrupt Handler - Layer 1 of the Flow Handler Architecture

Runs after key actions to dismiss common blocking UI:
- Modals, dialogs, overlays with OK/Continue/Close/Dismiss
- Cookie banners with Accept/Agree
- "Select delivery option" style popups

No site-specific logic - works for any application.
"""
import logging
from playwright.async_api import Page

logger = logging.getLogger(__name__)

# Common dismiss button texts (case-insensitive)
DISMISS_TEXTS = [
    "ok", "continue", "close", "dismiss", "got it", "agree", "accept",
    "select delivery", "select delivery option", "understood", "proceed",
    "yes", "confirm", "done", "acknowledge", "i understand"
]


async def handle_interrupts(page: Page, timeout_ms: int = 2500) -> int:
    """
    Look for and dismiss common blocking modals/dialogs.
    
    Returns:
        Number of interrupts dismissed (0 if none found)
    """
    dismissed = 0
    try:
        # Selectors for modal/dialog containers
        modal_selectors = [
            "[role='dialog']",
            "[role='alertdialog']",
            "dialog",
            ".modal:visible",
            "[class*='modal']:visible",
            "[class*='Modal']:visible",
            "[class*='popup']:visible",
            "[class*='overlay']:visible",
            "[class*='dialog']:visible",
        ]
        
        for selector in modal_selectors:
            try:
                modals = page.locator(selector)
                count = await modals.count()
                if count == 0:
                    continue
                
                for i in range(count):
                    try:
                        modal = modals.nth(i)
                        if not await modal.is_visible():
                            continue
                        
                        # Find dismiss buttons within this modal
                        buttons = modal.locator("button, a, [role='button'], input[type='submit']")
                        btn_count = await buttons.count()
                        
                        for j in range(min(btn_count, 5)):
                            btn = buttons.nth(j)
                            try:
                                text = (await btn.inner_text(timeout=300)).strip().lower()
                                if not text or len(text) > 50:
                                    continue
                                if any(d in text for d in DISMISS_TEXTS):
                                    await btn.click(timeout=1000)
                                    dismissed += 1
                                    logger.info(f"  🔔 Interrupt handler: dismissed '{text[:30]}'")
                                    await page.wait_for_timeout(400)
                                    break
                            except Exception:
                                continue
                        
                        if dismissed > 0:
                            break
                    except Exception:
                        continue
                
                if dismissed > 0:
                    break
            except Exception:
                continue
        
        # Fallback: look for any visible button with dismiss text (full page)
        if dismissed == 0:
            for text in DISMISS_TEXTS[:8]:
                try:
                    btn = page.get_by_role("button", name=text)
                    if await btn.count() > 0:
                        first = btn.first
                        if await first.is_visible():
                            await first.click(timeout=1000)
                            dismissed += 1
                            logger.info(f"  🔔 Interrupt handler: dismissed '{text}'")
                            await page.wait_for_timeout(400)
                            break
                except Exception:
                    continue
        
    except Exception as e:
        logger.debug(f"Interrupt handler error: {e}")
    
    return dismissed
