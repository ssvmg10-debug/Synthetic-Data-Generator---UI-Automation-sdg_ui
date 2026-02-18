"""
Enterprise Locator Registry (ELR) — V3 Core

Persistent locator storage with:
- Primary + fallback selectors (CSS, aria, xpath)
- DOM fingerprint for structural recovery
- Confidence scoring (success/failure counts)
- Per-site, per-page, per-target lookup

Replaces ad-hoc execution memory for locators; becomes the strongest deterministic layer.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)

# Confidence formula: base * stability_weight * recency_weight
# Demote when confidence < DEMOTE_THRESHOLD (move primary to fallback)
DEMOTE_THRESHOLD = 0.4
# Recency decay: after RECENCY_DAYS days without verification, confidence decays
RECENCY_DAYS_FULL = 7
RECENCY_DAYS_DECAY = 30

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
REGISTRY_FILE = ROOT_DIR / "backend" / "locator_registry.json"
if not REGISTRY_FILE.exists():
    REGISTRY_FILE = Path(__file__).resolve().parent.parent.parent.parent / "locator_registry.json"


def _normalize_url(url: str) -> str:
    if not url or not url.strip():
        return url or ""
    try:
        parsed = urlparse(url.strip())
        path = (parsed.path or "/").rstrip("/") or "/"
        return urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))
    except Exception:
        return url.strip()


def _extract_site(url: str) -> str:
    try:
        parsed = urlparse(url.strip())
        return (parsed.netloc or "").replace("www.", "").split(":")[0] or "unknown"
    except Exception:
        return "unknown"


def _elr_lookup_key(site: str, page_url: str, target: str, intent: str) -> str:
    """Canonical key: site|path|normalized_target|intent"""
    target_norm = (target or "").strip().lower()[:200]
    try:
        parsed = urlparse(page_url.strip())
        path = (parsed.path or "/").strip().rstrip("/") or "/"
    except Exception:
        path = "/"
    intent_upper = (intent or "CLICK").upper()
    return f"{site}|{path}|{target_norm}|{intent_upper}"


def get_elr_lookup_key(page_url: str, target: str, intent: str = "CLICK") -> str:
    """Public helper for plan adapter and executor to get canonical ELR key."""
    return _elr_lookup_key(_extract_site(page_url), _normalize_url(page_url), (target or "").strip().lower()[:200], intent)


class LocatorRegistry:
    """
    Enterprise Locator Registry — persistent selector store with confidence.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or REGISTRY_FILE
        self._entries: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._entries = data.get("entries", {}) if isinstance(data, dict) else {}
                if not isinstance(self._entries, dict):
                    self._entries = {}
        except Exception as e:
            logger.debug("LocatorRegistry load failed: %s", e)

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump({"entries": self._entries, "version": 1}, f, indent=2)
        except Exception as e:
            logger.debug("LocatorRegistry save failed: %s", e)

    def get(
        self,
        page_url: str,
        target: str,
        intent: str = "CLICK",
    ) -> Optional[Dict[str, Any]]:
        """
        Lookup entry for (page_url, target, intent).
        Tries: exact key, path prefix, site-level.
        """
        url = _normalize_url(page_url)
        site = _extract_site(url)
        target_norm = (target or "").strip().lower()[:200]
        if not target_norm:
            return None

        # Direct key
        key = _elr_lookup_key(site, url, target_norm, intent)
        entry = self._entries.get(key)
        if entry and self._confidence_ok(entry):
            return entry

        # Path prefix (e.g. /in matches /in/air-conditioners)
        for k, v in self._entries.items():
            if not self._confidence_ok(v):
                continue
            parts = k.split("|")
            if len(parts) < 4:
                continue
            s, path, t, i = parts[0], parts[1], parts[2], parts[3]
            if s != site or i != intent.upper():
                continue
            if t != target_norm:
                continue
            if path == "/" or url.startswith(path) or path in url:
                return v

        # Site-level fallback (path = /)
        fallback_key = f"{site}|/|{target_norm}|{intent.upper()}"
        return self._entries.get(fallback_key)

    def _confidence_ok(self, entry: Dict[str, Any]) -> bool:
        conf = entry.get("confidence_score", 0)
        return conf >= DEMOTE_THRESHOLD

    def _compute_confidence(self, entry: Dict[str, Any]) -> float:
        """
        Enterprise confidence: (success / (success + failure)) * stability_weight * recency_weight.
        stability_weight = 1 - (failure_rate); recency_weight = decay by last_verified age.
        """
        s = entry.get("success_count", 0)
        f = entry.get("failure_count", 0)
        total = s + f
        if total == 0:
            return 0.7
        base = s / total
        # Stability: penalize high failure rate
        failure_rate = f / total
        stability_weight = 1.0 - (failure_rate * 0.5)  # 0.5–1.0
        # Recency: decay if not verified recently
        last = entry.get("last_verified") or ""
        recency_weight = 1.0
        try:
            if last:
                dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age_days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
                if age_days > RECENCY_DAYS_DECAY:
                    recency_weight = 0.7
                elif age_days > RECENCY_DAYS_FULL:
                    recency_weight = 0.9
        except Exception:
            pass
        return round(min(0.98, base * stability_weight * recency_weight), 2)

    def get_primary_selector(self, entry: Dict[str, Any]) -> Optional[str]:
        """Return Playwright-usable selector string from primary."""
        p = entry.get("primary_selector") or {}
        t = (p.get("type") or "").lower()
        v = p.get("value")
        if not v:
            return None
        if t == "css":
            return v
        if t == "aria":
            # role=link[name='Air Solutions'] -> get_by_role equivalent; we return as locator string
            m = re.match(r"role=(\w+)\[name=['\"]?(.+?)['\"]?\]", v, re.I)
            if m:
                return f"role={m.group(1)}[name='{m.group(2)}']"
            return v
        if t == "xpath":
            return v
        return v

    def get_fallback_selectors(self, entry: Dict[str, Any]) -> List[str]:
        """Return list of Playwright-usable selector strings."""
        fallbacks = entry.get("fallback_selectors") or []
        out = []
        for f in fallbacks:
            if not isinstance(f, dict):
                continue
            t = (f.get("type") or "css").lower()
            v = f.get("value")
            if v:
                out.append(v)
        return out

    def get_all_selectors_ordered(self, entry: Dict[str, Any]) -> List[str]:
        """Return [primary, ...fallbacks] as Playwright-usable selector strings for phased try."""
        out: List[str] = []
        primary = self.get_primary_selector(entry)
        if primary:
            out.append(primary)
        for s in self.get_fallback_selectors(entry):
            if s and s not in out:
                out.append(s)
        return out

    def add_or_update(
        self,
        page_url: str,
        target: str,
        intent: str,
        selector: str,
        selector_type: str = "css",
        dom_fingerprint: Optional[Dict[str, Any]] = None,
        success: bool = True,
    ) -> None:
        """Add or update entry; adjust confidence based on success."""
        url = _normalize_url(page_url)
        site = _extract_site(url)
        target_norm = (target or "").strip().lower()[:200]
        key = _elr_lookup_key(site, url, target_norm, intent)

        entry = self._entries.get(key) or {
            "site": site,
            "page_url": url,
            "normalized_target": target_norm,
            "intent": intent.upper(),
            "primary_selector": {"type": selector_type, "value": selector},
            "fallback_selectors": [],
            "dom_fingerprint": dom_fingerprint or {},
            "confidence_score": 0.7,
            "success_count": 0,
            "failure_count": 0,
            "last_verified": datetime.utcnow().isoformat() + "Z",
        }

        if success:
            entry["success_count"] = entry.get("success_count", 0) + 1
        else:
            entry["failure_count"] = entry.get("failure_count", 0) + 1

        entry["last_verified"] = datetime.utcnow().isoformat() + "Z"
        entry["confidence_score"] = self._compute_confidence(entry)
        if dom_fingerprint:
            entry["dom_fingerprint"] = dom_fingerprint

        self._entries[key] = entry
        self._save()
        logger.debug("  ELR: updated %s (conf=%.2f)", key[:60], entry["confidence_score"])

    def add_fallback(
        self,
        page_url: str,
        target: str,
        intent: str,
        selector: str,
        selector_type: str = "css",
    ) -> None:
        """Add a fallback selector to existing entry."""
        entry = self.get(page_url, target, intent)
        if not entry:
            return
        key = _elr_lookup_key(_extract_site(page_url), _normalize_url(page_url), (target or "").strip().lower()[:200], intent)
        fallbacks = entry.get("fallback_selectors") or []
        for fb in fallbacks:
            if isinstance(fb, dict) and fb.get("value") == selector:
                return
        fallbacks.append({"type": selector_type, "value": selector})
        entry["fallback_selectors"] = fallbacks[:5]
        self._entries[key] = entry
        self._save()

    def demote(self, page_url: str, target: str, intent: str) -> None:
        """Demote primary (e.g. after failure); next fallback becomes primary."""
        key = _elr_lookup_key(
            _extract_site(page_url),
            _normalize_url(page_url),
            (target or "").strip().lower()[:200],
            intent,
        )
        entry = self._entries.get(key)
        if not entry or not entry.get("fallback_selectors"):
            return
        fallbacks = entry["fallback_selectors"]
        old_primary = entry.get("primary_selector", {})
        if old_primary:
            fallbacks = [old_primary] + [f for f in fallbacks if isinstance(f, dict) and f.get("value") != old_primary.get("value")]
        new_primary = fallbacks.pop(0) if fallbacks else None
        if new_primary and isinstance(new_primary, dict):
            entry["primary_selector"] = new_primary
            entry["fallback_selectors"] = fallbacks[:4]
            entry["failure_count"] = entry.get("failure_count", 0) + 1
            entry["confidence_score"] = max(0.3, entry.get("confidence_score", 0.5) - 0.1)
            self._entries[key] = entry
            self._save()

    def record_success(self, page_url: str, target: str, intent: str) -> None:
        """Record a successful use of the current primary selector; bump confidence."""
        entry = self.get(page_url, target, intent)
        if not entry:
            return
        key = _elr_lookup_key(
            _extract_site(page_url), _normalize_url(page_url), (target or "").strip().lower()[:200], intent
        )
        entry["success_count"] = entry.get("success_count", 0) + 1
        entry["last_verified"] = datetime.utcnow().isoformat() + "Z"
        entry["confidence_score"] = self._compute_confidence(entry)
        self._entries[key] = entry
        self._save()

    def record_failure(self, page_url: str, target: str, intent: str) -> None:
        """Record a failure; may demote primary to fallback when confidence drops below threshold."""
        key = _elr_lookup_key(
            _extract_site(page_url), _normalize_url(page_url), (target or "").strip().lower()[:200], intent
        )
        entry = self._entries.get(key)
        if not entry:
            return
        entry["failure_count"] = entry.get("failure_count", 0) + 1
        entry["last_verified"] = datetime.utcnow().isoformat() + "Z"
        entry["confidence_score"] = self._compute_confidence(entry)
        if entry["confidence_score"] < DEMOTE_THRESHOLD and entry.get("fallback_selectors"):
            # Demote: move primary to fallbacks, promote first fallback
            fallbacks = list(entry.get("fallback_selectors") or [])
            old_primary = entry.get("primary_selector")
            if old_primary and isinstance(old_primary, dict):
                fallbacks = [old_primary] + [f for f in fallbacks if isinstance(f, dict) and f.get("value") != old_primary.get("value")]
            if fallbacks:
                entry["primary_selector"] = fallbacks.pop(0)
                entry["fallback_selectors"] = fallbacks[:4]
        self._entries[key] = entry
        self._save()

    def prune_low_confidence(self, min_confidence: float = DEMOTE_THRESHOLD) -> int:
        """Remove entries with confidence below min_confidence. Returns count removed."""
        to_remove = [k for k, v in self._entries.items() if (v.get("confidence_score") or 0) < min_confidence]
        for k in to_remove:
            del self._entries[k]
        if to_remove:
            self._save()
        return len(to_remove)

    def bootstrap_from_site_knowledge(self, site_knowledge_data: Dict[str, Any]) -> int:
        """
        Bootstrap ELR from site_knowledge (crawl) data. Uses rich selectors (css, role, aria_label)
        when present; builds dom_fingerprint from parent_chain for structural recovery.
        """
        added = 0
        pages = site_knowledge_data.get("pages", {}) if isinstance(site_knowledge_data, dict) else {}
        for page_url, labels in pages.items():
            if not isinstance(labels, dict):
                continue
            for label, info in labels.items():
                if not isinstance(info, dict):
                    continue
                href = info.get("href")
                text = info.get("text", label)
                tag = (info.get("tag") or "a").lower()
                key = _elr_lookup_key(_extract_site(page_url), page_url, label, "CLICK")
                if key in self._entries:
                    continue
                primary = None
                fallbacks: List[Dict[str, Any]] = []
                # V3: prefer crawl-extracted css, then data_testid, then href, then role/aria
                css = (info.get("css") or "").strip()
                if css and len(css) < 500:
                    primary = {"type": "css", "value": css}
                if not primary and info.get("data_testid"):
                    primary = {"type": "css", "value": f"[data-testid=\"{(info.get('data_testid') or '').replace(chr(34), '')}\"]"}
                if not primary and href and str(href).strip() and not str(href).startswith("#"):
                    primary = {"type": "css", "value": f"a[href=\"{str(href).strip().replace(chr(34), '')}\"]"}
                if not primary and tag == "a":
                    primary = {"type": "aria", "value": f"role=link[name='{text}']"}
                else:
                    primary = primary or {"type": "aria", "value": f"role=button[name='{text}']"}
                # Fallbacks: aria by text, href if not primary
                if tag == "a":
                    fallbacks = [{"type": "aria", "value": f"role=link[name='{text}']"}]
                else:
                    fallbacks = [{"type": "aria", "value": f"role=button[name='{text}']"}]
                if href and str(href).strip() and not str(href).startswith("#") and (not primary or primary.get("value") != f"a[href=\"{href.strip()}\"]"):
                    fallbacks.append({"type": "css", "value": f"a[href=\"{str(href).strip().replace(chr(34), '')}\"]"})
                fp = {}
                if info.get("parent_chain"):
                    fp["parent_chain"] = info["parent_chain"]
                if tag:
                    fp["tag"] = tag
                if info.get("aria_label"):
                    fp["aria_label"] = info["aria_label"][:100]
                if info.get("data_testid"):
                    fp["data_testid"] = info["data_testid"][:100]
                self._entries[key] = {
                    "site": _extract_site(page_url),
                    "page_url": page_url,
                    "normalized_target": label,
                    "intent": "CLICK",
                    "primary_selector": primary,
                    "fallback_selectors": fallbacks[:5],
                    "dom_fingerprint": fp,
                    "confidence_score": 0.75,
                    "success_count": 0,
                    "failure_count": 0,
                    "last_verified": datetime.utcnow().isoformat() + "Z",
                }
                added += 1
        if added:
            self._save()
        return added


# Singleton for executor use
locator_registry = LocatorRegistry()
