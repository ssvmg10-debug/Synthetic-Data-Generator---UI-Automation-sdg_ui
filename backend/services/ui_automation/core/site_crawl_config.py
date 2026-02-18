"""
Site crawl configuration — whole-application coverage.

Defines navigation flows so we can pre-crawl a site (e.g. LG India) and build
site_knowledge.json for any test case. Flows are generic: list of click labels
per section; the runner uses the same resolution as the executor (smart_click,
site_knowledge) so no site-specific selectors.

Design: one flow = start at base_url, then click label1, label2, ... .
Each step records the page into site knowledge. This covers:
- Main nav (TV/Audio/Video, Home Appliances, Air Solutions, Computing, Accessories, Support)
- Sub-categories (All TV & Soundbars, Refrigerators, Water Purifiers, Split Air Conditioners, ...)
- Key CTAs (Buy Now, Know More, Checkout, Continue as guest, Search, etc.) appear on those pages
  and get recorded automatically.
"""

from __future__ import annotations

from typing import Any, Dict, List

# Base URL for LG India — used by run_lg_site_crawl and as reference
LG_INDIA_BASE = "https://www.lg.com/in"

# Flows: each is a list of click labels in order. First step is "after landing on base".
# Runner will: goto base -> record -> click label[0] -> record -> click label[1] -> record -> ...
# Keep labels short and match visible nav text (e.g. "Home Appliances", "All Water Purifiers").
LG_INDIA_FLOWS: List[List[str]] = [
    # Home only (banners, search, main nav visible)
    [],
    # TV/Audio/Video — broad coverage
    ["TV/Audio/Video", "All TV & Soundbars"],
    ["TV/Audio/Video", "LG SIGNATURE OLED"],
    ["TV/Audio/Video", "OLED evo"],
    ["TV/Audio/Video", "OLED"],
    ["TV/Audio/Video", "MiniLED"],
    ["TV/Audio/Video", "QNED"],
    ["TV/Audio/Video", "4K UHD TVs"],
    ["TV/Audio/Video", "TV by Size", "165 cm (65)"],
    ["TV/Audio/Video", "TV by Size", "139 cm (55)"],
    ["TV/Audio/Video", "Soundbars", "All Soundbars"],
    ["TV/Audio/Video", "Soundbars", "Featured Soundbars"],
    ["TV/Audio/Video", "Wireless Earbuds", "All Wireless Earbuds"],
    ["TV/Audio/Video", "Bluetooth Speakers", "All Bluetooth Speakers"],
    ["TV/Audio/Video", "Lifestyle Screens", "StanbyME"],
    # Home Appliances
    ["Home Appliances", "Refrigerators", "All Refrigerators"],
    ["Home Appliances", "Refrigerators", "French Door Refrigerators"],
    ["Home Appliances", "Laundry", "All Washing Machines"],
    ["Home Appliances", "Laundry", "Front Loading Washing Machines"],
    ["Home Appliances", "Water Purifiers", "All Water Purifiers"],
    ["Home Appliances", "Microwave Ovens", "All Microwave Ovens"],
    ["Home Appliances", "Dishwashers", "All Dishwashers"],
    ["Home Appliances", "Home Appliances Accessories"],
    # Air Solutions
    ["Air Solutions", "Air Conditioners", "All Air Conditioners"],
    ["Air Solutions", "Air Conditioners", "Split Air Conditioners"],
    ["Air Solutions", "Air Conditioners", "Window Air Conditioners"],
    ["Air Solutions", "Air Care", "All Air Cares"],
    # Computing
    ["Computing", "Monitors", "All Monitors"],
    ["Computing", "Monitors", "Gaming"],
    ["Computing", "Laptop", "All Laptops"],
    ["Computing", "Laptop", "LG gram"],
    ["Computing", "Computer Accessories"],
    # Accessories
    ["Accessories", "Explore Accessories", "All Accessories"],
    # Shop (offers, promotions)
    ["Shop", "Offers", "Shop The Latest"],
    ["Shop", "Offers", "Promotions"],
    ["Shop", "Offers", "Best Sellers"],
    ["Shop", "Why buy from LG", "LG Member Benefits"],
    # Support
    ["Support", "Product Support", "Warranty Information"],
    ["Support", "Product Support", "Manuals & Softwares"],
    ["Support", "Order Support", "Track My Order"],
    ["Support", "Order Support", "Frequently Asked Questions"],
    ["Support", "Contact", "Contact Us"],
    ["Support", "Contact", "Chatbot"],
]

# Optional: direct URLs to open and record (e.g. sitemap, key landing pages)
# Runner will open each and record_from_page.
LG_INDIA_EXTRA_URLS: List[str] = [
    f"{LG_INDIA_BASE}/sitemap",
    f"{LG_INDIA_BASE}/in/tv-soundbars/all-tv-soundbars",
    f"{LG_INDIA_BASE}/in/home-appliances/water-purifiers/all-water-purifiers",
    f"{LG_INDIA_BASE}/in/home-appliances/refrigerators/all-refrigerators",
    f"{LG_INDIA_BASE}/in/home-appliances/laundry/all-washing-machines",
    f"{LG_INDIA_BASE}/in/home-appliances/microwave-ovens/all-microwave-ovens",
    f"{LG_INDIA_BASE}/in/air-conditioners/split-air-conditioners",
    f"{LG_INDIA_BASE}/in/air-conditioners/window-air-conditioners",
    f"{LG_INDIA_BASE}/in/monitors/all-monitors",
    f"{LG_INDIA_BASE}/in/laptop/all-laptops",
]


def get_lg_india_crawl_plan() -> Dict[str, Any]:
    """Return full crawl plan for LG India (flows + extra URLs)."""
    return {
        "base_url": LG_INDIA_BASE,
        "flows": LG_INDIA_FLOWS,
        "extra_urls": LG_INDIA_EXTRA_URLS,
    }
