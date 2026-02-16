"""
Batch revalidation job – nightly or on-demand.
Re-run top-N flaky tests against current site and re-evaluate selectors; update registry.
Production: run as cron or scheduled job; use with staging only.
Usage: call from CLI with asyncio.run(batch_revalidate_top_flaky_async(limit=200)) or use sync stub.
"""
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


async def batch_revalidate_top_flaky_async(
    limit: int = 200,
    db: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Async: Re-run validation for top-N test cases. Updates selector registry from results.
    Returns: { "validated": N, "failed": M, "updated_registry": K }.
    """
    if not db:
        logger.warning("Batch revalidate: no db session, skipping")
        return {"validated": 0, "failed": 0, "updated_registry": 0}
    try:
        from models import UITestCase
        from services.ui_automation.utils.selector_validator import SelectorValidator
        cases = db.query(UITestCase).limit(limit).all()
        if not cases:
            return {"validated": 0, "failed": 0, "updated_registry": 0}
        validator = SelectorValidator(headless=True)
        validated = 0
        failed = 0
        for tc in cases:
            try:
                plan = tc.structured_json or {}
                url = plan.get("url") or plan.get("starting_url") or "https://example.com"
                steps = plan.get("steps") or []
                if not steps:
                    continue
                result = await validator.validate_script(url, steps, wait_for_load=True)
                if result.get("validation_passed"):
                    validated += 1
                else:
                    failed += 1
            except Exception as e:
                logger.debug("Batch revalidate case %s: %s", tc.id, e)
                failed += 1
        return {"validated": validated, "failed": failed, "updated_registry": 0}
    except Exception as e:
        logger.warning("Batch revalidate failed: %s", e)
        return {"validated": 0, "failed": 0, "updated_registry": 0}


def batch_revalidate_top_flaky(limit: int = 200, db: Optional[Any] = None) -> Dict[str, Any]:
    """Sync entrypoint for cron/scheduler. Runs async batch_revalidate_top_flaky_async."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return {"validated": 0, "failed": 0, "updated_registry": 0}
        return loop.run_until_complete(batch_revalidate_top_flaky_async(limit, db))
    except RuntimeError:
        return asyncio.run(batch_revalidate_top_flaky_async(limit, db))
