"""
Semantic element registry (Katalon/KaneAI-style).
Resolve app_key and page_pattern from URL; get ordered selectors for (app, page, intent);
save healed selectors with success stats.
"""
from __future__ import annotations

from typing import List, Optional, Tuple
from datetime import datetime
from urllib.parse import urlparse
from sqlalchemy.orm import Session

from models import UIElement


def _url_to_app_and_page(url: str) -> Tuple[str, str]:
    """Derive app_key and page_pattern from URL. Generic for any enterprise app."""
    if not url or not url.strip():
        return ("", "")
    try:
        parsed = urlparse(url.strip())
        host = (parsed.netloc or "").replace("www.", "").split(".")[0]  # lg, hilti, etc.
        path = (parsed.path or "/").strip("/").split("/")
        first_seg = path[0] if path and path[0] else ""
        page_pattern = host + ("/" + first_seg if first_seg else "")
        return (host or "default", page_pattern or host or "default")
    except Exception:
        return ("default", "default")


def get_registry_selectors(db: Session, url: str, intent: Optional[str]) -> List[str]:
    """
    Return ordered list of selectors for (app_key, page_pattern, intent).
    Selectors are sorted by success rate and last_success_at (best first).
    Used by Generator to prepend registry selectors before AKE and generic.
    """
    if not intent or not url:
        return []
    app_key, page_pattern = _url_to_app_and_page(url)
    row = db.query(UIElement).filter(
        UIElement.app_key == app_key,
        UIElement.page_pattern == page_pattern,
        UIElement.intent == intent,
    ).first()
    if not row or not row.selectors:
        return []
    # selectors: list of {selector, source, success_count, failure_count, last_success_at}
    items = [i for i in (row.selectors if isinstance(row.selectors, list) else []) if isinstance(i, dict) and i.get("selector")]
    if not items:
        return []
    # Sort by (success_count - failure_count) desc, then last_success_at desc
    def key(i: dict):
        s = i.get("success_count") or 0
        f = i.get("failure_count") or 0
        t = i.get("last_success_at") or ""
        return (s - f, t)

    ordered = sorted(items, key=key, reverse=True)
    return [str(x.get("selector", "")).strip() for x in ordered if x.get("selector")][:10]


def save_healed_selector(
    db: Session,
    url: str,
    intent: str,
    selector: str,
    element_name: Optional[str] = None,
) -> None:
    """
    When healer succeeds, add or update this selector in UIElement.
    If selector already exists, bump success_count and set last_success_at.
    Otherwise append with source='healer', success_count=1.
    """
    if not selector or not intent:
        return
    app_key, page_pattern = _url_to_app_and_page(url)
    now = datetime.utcnow().isoformat()
    row = db.query(UIElement).filter(
        UIElement.app_key == app_key,
        UIElement.page_pattern == page_pattern,
        UIElement.intent == intent,
    ).first()
    selectors = list(row.selectors) if row and isinstance(row.selectors, list) else []
    found = False
    for item in selectors:
        if isinstance(item, dict) and item.get("selector") == selector:
            item["success_count"] = (item.get("success_count") or 0) + 1
            item["last_success_at"] = now
            found = True
            break
    if not found:
        selectors.append({
            "selector": selector,
            "source": "healer",
            "success_count": 1,
            "failure_count": 0,
            "last_success_at": now,
        })
    if row:
        row.selectors = selectors
        row.updated_at = datetime.utcnow()
        if element_name:
            row.element_name = element_name
    else:
        db.add(UIElement(
            app_key=app_key,
            page_pattern=page_pattern,
            intent=intent,
            element_name=element_name,
            selectors=selectors,
        ))
    db.commit()
