#!/usr/bin/env python3
"""
Run full LG India site crawl to build site_knowledge.json for whole-application coverage.

This crawls as much as possible from https://www.lg.com/in (main nav, sub-categories,
key listing pages) and records every page into site_knowledge. After running once,
any test case (search, category, product, checkout, support, etc.) can benefit from
the cached selectors for faster and more reliable execution.

Usage:
  From repo root:
    python -m backend.run_lg_site_crawl
    python -m backend.run_lg_site_crawl --headless
    python -m backend.run_lg_site_crawl --validate   # crawl then run a short E2E test
  From backend/:
    python run_lg_site_crawl.py
    python run_lg_site_crawl.py --headless
    python run_lg_site_crawl.py --validate

Output:
  - site_knowledge.json (in backend/ or project root) is updated.
  - Console summary: pages_recorded, flows_run, any errors.
  - With --validate: runs a short test (navigate, click Home Appliances, click All Water Purifiers).
"""

import asyncio
import logging
import sys
from pathlib import Path

# Ensure backend is on path so "services.ui_automation" resolves
_backend = Path(__file__).resolve().parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from services.ui_automation.core.site_crawl_runner import run_site_crawl
from services.ui_automation.core.site_crawl_config import get_lg_india_crawl_plan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def _run_validation_test(headless: bool) -> bool:
    """Run a short E2E test to validate site_knowledge works. Returns True if test passed."""
    from playwright.async_api import async_playwright
    from services.ui_automation.core.enhanced_deterministic_executor import DeterministicExecutorV2
    from services.ui_automation.core.test_model import ExecutionResult

    test = (
        "navigate to this application https://www.lg.com/in\n"
        "click on Home Appliances and click on All Water Purifiers"
    )
    logger.info("Validation test: navigate -> Home Appliances -> All Water Purifiers")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        try:
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            )
            page = await context.new_page()
            executor = DeterministicExecutorV2(page, context)
            result: ExecutionResult = await executor.execute_natural_language(test)
            ok = result.passed and result.executed_steps >= 2
            if ok:
                logger.info("Validation PASSED: %s/%s steps", result.executed_steps, result.total_steps)
            else:
                logger.warning("Validation incomplete: %s/%s steps, error=%s",
                               result.executed_steps, result.total_steps, result.error)
            return ok
        finally:
            await browser.close()


def main() -> None:
    headless = "--headless" in sys.argv
    do_validate = "--validate" in sys.argv
    plan = get_lg_india_crawl_plan()
    logger.info("Starting LG India site crawl (base_url=%s, flows=%s, extra_urls=%s)",
                plan["base_url"], len(plan["flows"]), len(plan.get("extra_urls", [])))
    summary = asyncio.run(run_site_crawl(plan, headless=headless))
    logger.info("Crawl complete: pages_recorded=%s, flows_run=%s, errors=%s",
                summary["pages_recorded"], summary["flows_run"], len(summary["errors"]))
    if summary["errors"]:
        for e in summary["errors"][:10]:
            logger.warning("  %s", e)
        if len(summary["errors"]) > 10:
            logger.warning("  ... and %s more", len(summary["errors"]) - 10)
    if do_validate:
        logger.info("Running validation test...")
        asyncio.run(_run_validation_test(headless=headless))
    print("Done.", summary)


if __name__ == "__main__":
    main()
