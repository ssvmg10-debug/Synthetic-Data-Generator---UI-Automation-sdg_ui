"""
Phase 2 - Smart Resolver
Intelligent fallback when deterministic methods fail
Uses fuzzy matching and similarity scoring
"""
import logging
from playwright.async_api import Page, Locator
from difflib import SequenceMatcher
from typing import Optional

logger = logging.getLogger(__name__)


def similarity(a: str, b: str) -> float:
    """Calculate similarity score between two strings (0.0 to 1.0)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


async def smart_resolve_click(page: Page, target: str) -> bool:
    """
    Phase 2: Intelligent element resolution.
    
    Only called if Phase 1 deterministic methods fail.
    
    Strategy:
    1. Extract all clickable elements
    2. Score each by text similarity
    3. Try top 3 candidates (>0.7 score)
    4. Return success or failure
    """
    logger.info(f"🔍 Phase 2: Smart resolving '{target}'")
    
    try:
        # Get all buttons
        buttons = await page.locator("button").all()
        logger.debug(f"  Found {len(buttons)} buttons")
        
        # Score all buttons
        candidates = []
        for btn in buttons:
            try:
                text = await btn.inner_text(timeout=1000)
                if text:
                    score = similarity(text, target)
                    if score > 0.7:
                        candidates.append((btn, text, score))
            except:
                continue
        
        # Sort by score descending
        candidates.sort(key=lambda x: x[2], reverse=True)
        
        # Try top 3 candidates
        for i, (btn, text, score) in enumerate(candidates[:3], 1):
            try:
                logger.debug(f"  Candidate {i}: '{text}' (score: {score:.2f})")
                await btn.scroll_into_view_if_needed(timeout=2000)
                await btn.click(timeout=3000)
                logger.info(f"  ✅ Clicked using smart resolver: '{text}' (score: {score:.2f})")
                return True
            except Exception as e:
                logger.debug(f"  Candidate {i} click failed: {e}")
                continue
        
        # Try links as well
        links = await page.locator("a").all()
        logger.debug(f"  Found {len(links)} links")
        
        candidates = []
        for link in links:
            try:
                text = await link.inner_text(timeout=1000)
                if text:
                    score = similarity(text, target)
                    if score > 0.7:
                        candidates.append((link, text, score))
            except:
                continue
        
        candidates.sort(key=lambda x: x[2], reverse=True)
        
        for i, (link, text, score) in enumerate(candidates[:3], 1):
            try:
                logger.debug(f"  Link candidate {i}: '{text}' (score: {score:.2f})")
                await link.scroll_into_view_if_needed(timeout=2000)
                await link.click(timeout=3000)
                logger.info(f"  ✅ Clicked link using smart resolver: '{text}' (score: {score:.2f})")
                return True
            except Exception as e:
                logger.debug(f"  Link candidate {i} click failed: {e}")
                continue
        
        logger.warning(f"  ❌ Smart resolver found no good matches for '{target}'")
        return False
        
    except Exception as e:
        logger.error(f"  ❌ Smart resolver error: {e}")
        return False


async def smart_resolve_type(page: Page, target: str, value: str) -> bool:
    """
    Phase 2: Intelligent input field resolution.
    
    Finds input fields by:
    1. Fuzzy label matching (placeholder, aria-label)
    2. Visible and focused inputs (for search bars that were just opened)
    3. Input type matching (search, text, email, etc.)
    """
    logger.info(f"🔍 Phase 2: Smart resolving input '{target}'")
    
    try:
        # Get all input fields
        inputs = await page.locator("input:visible, textarea:visible").all()
        logger.debug(f"  Found {len(inputs)} visible input fields")
        
        # First try: Check for focused/active input (common for search bars)
        try:
            focused = page.locator("input:focus, textarea:focus")
            if await focused.count() > 0:
                logger.debug("  Found focused input field")
                await focused.first.fill(value, timeout=3000)
                logger.info(f"  ✅ Typed into focused input")
                return True
        except Exception as e:
            logger.debug(f"  No focused input: {e}")
        
        # Score by placeholder, aria-label, type, and name
        candidates = []
        for inp in inputs:
            try:
                placeholder = await inp.get_attribute("placeholder") or ""
                aria_label = await inp.get_attribute("aria-label") or ""
                input_type = await inp.get_attribute("type") or "text"
                name = await inp.get_attribute("name") or ""
                input_id = await inp.get_attribute("id") or ""
                
                # Combine all attributes for fuzzy matching
                combined = f"{placeholder} {aria_label} {name} {input_id}"
                
                # Boost score for search-type inputs if target mentions "search"
                base_score = similarity(combined, target) if combined.strip() else 0
                
                # Bonus for input type matching
                if "search" in target.lower() and input_type == "search":
                    base_score += 0.3
                elif "email" in target.lower() and input_type == "email":
                    base_score += 0.3
                    
                # Bonus for visible inputs with no disabled attribute
                is_enabled = await inp.is_enabled()
                if is_enabled:
                    base_score += 0.1
                
                if base_score > 0.3:  # Lower threshold to catch more candidates
                    candidates.append((inp, combined or f"[{input_type}]", base_score))
            except:
                continue
        
        candidates.sort(key=lambda x: x[2], reverse=True)
        
        for i, (inp, label, score) in enumerate(candidates[:3], 1):
            try:
                logger.debug(f"  Candidate {i}: '{label}' (score: {score:.2f})")
                await inp.scroll_into_view_if_needed(timeout=2000)
                await inp.fill(value, timeout=3000)
                logger.info(f"  ✅ Typed using smart resolver: '{label}' (score: {score:.2f})")
                return True
            except Exception as e:
                logger.debug(f"  Candidate {i} type failed: {e}")
                continue
        
        logger.warning(f"  ❌ Smart resolver found no good input matches for '{target}'")
        return False
        
    except Exception as e:
        logger.error(f"  ❌ Smart resolver error: {e}")
        return False
