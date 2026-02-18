"""
Site crawl runner — pre-crawl a site to build site_knowledge for whole-application coverage.

Uses the same resolution as the executor (smart_click, popup dismiss) so any test case
that touches these pages benefits. Run once (or periodically) to seed site_knowledge.json;
then all test runs use the cache for faster, more reliable clicks.

Usage:
  from services.ui_automation.core.site_crawl_runner import run_site_crawl
  await run_site_crawl(plan, headless=False)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from playwright.async_api import async_playwright, Page, BrowserContext

from .site_knowledge import site_knowledge
from .site_crawl_config import get_lg_india_crawl_plan

logger = logging.getLogger(__name__)

# Per-click timeout during crawl (avoid hanging on one label)
CRAWL_CLICK_TIMEOUT_SEC = 25
# Wait after each navigation/click for DOM to settle
CRAWL_WAIT_MS = 1500


async def _dismiss_popups(page: Page) -> None:
    """Dismiss cookie/quick menu so main nav is visible."""
    try:
        from .popup_classifier import classify_visible_popup, dismiss_popup_by_type, PopupType
        for _ in range(3):
            result = await classify_visible_popup(page)
            if result is None:
                break
            popup_type, modal_locator = result
            ok = await dismiss_popup_by_type(page, popup_type, modal_locator)
            if ok:
                await page.wait_for_timeout(500)
            else:
                break
    except Exception as e:
        logger.debug("Popup dismiss during crawl: %s", e)
    try:
        close_btn = page.locator("button.al-quick-menu__close, [aria-label='close' i]").first
        if await close_btn.count() > 0:
            await close_btn.click(timeout=2000)
            await page.wait_for_timeout(500)
    except Exception:
        pass


async def _click_label(page: Page, label: str) -> bool:
    """Try to click element by label (site_knowledge first, then smart_click). Returns True if clicked."""
    try:
        sel = await site_knowledge.try_click(page, label, timeout_ms=8000)
        if sel:
            return True
    except Exception as e:
        logger.debug("SiteKnowledge click %r: %s", label, e)
    try:
        from .element_resolver import smart_click
        await asyncio.wait_for(smart_click(page, label), timeout=CRAWL_CLICK_TIMEOUT_SEC)
        return True
    except asyncio.TimeoutError:
        logger.warning("Crawl: click %r timed out", label)
        return False
    except Exception as e:
        logger.warning("Crawl: click %r failed: %s", label, e)
        return False


async def _run_one_flow(
    page: Page,
    base_url: str,
    labels: List[str],
    flow_index: int,
) -> int:
    """Run a single flow (goto base, then click each label). Returns number of pages recorded."""
    recorded = 0
    try:
        await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(CRAWL_WAIT_MS)
        await _dismiss_popups(page)
        await page.wait_for_timeout(500)
        await site_knowledge.record_from_page(page, max_elements=400)
        recorded += 1
    except Exception as e:
        logger.warning("Crawl flow %s: goto failed: %s", flow_index, e)
        return 0

    for i, label in enumerate(labels):
        try:
            ok = await _click_label(page, label)
            if not ok:
                logger.info("Crawl flow %s step %s: skip %r", flow_index, i + 1, label)
                continue
            await page.wait_for_timeout(CRAWL_WAIT_MS)
            await _dismiss_popups(page)
            await page.wait_for_timeout(300)
            await site_knowledge.record_from_page(page, max_elements=400)
            recorded += 1
        except Exception as e:
            logger.warning("Crawl flow %s step %s (%r): %s", flow_index, i + 1, label, e)
    return recorded


async def _open_extra_urls(page: Page, urls: List[str]) -> int:
    """Open each URL and record. Returns number of pages recorded."""
    recorded = 0
    for url in urls:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(CRAWL_WAIT_MS)
            await _dismiss_popups(page)
            await page.wait_for_timeout(300)
            await site_knowledge.record_from_page(page, max_elements=400)
            recorded += 1
        except Exception as e:
            logger.warning("Crawl extra URL %s: %s", url, e)
    return recorded


async def run_site_crawl(
    plan: Optional[Dict[str, Any]] = None,
    headless: bool = False,
) -> Dict[str, Any]:
    """
    Run full site crawl from plan (flows + extra_urls), record every page into site_knowledge.

    plan: dict with base_url, flows (list of list of click labels), extra_urls (list of URLs).
          If None, uses get_lg_india_crawl_plan().
    headless: run browser headless or visible.

    Returns summary: { "pages_recorded": int, "flows_run": int, "errors": list }.
    """
    if plan is None:
        plan = get_lg_india_crawl_plan()
    base_url = plan.get("base_url") or "https://www.lg.com/in"
    flows = plan.get("flows") or []
    extra_urls = plan.get("extra_urls") or []

    total_pages = 0
    errors: List[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        try:
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
            page = await context.new_page()
            try:
                for idx, flow_labels in enumerate(flows):
                    try:
                        n = await _run_one_flow(page, base_url, flow_labels, idx)
                        total_pages += n
                    except Exception as e:
                        errors.append(f"flow_{idx}: {e}")
                if extra_urls:
                    total_pages += await _open_extra_urls(page, extra_urls)
            finally:
                await context.close()
        finally:
            await browser.close()

    # V3: Bootstrap Enterprise Locator Registry from crawl data (rich selectors → ELR)
    try:
        from .locator_registry import locator_registry
        bootstrap_count = locator_registry.bootstrap_from_site_knowledge(site_knowledge.get_pages_for_bootstrap())
        if bootstrap_count:
            logger.info("ELR bootstrap from crawl: %s entries added", bootstrap_count)
    except Exception as e:
        logger.debug("ELR bootstrap after crawl failed: %s", e)

    summary = {
        "pages_recorded": total_pages,
        "flows_run": len(flows),
        "extra_urls_count": len(extra_urls),
        "errors": errors,
    }
    logger.info("Site crawl complete: %s pages recorded, %s errors", total_pages, len(errors))
    return summary


def main() -> None:
    """CLI entrypoint: run LG India crawl and print summary."""
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    headless = "--headless" in sys.argv
    plan = get_lg_india_crawl_plan()
    summary = asyncio.run(run_site_crawl(plan, headless=headless))
    print("Crawl summary:", summary)


if __name__ == "__main__":
    main()
