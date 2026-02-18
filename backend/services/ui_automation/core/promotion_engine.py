"""
Self-Learning Promotion Engine — V3 Enterprise

After any successful click:
- resolved_selector → compare with registry
- If better (e.g. more stable or new) → promote to primary or add as fallback
- If failure on primary → demote (handled in LocatorRegistry.record_failure)

Enables: "A deterministic engine that learns and occasionally asks AI for help."
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def promote_on_success(
    page_url: str,
    target: str,
    intent: str,
    resolved_selector: str,
    selector_type: str = "css",
    dom_fingerprint: Optional[Dict[str, Any]] = None,
    source: str = "resolution",
) -> None:
    """
    Call after a successful click. If the selector that worked is not already the ELR primary,
    add or update ELR: promote to primary if we don't have one or this one is better;
    otherwise add as fallback.
    """
    try:
        from .locator_registry import locator_registry

        entry = locator_registry.get(page_url, target, intent)
        primary_sel = locator_registry.get_primary_selector(entry) if entry else None

        # Normalize for comparison (strip whitespace)
        resolved = (resolved_selector or "").strip()
        if not resolved:
            return

        # Already primary — just record success to bump confidence
        if primary_sel and primary_sel.strip() == resolved:
            locator_registry.record_success(page_url, target, intent)
            logger.debug("  Promotion: primary already matched, recorded success")
            return

        # New or different selector: add_or_update so it becomes primary (or add as fallback if entry exists with same primary)
        if entry and primary_sel and primary_sel != resolved:
            # Add as fallback so next time we have it as backup
            locator_registry.add_fallback(page_url, target, intent, resolved, selector_type)
            locator_registry.record_success(page_url, target, intent)
            logger.info("  Promotion: added as fallback selector for %r (primary unchanged)", target[:40])
        else:
            # No entry or no primary: set as primary
            locator_registry.add_or_update(
                page_url,
                target,
                intent,
                resolved,
                selector_type=selector_type,
                dom_fingerprint=dom_fingerprint,
                success=True,
            )
            logger.info("  Promotion: registered primary selector for %r", target[:40])
    except Exception as e:
        logger.debug("Promotion engine error: %s", e)


def demote_on_failure(page_url: str, target: str, intent: str) -> None:
    """
    Call when ELR primary (or an ELR selector) was tried and failed.
    Records failure; LocatorRegistry may demote primary to fallback when confidence drops.
    """
    try:
        from .locator_registry import locator_registry

        locator_registry.record_failure(page_url, target, intent)
        logger.debug("  Demotion: recorded failure for %r", target[:40])
    except Exception as e:
        logger.debug("Demotion engine error: %s", e)
