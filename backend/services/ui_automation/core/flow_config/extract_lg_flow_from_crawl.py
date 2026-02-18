"""
Extract LG flow handlers/validations from crawl output (page_content.html).
Run after crawling lg.com/in or lg.com/us to enrich lg_flow_config.json.
"""
import json
import re
from pathlib import Path
from typing import List, Set

logger = __import__("logging").getLogger(__name__)

# Patterns for modal/dialog button text (LG-specific + generic)
MODAL_BUTTON_PATTERNS = [
    r"(?i)OK|Continue|Close|Dismiss|Accept|Got it|Select delivery",
    r"(?i)Select delivery option|View delivery options",
    r"(?i)Got it|I understand|Understood",
]
# Known LG labels from crawl
LG_BUTTON_TEXTS = {
    "OK", "Continue", "Close", "Select delivery", "Select delivery option",
    "Add to Basket", "Buy Now", "Checkout", "Place order", "Continue as guest",
    "Free Delivery", "Free shipping",
}
# Pincode input patterns
PINCODE_INPUT_PATTERNS = [
    r'input[^>]*(?:name|id|placeholder|aria-label)=["\'][^"\']*pin[^"\']*["\']',
    r'input[^>]*(?:name|id|placeholder|aria-label)=["\'][^"\']*zip[^"\']*["\']',
    r'input[^>]*(?:name|id|placeholder|aria-label)=["\'][^"\']*pincode[^"\']*["\']',
]


def extract_button_texts(html: str) -> Set[str]:
    """Extract button/link text from HTML that may appear in modals."""
    found: Set[str] = set()
    # buttons
    for m in re.finditer(r"<button[^>]*>([^<]{1,50})</button>", html, re.I | re.S):
        t = re.sub(r"\s+", " ", m.group(1)).strip()
        if t and len(t) < 40:
            found.add(t)
    # [role=button] and links in dialogs
    for m in re.finditer(r'<(?:a|span|div)[^>]*role=["\']button["\'][^>]*>([^<]{1,50})</', html, re.I | re.S):
        t = re.sub(r"\s+", " ", m.group(1)).strip()
        if t and len(t) < 40:
            found.add(t)
    # cmp-button text
    for m in re.finditer(r'<span class="[^"]*cmp-button__text[^"]*"[^>]*>([^<]{1,50})</span>', html):
        t = re.sub(r"\s+", " ", m.group(1)).strip()
        if t:
            found.add(t)
    return found


def extract_modal_buttons(html: str) -> List[str]:
    """Suggest button texts for dismiss_modal based on crawl."""
    buttons = extract_button_texts(html)
    # Filter to likely modal-dismiss buttons
    keywords = ["ok", "continue", "close", "dismiss", "select delivery", "got it", "accept"]
    suggested = []
    for b in buttons:
        bl = b.lower()
        if any(kw in bl for kw in keywords) and len(b) < 35:
            suggested.append(b)
    return sorted(set(suggested), key=str.lower)


def extract_pincode_selectors(html: str) -> List[str]:
    """Find pincode input patterns for flow config."""
    selectors = []
    for pat in PINCODE_INPUT_PATTERNS:
        if re.search(pat, html, re.I):
            selectors.append(pat)
    return selectors


def extract_delivery_labels(html: str) -> Set[str]:
    """Extract delivery/shipping option labels."""
    found: Set[str] = set()
    for m in re.finditer(r"(?i)(free\s+delivery|free\s+shipping|standard\s+delivery|express\s+delivery)", html):
        found.add(m.group(1).strip())
    # From structured data
    for m in re.finditer(r'alt="([^"]*[Dd]elivery[^"]*)"', html):
        found.add(m.group(1))
    return found


def merge_into_config(config_path: Path, new_buttons: List[str], merge: bool = True) -> None:
    """Merge extracted button texts into lg_flow_config dismiss_modal actions."""
    if not config_path.exists():
        return
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    existing = set()
    for h in cfg.get("handlers", []):
        for a in h.get("actions", []):
            if a.get("type") == "dismiss_modal":
                existing.update(a.get("button_texts", []))
    combined = list(existing) if merge else []
    for b in new_buttons:
        if b not in combined:
            combined.append(b)
    for h in cfg.get("handlers", []):
        for a in h.get("actions", []):
            if a.get("type") == "dismiss_modal":
                a["button_texts"] = combined
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    logger.info("Updated %s with button texts: %s", config_path, combined[:10])


def run_on_crawl_dir(crawl_dir: Path, config_path: Path, merge: bool = True) -> dict:
    """
    Process crawl directory and optionally update flow config.
    Returns extracted data.
    """
    html_file = crawl_dir / "page_content.html"
    if not html_file.exists():
        # Try first subdir
        subdirs = [d for d in crawl_dir.iterdir() if d.is_dir()]
        if subdirs:
            html_file = subdirs[0] / "page_content.html"
    if not html_file.exists():
        return {"error": f"No page_content.html in {crawl_dir}"}
    html = html_file.read_text(encoding="utf-8", errors="replace")
    buttons = extract_modal_buttons(html)
    delivery = extract_delivery_labels(html)
    pincode = extract_pincode_selectors(html)
    if config_path and buttons:
        merge_into_config(config_path, buttons, merge=merge)
    return {
        "modal_buttons": buttons,
        "delivery_labels": list(delivery),
        "has_pincode_input": bool(pincode),
    }


if __name__ == "__main__":
    import sys
    backend = Path(__file__).resolve().parent.parent.parent.parent.parent
    crawls = backend / "temp_crawl" / "crawls"
    config = Path(__file__).parent / "lg_flow_config.json"
    dirs = sorted(crawls.glob("*lg*"), key=lambda p: p.stat().st_mtime, reverse=True) if crawls.exists() else []
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else (dirs[0] if dirs else crawls)
    out = run_on_crawl_dir(target, config)
    print(json.dumps(out, indent=2))
