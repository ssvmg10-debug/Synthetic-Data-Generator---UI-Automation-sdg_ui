"""
Goal Extractor – converts raw test case or structured plan → GoalObject.

Input: "Navigate to LG, search for lg 108cm tv, buy product under 30000, complete purchase as guest, fill address"
Output: GoalObject(search_query="lg 108cm tv", price_max=30000, checkout_mode="guest", complete_purchase=True)

No steps. No selectors. No intents. Just final objective.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class GoalObject:
    """
    Structured goal – what the test must achieve, not how.
    Used by the decision engine for goal matching.
    """
    # Search
    search_query: Optional[str] = None
    
    # Product selection
    price_max: Optional[int] = None
    price_min: Optional[int] = None
    product_keywords: List[str] = field(default_factory=list)
    
    # Checkout
    checkout_mode: str = "guest"  # guest | login | either
    complete_purchase: bool = True
    fill_address: bool = True
    
    # Delivery
    pincode: Optional[str] = None
    
    # URL
    start_url: Optional[str] = None
    
    # Optional test-specific hints (for extensibility)
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def has_search_goal(self) -> bool:
        return bool(self.search_query and self.search_query.strip())
    
    def has_price_constraint(self) -> bool:
        return self.price_max is not None or self.price_min is not None
    
    def wants_guest_checkout(self) -> bool:
        return self.checkout_mode.lower() in ("guest", "either", "")
    
    def wants_address_filled(self) -> bool:
        return self.fill_address
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "search_query": self.search_query,
            "price_max": self.price_max,
            "price_min": self.price_min,
            "checkout_mode": self.checkout_mode,
            "complete_purchase": self.complete_purchase,
            "fill_address": self.fill_address,
            "pincode": self.pincode,
            "start_url": self.start_url,
        }


def _parse_price_from_text(text: str) -> Optional[int]:
    """Extract price from text like 'under 30000', 'below 30k', '₹25000'."""
    text = (text or "").lower()
    # under 30000, below 30k, less than 25000
    m = re.search(r"(?:under|below|less than|<)\s*[^\d]*(?:₹|rs\.?|inr)?\s*([0-9,]+)\s*(k|000)?", text)
    if m:
        raw = m.group(1).replace(",", "")
        try:
            n = int(raw)
            if m.lastindex >= 2 and m.group(2):
                n = n * 1000
            return n
        except ValueError:
            pass
    m = re.search(r"[₹$]?\s*([0-9,]+)\s*(?:k|000)\b", text)
    if m:
        try:
            n = int(m.group(1).replace(",", ""))
            return n * 1000
        except ValueError:
            pass
    m = re.search(r"\b(\d{4,6})\b", text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return None


def _parse_search_query(steps: List[Dict[str, Any]], raw_input: str) -> Optional[str]:
    """Extract search query from plan steps or raw text."""
    for s in steps or []:
        if s.get("intent") in ("search_box", "search_submit") and s.get("value"):
            return str(s["value"]).strip()
        if s.get("action") in ("type", "fill") and "search" in str(s.get("element", "")).lower():
            if s.get("value"):
                return str(s["value"]).strip()
    # Fallback: regex on raw input (stop at comma/period to avoid capturing "buy under 30000")
    if raw_input:
        m = re.search(r"search\s+for\s+([^,.\n]+)", raw_input, re.I)
        if m:
            return m.group(1).strip()[:80]
    return None


def _parse_pincode(steps: List[Dict[str, Any]], raw_input: str) -> Optional[str]:
    """Extract pincode from plan steps or raw text."""
    for s in steps or []:
        if s.get("intent") == "pincode_zip" and s.get("value"):
            return str(s["value"]).strip()
    if raw_input:
        m = re.search(r"\b(\d{6})\b", raw_input)
        if m:
            return m.group(1)
    return "500032"  # Default India pincode


def _parse_url(steps: List[Dict[str, Any]], raw_input: str, fallback: Optional[str] = None) -> Optional[str]:
    """Extract start URL from plan or raw input."""
    for s in steps or []:
        if s.get("action") == "goto" or s.get("action") == "navigate":
            url = s.get("value") or s.get("url")
            if url and url.startswith("http"):
                return url
    if raw_input:
        m = re.search(r"https?://[^\s'\"]+", raw_input)
        if m:
            return m.group(0)
    return fallback


def extract_goal(
    plan: Optional[Dict[str, Any]] = None,
    raw_input: Optional[str] = None,
    url: Optional[str] = None,
) -> GoalObject:
    """
    Convert test case (plan or raw text) into structured GoalObject.
    
    Args:
        plan: Structured plan with steps (from planner)
        raw_input: Raw user test case text
        url: Fallback URL if not in plan
    
    Returns:
        GoalObject with extracted fields
    """
    steps = (plan or {}).get("steps", [])
    raw = raw_input or ""
    
    # Search query
    search_query = _parse_search_query(steps, raw)
    
    # Price constraint
    price_max = None
    for s in steps or []:
        cond = s.get("condition") or {}
        if cond.get("price_max") is not None:
            price_max = int(cond["price_max"])
            break
    if price_max is None and raw:
        price_max = _parse_price_from_text(raw)
    
    # Checkout mode
    checkout_mode = "guest"
    if raw:
        rl = raw.lower()
        if "login" in rl and "guest" not in rl:
            checkout_mode = "login"
        elif "guest" in rl or "checkout as guest" in rl:
            checkout_mode = "guest"
    
    # Complete purchase, fill address
    complete_purchase = bool(re.search(r"complete\s+purchase|buy|checkout|purchase", raw or "", re.I))
    fill_address = bool(re.search(r"fill\s+address|billing|shipping|address\s+form", raw or "", re.I))
    if not complete_purchase and ("checkout" in (raw or "").lower() or "buy" in (raw or "").lower()):
        complete_purchase = True
    if not fill_address and "guest" in (raw or "").lower():
        fill_address = True  # Guest checkout typically requires address
    
    # Pincode
    pincode = _parse_pincode(steps, raw)
    
    # Start URL
    start_url = _parse_url(steps, raw, url)
    
    goal = GoalObject(
        search_query=search_query,
        price_max=price_max,
        checkout_mode=checkout_mode,
        complete_purchase=complete_purchase,
        fill_address=fill_address,
        pincode=pincode,
        start_url=start_url,
    )
    logger.info("Goal extracted: %s", goal.to_dict())
    return goal
