"""
Module 4 — Dynamic UI Handling Engine (Contextual Action Router)

Before each step:
- Detect visible modals, overlays, login wall, delivery modal
- Route:
  - If login modal and step = guest checkout → click guest path
  - If delivery popup → auto resolve before next step
  - If payment iframe → switch frame automatically

Removes instability from unexpected overlays.
"""
import logging
from typing import Optional
from playwright.async_api import Page

from .popup_classifier import classify_visible_popup, dismiss_popup_by_type, PopupType
from .flow_config_loader import run_flow_handlers

logger = logging.getLogger(__name__)


async def route_before_step(
    page: Page,
    step_intent: str,
    step_target: Optional[str] = None,
    url: Optional[str] = None,
) -> bool:
    """
    Run before executing a step. Resolve blocking UI when it matches current intent.
    Loops up to 3 times to ensure cookie/consent popups are fully dismissed.
    Returns True if something was resolved (caller may re-detect state).
    """
    resolved = False
    step_intent_lower = (step_intent.value if hasattr(step_intent, "value") else str(step_intent)).lower()
    step_target_lower = (step_target or "").lower()

    # Is this step guest checkout?
    is_guest_step = "guest" in step_intent_lower or "guest" in step_target_lower

    for attempt in range(3):
        popup_result = await classify_visible_popup(page)
        if popup_result is None:
            if attempt == 0:
                logger.debug("  route_before_step: no popup detected")
            break
        popup_type, modal_locator = popup_result
        logger.info("  route_before_step: popup detected (attempt %d): %s", attempt + 1, popup_type.value)

        if popup_type == PopupType.LOGIN and is_guest_step:
            ok = await dismiss_popup_by_type(page, PopupType.LOGIN, modal_locator, prefer_guest=True)
            if ok:
                logger.info("  Contextual router: dismissed login modal with guest path")
                resolved = True
            else:
                ok = await dismiss_popup_by_type(page, PopupType.GENERIC, modal_locator)
                if ok:
                    resolved = True
        elif popup_type == PopupType.DELIVERY:
            try:
                await run_flow_handlers(page, "before_select_delivery", url=url)
            except Exception as e:
                logger.debug(f"Flow handler before_select_delivery: {e}")
            ok = await dismiss_popup_by_type(page, PopupType.DELIVERY, modal_locator)
            if ok:
                logger.info("  Contextual router: dismissed delivery modal")
                resolved = True
        elif popup_type == PopupType.CONSENT:
            ok = await dismiss_popup_by_type(page, PopupType.CONSENT, modal_locator)
            if ok:
                resolved = True
        else:
            ok = await dismiss_popup_by_type(page, PopupType.GENERIC, modal_locator)
            if ok:
                resolved = True

        if not ok:
            logger.debug("  route_before_step: could not dismiss popup, stopping")
            break
        await page.wait_for_timeout(400)

    # LG quick menu / generic overlay: try direct close selectors so main nav (e.g. search) is clickable
    if url and "lg.com" in url:
        for _ in range(2):
            try:
                close_loc = page.locator("button.al-quick-menu__close, [aria-label='close' i], .al-quick-menu button[type='button']")
                if await close_loc.count() > 0:
                    first_btn = close_loc.first
                    if await first_btn.is_visible():
                        await first_btn.click(timeout=2000)
                        logger.info("  Contextual router: closed LG quick menu")
                        resolved = True
                        break
            except Exception:
                pass
            await page.wait_for_timeout(300)
        # If modal still present, try clicking any visible "close" in dialogs
        try:
            again = await classify_visible_popup(page)
            if again and not resolved:
                _, modal2 = again
                ok2 = await dismiss_popup_by_type(page, PopupType.GENERIC, modal2)
                if ok2:
                    resolved = True
        except Exception:
            pass

    if resolved:
        await page.wait_for_timeout(800)
    return resolved


async def ensure_payment_frame_if_needed(page: Page) -> bool:
    """
    If payment iframe is visible, switch to it so subsequent actions target the frame.
    Caller can switch back with page.frame_parent if needed.
    """
    try:
        frames = page.frames
        for f in frames:
            if f != page.main_frame:
                url = f.url
                if "payment" in url.lower() or "pay" in url.lower() or "card" in url.lower():
                    logger.info("  Contextual router: payment iframe detected")
                    # Don't switch by default - caller can use frame for fill
                    return True
    except Exception as e:
        logger.debug(f"ensure_payment_frame: {e}")
    return False
