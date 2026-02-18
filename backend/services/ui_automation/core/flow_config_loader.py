"""
Site Flow Config Loader - Layer 2 of the Flow Handler Architecture

Loads and runs site-specific flow handlers (e.g., LG) from JSON config.
Triggers: after_pincode_check, before_select_delivery, before_checkout, etc.
"""
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from playwright.async_api import Page

from .interrupt_handler import handle_interrupts

logger = logging.getLogger(__name__)

# Config cache
_configs: Dict[str, Dict] = {}
_CONFIG_DIR = Path(__file__).parent / "flow_config"


def _load_config(site_key: str) -> Optional[Dict]:
    """Load flow config for site (e.g., 'lg')"""
    if site_key in _configs:
        return _configs[site_key]
    path = _CONFIG_DIR / f"{site_key}_flow_config.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        # Strip BOM and trailing commas that break JSON
        raw = raw.strip().strip("\ufeff")
        _configs[site_key] = json.loads(raw)
        return _configs[site_key]
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in flow config {path}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Failed to load flow config {path}: {e}")
        return None


def _match_site(url: str) -> Optional[str]:
    """Determine site key from URL for flow config. Unknown sites return None (no handlers — agent still runs)."""
    url_lower = url.lower()
    if "lg.com" in url_lower:
        return "lg"
    # Add more sites as needed: "amazon." -> "amazon", etc.
    return None


async def run_flow_handlers(
    page: Page,
    trigger: str,
    url: Optional[str] = None,
) -> int:
    """
    Run flow handlers for the given trigger.
    
    Args:
        page: Playwright page
        trigger: e.g. 'after_pincode_check', 'before_select_delivery', 'before_checkout'
        url: Current page URL (if None, uses page.url())
    
    Returns:
        Number of actions executed
    """
    run_url = url or page.url
    site = _match_site(run_url)
    if not site:
        return 0
    
    config = _load_config(site)
    if not config or "handlers" not in config:
        return 0
    
    executed = 0
    for handler in config.get("handlers", []):
        if handler.get("trigger") != trigger:
            continue
        for action in handler.get("actions", []):
            try:
                atype = action.get("type")
                if atype == "dismiss_modal":
                    texts = action.get("button_texts", ["OK", "Continue"])
                    dismissed = False
                    for txt in texts:
                        if dismissed:
                            break
                        try:
                            for locator in [
                                page.get_by_role("button", name=txt),
                                page.get_by_role("button", name=txt, exact=False),
                                page.get_by_text(txt, exact=True),
                                page.get_by_text(txt, exact=False),
                            ]:
                                if await locator.count() > 0:
                                    first = locator.first
                                    if await first.is_visible():
                                        await first.click(timeout=1500)
                                        executed += 1
                                        dismissed = True
                                        logger.info(f"  📋 Flow config: dismissed '{txt}'")
                                        await page.wait_for_timeout(300)
                                        break
                        except Exception:
                            continue
                elif atype == "run_interrupt_handler":
                    n = await handle_interrupts(page, timeout_ms=2000)
                    executed += n
                elif atype == "wait":
                    ms = action.get("ms", 500)
                    await page.wait_for_timeout(ms)
            except Exception as e:
                logger.debug(f"Flow handler action failed: {e}")
    
    return executed
