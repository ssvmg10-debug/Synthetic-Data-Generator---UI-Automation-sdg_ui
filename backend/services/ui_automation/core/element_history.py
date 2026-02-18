"""
B3 — Element History (per step)

After successful step + validation, store fingerprint (attributes + selector + bbox + ancestor).
On next run, prefer candidate that matches last successful fingerprint; fall back to current scorer.
"""
import json
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

HISTORY_DIR = Path(__file__).resolve().parent
HISTORY_FILE = HISTORY_DIR / "element_history.json"


def _key(url: str, intent_type: str, normalized_target: str, env_id: Optional[str] = None) -> str:
    env = env_id or os.getenv("UI_AUTOMATION_ENV", "default")
    h = hashlib.md5(f"{env}::{url}::{intent_type}::{normalized_target}".encode()).hexdigest()
    return h[:20]


def _fingerprint_from_candidate(candidate: Any) -> Dict[str, Any]:
    """Build fingerprint dict from CandidateNode for matching."""
    return {
        "data_testid": getattr(candidate, "data_testid", "") or "",
        "aria_label": getattr(candidate, "aria_label", "") or "",
        "ancestor_path": getattr(candidate, "ancestor_path", "") or "",
        "ordinal_in_section": getattr(candidate, "ordinal_in_section", 0) or 0,
        "tag": getattr(candidate, "tag", "") or "",
        "role": getattr(candidate, "role", "") or "",
        "text_preview": (getattr(candidate, "text", None) or "")[:80] or "",
    }


def fingerprint_match_score(candidate_fp: Dict[str, Any], stored_fp: Dict[str, Any]) -> float:
    """Return 0-1 score: how well candidate matches stored fingerprint (2+ attributes = boost)."""
    if not stored_fp:
        return 0.0
    matches = 0
    total = 0
    for k in ("data_testid", "aria_label", "ancestor_path", "tag", "role"):
        s_val = stored_fp.get(k) or ""
        c_val = candidate_fp.get(k) or ""
        if s_val:
            total += 1
            if c_val and (s_val == c_val or (s_val in c_val or c_val in s_val)):
                matches += 1
    if stored_fp.get("ordinal_in_section") and candidate_fp.get("ordinal_in_section") == stored_fp.get("ordinal_in_section"):
        matches += 1
        total += 1
    if total == 0:
        return 0.0
    return matches / max(total, 1)


class ElementHistory:
    def __init__(self, filepath: Optional[Path] = None):
        self._path = filepath or HISTORY_FILE
        self._data: Dict[str, Any] = {"history": {}}
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                if "history" not in self._data:
                    self._data["history"] = {}
        except Exception as e:
            logger.debug(f"Element history load: {e}")

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            logger.debug(f"Element history save: {e}")

    def record(
        self,
        url: str,
        intent_type: str,
        normalized_target: str,
        fingerprint: Dict[str, Any],
        selector: Optional[str] = None,
        bounding_box: Optional[Dict[str, float]] = None,
        env_id: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> None:
        """Store fingerprint after successful step + validation. D1: append duration_ms for learned wait."""
        k = _key(url, intent_type, normalized_target, env_id)
        if "history" not in self._data:
            self._data["history"] = {}
        entry = self._data["history"].get(k) or {}
        entry.update({
            "fingerprint": fingerprint,
            "selector": selector,
            "bounding_box": bounding_box,
        })
        if duration_ms is not None:
            delays = entry.get("last_delays_ms") or []
            delays.append(duration_ms)
            entry["last_delays_ms"] = delays[-20:]
        self._data["history"][k] = entry
        self._save()
        logger.debug(f"  Element history: recorded for {intent_type} '{normalized_target[:40]}'")

    def get_learned_wait_ms(
        self,
        url: str,
        intent_type: str,
        normalized_target: str,
        env_id: Optional[str] = None,
        cap_ms: int = 5000,
    ) -> Optional[int]:
        """D1: Return p95 of last success delays (capped) for learned wait, or None."""
        k = _key(url, intent_type, normalized_target, env_id)
        entry = self._data.get("history", {}).get(k) or {}
        delays = entry.get("last_delays_ms") or []
        if len(delays) < 3:
            return None
        sorted_d = sorted(delays)
        idx = min(int(len(sorted_d) * 0.95), len(sorted_d) - 1)
        return min(cap_ms, sorted_d[idx])

    def get(
        self,
        url: str,
        intent_type: str,
        normalized_target: str,
        env_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve last successful fingerprint for this step (for scoring boost)."""
        k = _key(url, intent_type, normalized_target, env_id)
        return self._data.get("history", {}).get(k)
