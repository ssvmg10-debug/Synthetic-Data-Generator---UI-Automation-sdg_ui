"""
Module 10 — Execution Memory Layer

Store:
- Previous successful selector for this step (keyed by step context: url + target)
- Last successful state transition
- Stable path for LG flows

Over time: system becomes more deterministic.
"""
import json
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

MEMORY_DIR = Path(__file__).resolve().parent
MEMORY_FILE = MEMORY_DIR.parent.parent.parent.parent / "execution_memory.json"
if not MEMORY_FILE.exists():
    MEMORY_FILE = MEMORY_DIR / "execution_memory.json"


def _step_key(url: str, target: str, intent: str) -> str:
    h = hashlib.md5(f"{url}::{target}::{intent}".encode()).hexdigest()
    return h[:16]


def _normalize_target(target: str) -> str:
    return (target or "").strip().lower()[:200]


def _step_key_v2(
    url: str, intent_type: str, normalized_target: str, env_id: Optional[str] = None
) -> str:
    """Production cache key: (env_id, url, intent_type, normalized_target). Per-environment to avoid QA/prod cross-use."""
    env = env_id or os.getenv("UI_AUTOMATION_ENV", "default")
    h = hashlib.md5(f"{env}::{url}::{intent_type}::{normalized_target}".encode()).hexdigest()
    return "v2_" + h[:16]


class ExecutionMemory:
    def __init__(self, filepath: Optional[Path] = None):
        self._path = filepath or MEMORY_FILE
        self._cache: Dict[str, Any] = {"selectors": {}, "state_transitions": [], "stable_paths": []}
        self._load()

    def _load(self) -> None:
        try:
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
                if "selectors" not in self._cache:
                    self._cache["selectors"] = {}
                if "selectors_v2" not in self._cache:
                    self._cache["selectors_v2"] = {}
        except Exception as e:
            logger.debug(f"Execution memory load: {e}")

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            logger.debug(f"Execution memory save: {e}")

    def get_cached_selector(self, url: str, target: str, intent: str) -> Optional[str]:
        key = _step_key(url, target, intent)
        return self._cache.get("selectors", {}).get(key)

    def set_cached_selector(self, url: str, target: str, intent: str, selector: str) -> None:
        key = _step_key(url, target, intent)
        if "selectors" not in self._cache:
            self._cache["selectors"] = {}
        self._cache["selectors"][key] = selector
        self._save()
        logger.debug(f"  Execution memory: cached selector for '{target[:40]}'")

    def get_cached_selector_v2(
        self,
        url: str,
        intent_type: str,
        normalized_target: str,
        env_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Production: get cache by (env_id, url, intent_type, normalized_target). Per-environment (QA vs prod)."""
        key = _step_key_v2(url, intent_type, normalized_target, env_id)
        return self._cache.get("selectors_v2", {}).get(key)

    def set_cached_selector_v2(
        self,
        url: str,
        intent_type: str,
        normalized_target: str,
        selector: Optional[str] = None,
        dom_path: Optional[str] = None,
        bounding_box: Optional[Dict[str, float]] = None,
        container_info: Optional[Dict[str, Any]] = None,
        env_id: Optional[str] = None,
    ) -> None:
        """Production: cache only after validation success. Store selector, resolved DOM path, bbox, container. Per-environment."""
        key = _step_key_v2(url, intent_type, normalized_target, env_id)
        if "selectors_v2" not in self._cache:
            self._cache["selectors_v2"] = {}
        self._cache["selectors_v2"][key] = {
            "selector": selector,
            "dom_path": dom_path,
            "bounding_box": bounding_box,
            "container_info": container_info or {},
        }
        self._save()
        logger.debug(f"  Execution memory v2: cached for intent={intent_type} target='{normalized_target[:40]}'")

    def record_state_transition(self, from_state: str, to_state: str, step_id: int) -> None:
        rec = {"from": from_state, "to": to_state, "step_id": step_id}
        if "state_transitions" not in self._cache:
            self._cache["state_transitions"] = []
        self._cache["state_transitions"].append(rec)
        # Keep last 200
        self._cache["state_transitions"] = self._cache["state_transitions"][-200:]
        self._save()

    def get_last_transition_for_state(self, from_state: str) -> Optional[str]:
        trans = self._cache.get("state_transitions", [])
        for t in reversed(trans):
            if t.get("from") == from_state:
                return t.get("to")
        return None

    def record_stable_path(self, site: str, steps: List[str]) -> None:
        if "stable_paths" not in self._cache:
            self._cache["stable_paths"] = []
        entry = {"site": site, "steps": steps}
        # Dedupe by site (keep latest)
        self._cache["stable_paths"] = [
            p for p in self._cache["stable_paths"] if p.get("site") != site
        ] + [entry]
        self._cache["stable_paths"] = self._cache["stable_paths"][-20:]
        self._save()

    def get_stable_path(self, site: str) -> Optional[List[str]]:
        for p in reversed(self._cache.get("stable_paths", [])):
            if p.get("site") == site:
                return p.get("steps")
        return None
