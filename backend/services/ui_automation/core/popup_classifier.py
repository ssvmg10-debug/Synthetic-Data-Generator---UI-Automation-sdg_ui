"""
Module 5 — Intelligent Popup Reasoning (Popup Classifier)

Instead of keyword matching only, classify popup by content:
- Contains email field → login modal
- Contains pincode → delivery modal
- Contains "agree" / "accept" → consent modal
- Contains QR / payment → payment modal

Then route resolution accordingly (which button to click, or which flow handler).
"""
import logging
from enum import Enum
from typing import Optional, Tuple, List
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class PopupType(str, Enum):
    LOGIN = "login"
    DELIVERY = "delivery"
    CONSENT = "consent"
    PAYMENT = "payment"
    GENERIC = "generic"


# Dismiss button texts per type (preferred order)
DISMISS_BY_TYPE = {
    PopupType.LOGIN: ["continue as guest", "guest checkout", "checkout as guest", "proceed without account", "skip", "close"],
    PopupType.DELIVERY: ["ok", "continue", "select delivery", "select delivery option", "close"],
    PopupType.CONSENT: ["agree", "accept", "accept all", "ok", "got it", "allow"],
    PopupType.PAYMENT: ["close", "cancel", "back", "continue"],
    PopupType.GENERIC: ["ok", "continue", "close", "dismiss", "got it", "agree", "accept"],
}


async def _modal_content_summary(page: Page, modal_locator) -> str:
    """Get inner text of modal (first 500 chars) for classification."""
    try:
        text = (await modal_locator.inner_text(timeout=500)).strip().lower()
        return text[:500]
    except Exception:
        return ""


def _classify_by_content(content: str) -> PopupType:
    """Classify popup type from text content."""
    if not content:
        return PopupType.GENERIC
    # Login: email field or sign-in wording
    if "email" in content or "sign in" in content or "log in" in content or "password" in content:
        if "pincode" not in content and "delivery" not in content:
            return PopupType.LOGIN
    # Delivery: pincode, delivery, shipping
    if "pincode" in content or "pin code" in content or "zip" in content:
        return PopupType.DELIVERY
    if "delivery" in content and ("option" in content or "select" in content or "choose" in content):
        return PopupType.DELIVERY
    if "shipping" in content and ("option" in content or "method" in content):
        return PopupType.DELIVERY
    # Consent / cookie
    if "agree" in content or "accept" in content or "cookie" in content or "consent" in content or "privacy" in content:
        return PopupType.CONSENT
    # Payment (QR, card, etc.)
    if "qr" in content or "payment" in content or "pay" in content or "card" in content:
        return PopupType.PAYMENT
    return PopupType.GENERIC


async def classify_visible_popup(page: Page) -> Optional[Tuple[PopupType, any]]:
    """
    Detect if there is a visible modal and classify its type.
    Returns (PopupType, modal_locator) or None if no modal found.
    """
    modal_selectors = [
        "[role='dialog']",
        "[role='alertdialog']",
        "dialog",
        ".modal",
        "[class*='modal']",
        "[class*='Modal']",
        "[class*='popup']",
        "[class*='overlay']",
        "[class*='dialog']",
    ]
    for sel in modal_selectors:
        try:
            modals = page.locator(sel)
            n = await modals.count()
            for i in range(n):
                modal = modals.nth(i)
                if not await modal.is_visible():
                    continue
                content = await _modal_content_summary(page, modal)
                popup_type = _classify_by_content(content)
                logger.info(f"  Popup classified: {popup_type.value} (selector: {sel})")
                return (popup_type, modal)
        except Exception as e:
            logger.debug(f"Classifier {sel}: {e}")
            continue
    return None


async def dismiss_popup_by_type(
    page: Page,
    popup_type: PopupType,
    modal_locator=None,
    prefer_guest: bool = False,
) -> bool:
    """
    Dismiss popup using type-appropriate buttons.
    If prefer_guest and type is LOGIN, prefer "Continue as guest" etc.
    """
    buttons_to_try = DISMISS_BY_TYPE.get(popup_type, DISMISS_BY_TYPE[PopupType.GENERIC])
    if popup_type == PopupType.LOGIN and prefer_guest:
        buttons_to_try = DISMISS_BY_TYPE[PopupType.LOGIN]

    scope = modal_locator if modal_locator is not None else page
    try:
        buttons = scope.locator("button, a, [role='button'], input[type='submit']")
        n = await buttons.count()
        for txt in buttons_to_try:
            for i in range(min(n, 8)):
                btn = buttons.nth(i)
                try:
                    bt = (await btn.inner_text(timeout=300)).strip().lower()
                    if not bt or len(bt) > 50:
                        continue
                    if txt in bt or (len(txt) > 3 and txt in bt):
                        await btn.click(timeout=1000)
                        logger.info(f"  Dismissed popup ({popup_type.value}): '{bt[:40]}'")
                        await page.wait_for_timeout(400)
                        return True
                except Exception:
                    continue
    except Exception as e:
        logger.debug(f"dismiss_popup_by_type: {e}")
    return False


async def handle_interrupts_classified(
    page: Page,
    timeout_ms: int = 2500,
    current_step_guest_checkout: bool = False,
) -> int:
    """
    Classify visible popup and dismiss with appropriate button list.
    Returns number of popups dismissed.
    """
    dismissed = 0
    deadline = (timeout_ms / 1000.0) if timeout_ms else 2.5
    import time
    start = time.monotonic()
    while (time.monotonic() - start) < deadline:
        result = await classify_visible_popup(page)
        if result is None:
            break
        popup_type, modal_locator = result
        prefer_guest = current_step_guest_checkout and popup_type == PopupType.LOGIN
        ok = await dismiss_popup_by_type(page, popup_type, modal_locator, prefer_guest=prefer_guest)
        if ok:
            dismissed += 1
            await page.wait_for_timeout(400)
        else:
            # Fallback to generic dismiss
            ok = await dismiss_popup_by_type(page, PopupType.GENERIC, modal_locator)
            if ok:
                dismissed += 1
            break
    return dismissed
