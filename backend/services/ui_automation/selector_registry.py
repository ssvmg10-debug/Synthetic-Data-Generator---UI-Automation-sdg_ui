"""
Selector Registry Service – persistent store for host + intent → selectors with success/failure rates.
Production-grade: consult before execution; record heals; auto-promote after 3 consecutive successes.
Uses UIElement (app_key, intent, selectors JSON); fallback to LocatorRegistry for compatibility.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)

# Auto-promote when selector succeeds this many times (consecutive or total)
PROMOTE_AFTER_SUCCESS_COUNT = 3


def _host_to_app_key(host: str) -> str:
    """e.g. www.lg.com/in -> lg, lg.com -> lg."""
    if not host:
        return ""
    # Remove port and path, take first part of domain
    host = host.split("/")[0].split(":")[0].lower()
    for part in ["www.", ".com", ".in", ".co.", ".org"]:
        host = host.replace(part, " ")
    parts = [p for p in host.split() if len(p) > 1]
    return (parts[0] or host)[:32] if parts else host[:32]


class SelectorRegistryService:
    """
    Get primary selector for host+intent; record heals and failures.
    When db is None, all operations no-op (for tests or when DB unavailable).
    """

    def __init__(self, db: Optional[Any] = None):
        self._db = db

    def get_primary_selector(
        self,
        host: str,
        intent_name: str,
        page_pattern: Optional[str] = None,
    ) -> Optional[str]:
        """
        Look up best selector for host+intent. Returns primary (highest success_count) or None.
        """
        if not self._db or not host or not intent_name:
            return None
        try:
            from models import UIElement
            app_key = _host_to_app_key(host)
            pattern = page_pattern or host
            row = self._db.query(UIElement).filter(
                UIElement.app_key == app_key,
                UIElement.intent == intent_name,
            ).first()
            if not row or not row.selectors:
                return self._get_from_locator_registry(host, intent_name)
            selectors = row.selectors if isinstance(row.selectors, list) else []
            if not selectors:
                return None
            # Primary = first, or sort by success_count descending and take first
            best = max(
                (s for s in selectors if isinstance(s, dict) and s.get("selector")),
                key=lambda s: (s.get("success_count") or 0) - (s.get("failure_count") or 0) * 0.5,
                default=None,
            )
            return best.get("selector") if best else (selectors[0].get("selector") if isinstance(selectors[0], dict) else selectors[0])
        except Exception as e:
            logger.debug("SelectorRegistry get_primary_selector: %s", e)
            return self._get_from_locator_registry(host, intent_name)

    def _get_from_locator_registry(self, host: str, intent_name: str) -> Optional[str]:
        """Fallback: LocatorRegistry element = host::intent."""
        if not self._db:
            return None
        try:
            from models import LocatorRegistry
            key = f"{host}::{intent_name}"
            entry = self._db.query(LocatorRegistry).filter(LocatorRegistry.element == key).first()
            return entry.primary_locator if entry and entry.primary_locator else None
        except Exception:
            return None

    def record_heal(
        self,
        host: str,
        intent_name: str,
        selector: str,
        source: str = "healed",
        confidence: float = 0.8,
        page_pattern: Optional[str] = None,
    ) -> None:
        """
        Record a successful heal. Upserts UIElement; if same selector reaches
        PROMOTE_AFTER_SUCCESS_COUNT successes, it becomes primary.
        """
        if not self._db or not host or not intent_name or not selector:
            return
        try:
            from models import UIElement
            app_key = _host_to_app_key(host)
            pattern = page_pattern or host
            row = self._db.query(UIElement).filter(
                UIElement.app_key == app_key,
                UIElement.intent == intent_name,
            ).first()
            now_iso = datetime.utcnow().isoformat() + "Z"
            selectors = list(row.selectors) if row and row.selectors else []

            # Find or create entry for this selector
            found = False
            for s in selectors:
                if not isinstance(s, dict):
                    continue
                if (s.get("selector") or "").strip() == (selector or "").strip():
                    s["success_count"] = (s.get("success_count") or 0) + 1
                    s["last_success_at"] = now_iso
                    s["source"] = source
                    s["confidence"] = confidence
                    found = True
                    break
            if not found:
                selectors.append({
                    "selector": selector,
                    "source": source,
                    "success_count": 1,
                    "failure_count": 0,
                    "last_success_at": now_iso,
                    "confidence": confidence,
                })

            # Auto-promote: move selector with >= PROMOTE_AFTER_SUCCESS_COUNT to front
            for s in selectors:
                if isinstance(s, dict) and (s.get("success_count") or 0) >= PROMOTE_AFTER_SUCCESS_COUNT:
                    selectors.remove(s)
                    selectors.insert(0, s)
                    break

            if row:
                row.selectors = selectors
                row.updated_at = datetime.utcnow()
            else:
                self._db.add(UIElement(
                    app_key=app_key,
                    page_pattern=pattern[:256],
                    intent=intent_name,
                    selectors=selectors,
                ))
            self._db.commit()
            logger.info("SelectorRegistry record_heal: %s :: %s -> %s (source=%s)", app_key, intent_name, selector[:50], source)
        except Exception as e:
            logger.warning("SelectorRegistry record_heal failed: %s", e)
            if self._db:
                try:
                    self._db.rollback()
                except Exception:
                    pass

    def record_failure(self, host: str, intent_name: str, selector: str) -> None:
        """Increment failure_count for this selector so we can deprioritize it."""
        if not self._db or not host or not intent_name or not selector:
            return
        try:
            from models import UIElement
            app_key = _host_to_app_key(host)
            row = self._db.query(UIElement).filter(
                UIElement.app_key == app_key,
                UIElement.intent == intent_name,
            ).first()
            if not row or not row.selectors:
                return
            for s in row.selectors or []:
                if isinstance(s, dict) and (s.get("selector") or "").strip() == selector.strip():
                    s["failure_count"] = (s.get("failure_count") or 0) + 1
                    break
            row.updated_at = datetime.utcnow()
            self._db.commit()
        except Exception as e:
            logger.debug("SelectorRegistry record_failure: %s", e)
            if self._db:
                try:
                    self._db.rollback()
                except Exception:
                    pass
