#!/usr/bin/env python3
"""
Standalone E2E test for LG India: navigate, cookie, search, buy, pincode, checkout, guest, billing.
Run from project root:  python backend/run_lg_india_e2e.py
Or from backend:       python run_lg_india_e2e.py

Uses Playwright sync + app_config selectors + locator_hint. Headed by default so you can watch.
"""
import os
import sys
import re
from pathlib import Path

# Allow importing backend modules
_backend = Path(__file__).resolve().parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend.parent))
os.chdir(_backend)

from playwright.sync_api import sync_playwright

BASE_URL = "https://www.lg.com/in"
HEADED = os.environ.get("HEADED", "1") == "1"
TIMEOUT_MS = 30000
WAIT_AFTER = 2000


def try_locator_hint(page, step):
    """Execute step via get_by_role/get_by_placeholder. Returns True if done."""
    hint = step.get("locator_hint")
    if not isinstance(hint, dict) or not hint:
        return False
    action = step.get("action")
    value = (step.get("value") or "").strip()
    try:
        loc = None
        if hint.get("role"):
            name = hint.get("name")
            if name:
                loc = page.get_by_role(hint["role"], name=re.compile(re.escape(name), re.I))
            else:
                loc = page.get_by_role(hint["role"])
        elif hint.get("placeholder"):
            loc = page.get_by_placeholder(hint["placeholder"])
        elif hint.get("label"):
            loc = page.get_by_label(hint["label"])
        if not loc:
            return False
        loc.first.wait_for(state="visible", timeout=TIMEOUT_MS)
        if action == "click":
            loc.first.click(timeout=15000)
            page.wait_for_timeout(1500)
            return True
        if action in ("fill", "type"):
            loc.first.fill(value or "", timeout=15000)
            page.wait_for_timeout(500)
            return True
    except Exception as e:
        print(f"  [locator_hint] {e}")
        return False
    return False


def try_selectors(page, step):
    """Try selector + alternatives for click or fill. Returns True if done."""
    action = step.get("action")
    value = (step.get("value") or "").strip()
    sel = step.get("selector", "")
    alts = step.get("alternatives") or []
    for s in [sel] + [a for a in alts if a and a != sel]:
        if not s:
            continue
        try:
            page.wait_for_selector(s, state="visible", timeout=12000)
            if action == "click":
                page.click(s, timeout=15000)
                page.wait_for_timeout(1500)
                return True
            if action in ("fill", "type"):
                page.fill(s, value or "", timeout=15000)
                page.wait_for_timeout(500)
                return True
        except Exception as e:
            print(f"  [selector failed] {s[:50]}... -> {e}")
            continue
    return False


def run_step(page, step, step_num, screenshot_dir):
    """Run one step: locator_hint first, then selectors. Returns True if done or skipped (cookie)."""
    action = step.get("action")
    intent = step.get("intent", "")
    value = step.get("value", "")
    print(f"  Step {step_num}: {action} {f'({intent})' if intent else ''} {f'value={value[:30]}...' if value and len(value) > 30 else value or ''}")

    if action == "goto":
        page.goto(value or BASE_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(WAIT_AFTER)
        return True

    if action == "wait":
        page.wait_for_timeout(min(int(value or 2000), 5000))
        return True

    # Prefer locator_hint (Playwright role/placeholder)
    if step.get("locator_hint") and action in ("click", "fill", "type"):
        if try_locator_hint(page, step):
            print(f"    -> OK (locator_hint)")
            return True

    # Then try CSS selectors
    if try_selectors(page, step):
        print(f"    -> OK (selector)")
        return True

    # Cookie: skip if not found so we can continue
    if intent == "cookie_accept":
        print("    -> Skip (cookie not found)")
        return True

    return False


def main():
    # Import app_config after path is set
    from config.app_config import get_app_config_for_url, get_selectors_for_intent

    cfg = get_app_config_for_url(BASE_URL) or {}
    def sel(intent, default=None):
        return get_selectors_for_intent(cfg, intent) or (default or [])

    # Exact steps for: navigate, cookie, search icon, search fill, search submit, buy now, pincode, check, checkout, guest, billing
    steps = [
        {"action": "goto", "value": BASE_URL, "selector": "", "alternatives": []},
        {
            "action": "click",
            "intent": "cookie_accept",
            "selector": cfg.get("cookie_accept_selectors", ["button:has-text('Accept all')"])[0],
            "alternatives": cfg.get("cookie_accept_selectors", [])[1:10],
            "locator_hint": {"role": "button", "name": "Accept all"},
        },
        {
            "action": "click",
            "intent": "search_icon",
            "selector": (sel("search_icon", []) or ["a:has-text('Search')", "[aria-label*='Search']"])[0],
            "alternatives": (sel("search_icon", []) or ["button:has-text('Search')", "[aria-label*='Search']"])[1:8],
        },
        {
            "action": "fill",
            "intent": "search_box",
            "value": "lg 108cm tv",
            "selector": (sel("search_box", []) or ["input[type='search']", "input[placeholder*='Search']"])[0],
            "alternatives": (sel("search_box", []) or ["input[placeholder*='Search']", "input[name='q']"])[1:10],
            "locator_hint": {"role": "searchbox"},
        },
        {
            "action": "press",
            "intent": "search_submit",
            "value": "Enter",
            "selector": "input[type='search'], input[placeholder*='Search'], input[name='q']",
            "alternatives": [],
        },
        {"action": "wait", "value": "4000", "selector": "", "alternatives": []},
        {
            "action": "click",
            "intent": "add_to_cart",
            "selector": (sel("add_to_cart", []) or ["a:has-text('Buy Now')", "button:has-text('Buy Now')"])[0],
            "alternatives": (sel("add_to_cart", []) or [".cmp-button:has-text('Buy Now')"])[1:8],
            "locator_hint": {"role": "button", "name": "Buy Now"},
        },
        {"action": "wait", "value": "3000", "selector": "", "alternatives": []},
        {
            "action": "fill",
            "intent": "pincode_zip",
            "value": "500032",
            "selector": (sel("pincode_zip", []) or ["input[placeholder*='Pincode']", "input[name*='pincode']"])[0],
            "alternatives": (sel("pincode_zip", []))[1:8],
            "locator_hint": {"placeholder": "Pincode"},
        },
        {
            "action": "click",
            "intent": "pincode_check",
            "selector": (sel("pincode_check", []) or ["button:has-text('Check')"])[0],
            "alternatives": (sel("pincode_check", []))[1:5],
            "locator_hint": {"role": "button", "name": "Check"},
        },
        {"action": "wait", "value": "2000", "selector": "", "alternatives": []},
        {
            "action": "click",
            "intent": "checkout",
            "selector": (sel("checkout", []) or ["button:has-text('Checkout')", "a:has-text('Checkout')"])[0],
            "alternatives": (sel("checkout", []))[1:8],
            "locator_hint": {"role": "button", "name": "Checkout"},
        },
        {"action": "wait", "value": "2000", "selector": "", "alternatives": []},
        {
            "action": "click",
            "intent": "guest_checkout",
            "selector": (sel("guest_checkout", []) or ["button:has-text('Continue as guest')", "button:has-text('Continue')"])[0],
            "alternatives": (sel("guest_checkout", []))[1:8],
            "locator_hint": {"role": "button", "name": "Continue as guest"},
        },
        {"action": "wait", "value": "2000", "selector": "", "alternatives": []},
        {
            "action": "fill",
            "intent": "billing_shipping",
            "value": "Test User",
            "selector": (sel("billing_shipping", []) or ["input[name*='name']", "input[name*='address']"])[0],
            "alternatives": (sel("billing_shipping", []))[1:10],
            "locator_hint": {"placeholder": "Address"},
        },
    ]

    out_dir = _backend / "test_outputs" / "lg_india_e2e"
    out_dir.mkdir(parents=True, exist_ok=True)
    screenshot_dir = out_dir / "screenshots"
    screenshot_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("LG India E2E – Test case: search lg 108cm tv, buy, pincode, checkout, guest, billing")
    print("=" * 60)
    print(f"URL: {BASE_URL}  |  Headed: {HEADED}  |  Screenshots: {screenshot_dir}")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not HEADED)
        page = browser.new_page()
        try:
            for i, step in enumerate(steps, 1):
                if step.get("action") == "press":
                    print(f"  Step {i}: press Enter (search submit)")
                    try:
                        sel_val = step.get("selector", "input[type='search']")
                        page.wait_for_selector(sel_val, state="visible", timeout=12000)
                        page.press(sel_val, step.get("value") or "Enter")
                        page.wait_for_timeout(2000)
                        print("    -> OK")
                    except Exception as e:
                        print(f"    -> Failed: {e}")
                    continue
                ok = run_step(page, step, i, screenshot_dir)
                if not ok:
                    print(f"  Step {i} FAILED – stopping.")
                    try:
                        page.screenshot(path=str(screenshot_dir / f"step_{i}_failed.png"))
                    except Exception:
                        pass
                    break
            else:
                print()
                print("All steps completed. Check the browser for final state.")
        finally:
            browser.close()

    print()
    print("Done.")


if __name__ == "__main__":
    main()
