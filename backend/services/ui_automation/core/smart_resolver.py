"""
Phase 2 - Smart Resolver
Intelligent fallback when deterministic methods fail
Uses fuzzy matching and similarity scoring

🔒 PHASE 6 — DETERMINISTIC SELECTOR CACHING
Always picks same element, caches successful selectors
"""
import logging
import re
import hashlib
import json
import os
from playwright.async_api import Page, Locator
from difflib import SequenceMatcher
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)


def _weighted_score(
    semantic_similarity: float,
    role_weight: float,
    visibility_weight: float,
    position_weight: float,
    container_relevance: float,
) -> float:
    """
    Module 8 — Weighted selector scoring.
    score = semantic*0.5 + role*0.2 + visibility*0.1 + position*0.1 + container*0.1
    All inputs in [0, 1]. Returns combined score in [0, 1].
    """
    return (
        min(1.0, semantic_similarity) * 0.5
        + min(1.0, role_weight) * 0.2
        + min(1.0, visibility_weight) * 0.1
        + min(1.0, position_weight) * 0.1
        + min(1.0, container_relevance) * 0.1
    )

# 🔒 GLOBAL SELECTOR CACHE (persisted across runs)
SELECTOR_CACHE_FILE = "selector_cache.json"
_selector_cache: Dict[str, str] = {}


def _load_selector_cache():
    """Load cached selectors from disk"""
    global _selector_cache
    try:
        if os.path.exists(SELECTOR_CACHE_FILE):
            with open(SELECTOR_CACHE_FILE, 'r') as f:
                _selector_cache = json.load(f)
                logger.debug(f"📦 Loaded {len(_selector_cache)} cached selectors")
    except Exception as e:
        logger.debug(f"Cache load failed: {e}")
        _selector_cache = {}


def _save_selector_cache():
    """Save cached selectors to disk"""
    try:
        with open(SELECTOR_CACHE_FILE, 'w') as f:
            json.dump(_selector_cache, f, indent=2)
            logger.debug(f"💾 Saved {len(_selector_cache)} selectors to cache")
    except Exception as e:
        logger.debug(f"Cache save failed: {e}")


def _get_step_hash(target: str, url: str) -> str:
    """Generate hash for step (target + URL context)"""
    context = f"{url}::{target}"
    return hashlib.md5(context.encode()).hexdigest()


def _cache_selector(target: str, url: str, selector: str):
    """Cache successful selector for future runs"""
    step_hash = _get_step_hash(target, url)
    _selector_cache[step_hash] = selector
    _save_selector_cache()
    logger.debug(f"✅ Cached selector for '{target}': {selector}")


def _get_cached_selector(target: str, url: str) -> Optional[str]:
    """Retrieve cached selector if available"""
    if not _selector_cache:
        _load_selector_cache()
    
    step_hash = _get_step_hash(target, url)
    selector = _selector_cache.get(step_hash)
    
    if selector:
        logger.info(f"♻️ Using cached selector for '{target}': {selector}")
    
    return selector


# Load cache on module import
_load_selector_cache()


def similarity(a: str, b: str) -> float:
    """Calculate similarity score between two strings (0.0 to 1.0)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def exact_word_match(target: str, text: str) -> float:
    """
    Check if target words exist as complete words in text (word boundary check).
    Prevents 'continue' from matching 'computing' or 'legal' from matching 'illegal'.
    
    Returns:
    - 1.0 if all target words found as complete words
    - 0.9 if most target words found
    - 0.75 if some key words match (LOWERED for better fuzzy matching)
    - 0.0 if no exact word matches
    """
    target_lower = target.lower()
    text_lower = text.lower()
    
    # Extract words (alphanumeric sequences)
    target_words = re.findall(r'\b\w+\b', target_lower)
    text_words = set(re.findall(r'\b\w+\b', text_lower))
    
    if not target_words:
        return 0.0
    
    # Count exact word matches
    matches = sum(1 for word in target_words if word in text_words)
    match_ratio = matches / len(target_words)
    
    if match_ratio == 1.0:
        return 1.0  # Perfect word match
    elif match_ratio >= 0.7:
        return 0.9  # Most words match
    elif match_ratio >= 0.5:
        return 0.75  # Some words match (LOWERED from 0.7)
    elif match_ratio >= 0.3:
        return 0.6  # Few words match (NEW tier for partial matches)
    else:
        return 0.0  # Poor word match


def partial_similarity(short: str, long: str) -> float:
    """
    Calculate similarity for partial matches.
    Useful for product names where target is abbreviated.
    
    Example:
    - short: "LG 4 Star (1.5) Split AC product"
    - long: "LG 4 Star (1.5) Split AC, AI Convertible 6-in-1, Gold Fin+, ..."
    - Returns: 0.85 (high match because short is contained in long)
    """
    short_lower = short.lower()
    long_lower = long.lower()
    
    # If short is fully contained in long, high score
    if short_lower in long_lower:
        return 0.9
    
    # Otherwise, use token-based matching
    short_tokens = set(short_lower.split())
    long_tokens = set(long_lower.split())
    
    if not short_tokens:
        return 0.0
    
    # How many tokens from short appear in long?
    matching_tokens = short_tokens.intersection(long_tokens)
    token_match_score = len(matching_tokens) / len(short_tokens)
    
    return token_match_score


def _product_spec_penalty(target: str, candidate_text: str) -> float:
    """
    Penalize when target has specific product specs that conflict with candidate.
    E.g. target="LG 5 Star (1.0) ... 2025" vs candidate="LG 3 Star (1.5) ... 2026" → penalty.
    Returns multiplier (1.0 = no penalty, 0.3 = heavy penalty).
    """
    t, c = target.lower(), candidate_text.lower()
    penalty = 1.0
    # Star rating: 5 Star vs 3 Star
    star_t = re.search(r'(\d)\s*star', t)
    star_c = re.search(r'(\d)\s*star', c)
    if star_t and star_c and star_t.group(1) != star_c.group(1):
        penalty *= 0.4
    # Ton/kW: 1.0 vs 1.5, 3.5 vs 4.4
    for pattern in [r'\((\d+\.?\d*)\s*(?:ton|kw)', r'(\d+\.?\d*)\s*kw', r'(\d+\.?\d*)\s*ton']:
        mt, mc = re.search(pattern, t), re.search(pattern, c)
        if mt and mc:
            vt, vc = float(mt.group(1)), float(mc.group(1))
            if abs(vt - vc) > 0.1:
                penalty *= 0.5
            break
    # Year: 2025 vs 2026
    year_t = re.search(r'20\d{2}', t)
    year_c = re.search(r'20\d{2}', c)
    if year_t and year_c and year_t.group() != year_c.group():
        penalty *= 0.4
    return penalty


# Link text we must NOT click when target is a specific category, product, or CTA (e.g. "split air conditioners", "buy now")
GENERIC_NAV_LINK_BLOCKLIST = frozenset({
    "shop", "promotions", "support", "contact", "careers", "news", "blog",
    "sign in", "register", "login", "more", "view all", "see all", "explore",
    "menu", "close", "back", "next", "previous", "search", "cart", "account",
})


def _target_words(target: str) -> set:
    """Normalized words from target for overlap check."""
    return set(re.findall(r"\b\w+\b", target.lower()))


def _link_text_has_target_word(link_text: str, target_words: set) -> bool:
    """True if at least one target word appears as a whole word in link text."""
    if not target_words:
        return True
    link_words = set(re.findall(r"\b\w+\b", link_text.lower()))
    return bool(target_words & link_words)


def get_button_aliases(target: str) -> list[str]:
    """
    Get common aliases for button text.
    
    Example:
    - "Add to cart" → ["add to cart", "buy now", "add to bag", "add to basket"]
    - "Checkout" → ["checkout", "proceed to checkout", "continue"]
    - "Continue as guest" → ["continue", "guest checkout", "continue as guest"]
    """
    target_lower = target.lower()
    
    # Common button alias mappings
    alias_map = {
        "add to cart": ["add to cart", "buy now", "add to bag", "add to basket", "purchase"],
        "buy now": ["buy now", "add to cart", "add to bag", "purchase"],
        "buynow": ["buy now", "add to cart", "add to bag", "purchase"],
        "checkout": ["checkout", "proceed to checkout", "continue", "go to checkout"],
        "continue as guest": ["continue", "continue as guest", "guest checkout", "checkout as guest", "guest", "proceed"],
        "guest": ["continue as guest", "guest checkout", "checkout as guest", "guest", "continue", "proceed without account"],
        "any product": ["product", "view", "details", "buy", "add to cart"],
        "free delivery": ["free delivery", "free shipping", "standard delivery", "standard", "free", "free (standard)", "no charge"],
        "check beside pincode": ["check", "verify", "apply", "check pincode", "verify pincode"],
        "check": ["check", "verify", "apply", "ok"],
        "sign in": ["sign in", "log in", "login"],
        "sign up": ["sign up", "register", "create account"],
        "submit": ["submit", "send", "continue"],
    }
    
    # Check if target matches any known alias group
    for key, aliases in alias_map.items():
        if key in target_lower:
            return aliases
    
    # Default: just return the target
    return [target_lower]


async def smart_resolve_click(page: Page, target: str) -> Tuple[bool, Optional[str]]:
    """
    Phase 2: Intelligent element resolution with weighted scoring (Module 8).
    
    Returns:
        (success, selector_used) — selector_used is set when click succeeds for cache-on-validation.
    """
    logger.info(f"🔍 Phase 2: Smart resolving '{target}'")
    
    try:
        # 🔒 STEP 1: Check cache for previously successful selector
        cached_selector = _get_cached_selector(target, page.url)
        if cached_selector:
            try:
                cached_element = page.locator(cached_selector)
                if await cached_element.count() > 0:
                    await cached_element.first.scroll_into_view_if_needed(timeout=2000)
                    await page.wait_for_timeout(400)
                    await cached_element.first.click(timeout=3000)
                    logger.info(f"  ✅ Clicked using cached selector!")
                    await page.wait_for_timeout(600)
                    return (True, cached_selector)
            except Exception as e:
                logger.debug(f"  Cached selector failed: {e}, falling back to scoring")
        
        # Wait for any dropdowns/menus that might have appeared from previous action
        await page.wait_for_timeout(500)
        
        # Wait for page to be stable (especially after navigation-triggering actions like checkout)
        try:
            # Wait for DOM to be ready
            await page.wait_for_load_state("domcontentloaded", timeout=5000)
            logger.debug("  DOM content loaded")
        except Exception as e:
            logger.debug(f"  DOM wait timeout (might be already loaded): {e}")
        
        try:
            # Wait for network activity to settle
            await page.wait_for_load_state("networkidle", timeout=5000)
            logger.debug("  Network idle")
        except Exception as e:
            logger.debug(f"  Network idle timeout (might be already idle): {e}")
        
        # Additional wait for any client-side rendering
        await page.wait_for_timeout(500)
        
        # Get button aliases for better matching
        target_aliases = get_button_aliases(target)
        logger.debug(f"  Target aliases: {target_aliases}")
        
        # Determine if this is an e-commerce CTA (needs aggressive filtering)
        target_lower = target.lower()
        is_ecommerce_cta = any(keyword in target_lower for keyword in [
            'cart',
            'buy',
            'purchase',
            'checkout',
            'order',
            'payment',
            # Treat delivery/shipping options as high-impact actions too
            'delivery',
            'shipping',
            'free delivery',
        ])
        
        # 🔥 FIX: Detect if this is a product selection (needs product card support)
        is_product_selection = any(keyword in target_lower for keyword in [
            'star', 'ac', 'split', 'lg', 'samsung', 'product', 'model', 'kw', 'ton', 'btu', 'any product'
        ])
        
        if is_ecommerce_cta:
            logger.debug(f"  E-commerce CTA detected - applying aggressive filtering")
        if is_product_selection:
            logger.debug(f"  Product selection detected - including product cards")
        
        # Get all visible buttons only
        buttons = await page.locator("button:visible").all()
        logger.debug(f"  Found {len(buttons)} visible buttons")
        
        # Score all buttons
        candidates = []
        for btn in buttons:
            try:
                text = await btn.inner_text(timeout=500)  # Reduced from 1000ms
                if text:
                    text_lower = text.lower()
                    
                    # Skip if it looks like a navigation/utility button
                    if any(skip in text_lower for skip in ['menu', 'close', 'back', 'previous', 'next page', 'filter', 'sort']):
                        continue
                    
                    # 🔥 FIX: Check if element is in viewport (with error handling)
                    try:
                        in_viewport = await btn.evaluate("""el => {
                            const rect = el.getBoundingClientRect();
                            return (
                                rect.top >= 0 &&
                                rect.left >= 0 &&
                                rect.bottom <= window.innerHeight &&
                                rect.right <= window.innerWidth
                            );
                        }""")
                    except:
                        in_viewport = False
                    # Module 8: container relevance (main content vs footer/sidebar)
                    try:
                        in_main = await btn.evaluate("""el => {
                            const m = el.closest('main, #main, [class*="content"], [class*="main"], [role="main"]');
                            return m ? 1 : 0.7;
                        }""")
                    except:
                        in_main = 0.7
                    
                    # Check against all aliases (semantic similarity)
                    best_semantic = 0.0
                    for alias in target_aliases:
                        word_match_score = exact_word_match(alias, text)
                        full_score = similarity(text, alias)
                        partial_score = partial_similarity(alias, text)
                        if alias in text_lower or text_lower in alias:
                            substring_score = 0.85
                        else:
                            substring_score = 0.0
                        score = max(word_match_score, substring_score, full_score, partial_score)
                        best_semantic = max(best_semantic, score)
                    
                    # Module 8: weighted score = semantic*0.5 + role*0.2 + visibility*0.1 + position*0.1 + container*0.1
                    combined = _weighted_score(
                        semantic_similarity=best_semantic,
                        role_weight=1.0,  # button
                        visibility_weight=1.0,
                        position_weight=1.0 if in_viewport else 0.5,
                        container_relevance=float(in_main) if isinstance(in_main, (int, float)) else 0.7,
                    )
                    # Minimum semantic floor for buttons too (avoid clicking "Shop" for "buy now")
                    if is_ecommerce_cta and best_semantic < 0.4:
                        continue
                    if combined > 0.25:  # lower threshold since we now use weighted
                        candidates.append((btn, text, combined, in_viewport))
            except:
                continue
        
        # Sort by weighted score descending (DETERMINISTIC)
        candidates.sort(key=lambda x: (x[2], x[3]), reverse=True)
        
        # Minimum weighted confidence (Module 8: scale 0-1)
        min_confidence = 0.25
        if target_lower == "any product":
            min_confidence = 0.3
        elif is_product_selection:
            min_confidence = 0.35
        elif is_ecommerce_cta:
            min_confidence = 0.35 if any(k in target_lower for k in ["delivery", "shipping", "free delivery"]) else 0.4
        
        if candidates:
            logger.debug(f"  Found {len(candidates)} button candidates (weighted):")
            for i, (_, text, score, in_vp) in enumerate(candidates[:5], 1):
                vp_marker = "📍" if in_vp else "  "
                logger.debug(f"    {vp_marker}{i}. '{text}' (score: {score:.2f})")
            best_combined = candidates[0][2]
            if best_combined < min_confidence:
                logger.warning(
                    f"  ❌ Smart resolver button candidates below threshold "
                    f"(best={best_combined:.2f}, min={min_confidence:.2f})"
                )
                return (False, None)
        
        for i, (btn, text, score, in_viewport) in enumerate(candidates[:5], 1):
            try:
                logger.debug(f"  Trying candidate {i}: '{text}' (score: {score:.2f}, in_viewport: {in_viewport})")
                await btn.scroll_into_view_if_needed(timeout=2000)
                await page.wait_for_timeout(400)
                try:
                    selector = await btn.evaluate("el => { const id = el.id; const classes = Array.from(el.classList).join('.'); return id ? `#${id}` : (classes ? `.${classes}` : el.tagName); }")
                except:
                    selector = None
                await btn.click(timeout=3000)
                logger.info(f"  ✅ Clicked using smart resolver: '{text}' (score: {score:.2f})")
                if selector:
                    _cache_selector(target, page.url, selector)
                return (True, selector or f"button:has-text('{text[:50]}')")
            except Exception as e:
                logger.debug(f"  Candidate {i} click failed: {e}")
                continue
        
        # Try visible links as well
        links = await page.locator("a:visible").all()
        logger.debug(f"  Found {len(links)} visible links")
        
        target_words = _target_words(target)
        is_category_or_product_link = is_product_selection or any(
            w in target_lower for w in ("air", "split", "conditioner", "solution", "ac", "category", "product")
        )
        candidates = []
        for link in links:
            try:
                text = await link.inner_text(timeout=500)  # Reduced from 1000ms
                href = await link.get_attribute("href") or ""
                
                if text:
                    text_lower = text.lower().strip()
                    text_stripped = text_lower
                    href_lower = href.lower()
                    
                    # Blocklist: never click generic nav links when target is specific (category/product/CTA)
                    if is_ecommerce_cta or is_category_or_product_link:
                        if text_stripped in GENERIC_NAV_LINK_BLOCKLIST:
                            logger.debug(f"  Skipping blocklisted nav link: '{text[:40]}'")
                            continue
                        if any(bl in text_stripped for bl in ("shop", "promotions", "support", "contact", "careers", "news", "blog")):
                            # Only skip if link text is NOT an alias for target (e.g. "checkout" for target "checkout")
                            alias_match = any(alias in text_stripped or text_stripped in alias for alias in target_aliases)
                            if not alias_match:
                                logger.debug(f"  Skipping generic nav link for specific target: '{text[:40]}'")
                                continue
                    
                    # Only apply aggressive filtering for e-commerce CTAs
                    if is_ecommerce_cta:
                        skip_patterns = [
                            'terms', 'condition', 'policy', 'privacy', 'cookie',
                            'about', 'contact', 'support', 'help', 'faq',
                            'careers', 'jobs', 'press', 'news', 'blog',
                            'facebook', 'twitter', 'instagram', 'social',
                            'legal', 'copyright', 'trademark', 'disclaimer'
                        ]
                        if any(skip in text_lower for skip in skip_patterns):
                            logger.debug(f"  Skipping footer/nav link (CTA context): '{text}'")
                            continue
                        if any(skip in href_lower for skip in skip_patterns):
                            logger.debug(f"  Skipping policy link (CTA context): '{href}'")
                            continue
                    
                    # Category/product: link text must contain at least one word from target (avoids "Promotions" for "split air conditioners")
                    if is_category_or_product_link and target_words:
                        if not _link_text_has_target_word(text, target_words):
                            logger.debug(f"  Skipping link (no target word overlap): '{text[:40]}'")
                            continue
                    
                    try:
                        in_viewport = await link.evaluate("""el => {
                            const rect = el.getBoundingClientRect();
                            return (rect.top >= 0 && rect.left >= 0 && rect.bottom <= window.innerHeight && rect.right <= window.innerWidth);
                        }""")
                    except:
                        in_viewport = False
                    try:
                        in_main = await link.evaluate("""el => { const m = el.closest('main, #main, [class*="content"], [class*="main"], [role="main"]'); return m ? 1 : 0.7; }""")
                    except:
                        in_main = 0.7
                    best_semantic = 0.0
                    for alias in target_aliases:
                        word_match_score = exact_word_match(alias, text)
                        full_score = similarity(text, alias)
                        partial_score = partial_similarity(alias, text)
                        substring_score = 0.85 if (alias in text_lower or text_lower in alias) else 0.0
                        score = max(word_match_score, substring_score, full_score, partial_score)
                        best_semantic = max(best_semantic, score)
                    if is_product_selection and len(target) > 40 and len(text) > 40:
                        best_semantic *= _product_spec_penalty(target, text)
                    # Minimum semantic floor: don't click links with almost no text match (e.g. "Promotions" for "split air conditioners")
                    if best_semantic < 0.35:
                        logger.debug(f"  Skipping link (semantic too low {best_semantic:.2f}): '{text[:40]}'")
                        continue
                    combined = _weighted_score(
                        semantic_similarity=best_semantic,
                        role_weight=0.9,  # link
                        visibility_weight=1.0,
                        position_weight=1.0 if in_viewport else 0.5,
                        container_relevance=float(in_main) if isinstance(in_main, (int, float)) else 0.7,
                    )
                    if combined > 0.25:
                        candidates.append((link, text, combined, in_viewport))
            except:
                continue
        
        candidates.sort(key=lambda x: (x[2], x[3]), reverse=True)
        if candidates:
            best_combined = candidates[0][2]
            if best_combined < min_confidence:
                logger.warning(f"  ❌ Link candidates below threshold (best={best_combined:.2f})")
                return (False, None)
            for i, (link, text, score, in_viewport) in enumerate(candidates[:5], 1):
                try:
                    await link.scroll_into_view_if_needed(timeout=2000)
                    await page.wait_for_timeout(300)
                    await link.click(timeout=3000)
                    logger.info(f"  ✅ Clicked link using smart resolver: '{text}' (score: {score:.2f})")
                    return (True, None)  # link selector not cached (rely on text next time)
                except Exception as e:
                    logger.debug(f"  Link candidate {i} click failed: {e}")
                    continue
        
        # 🔥 FIX: Try product cards for product selections
        if is_product_selection:
            logger.debug(f"  Searching for product cards...")
            
            # Common product card selectors
            product_cards = await page.locator("""
                div[class*='product']:visible,
                article[class*='product']:visible,
                div[class*='card']:visible,
                div[class*='item']:visible,
                a[class*='product']:visible,
                div[data-product]:visible,
                div[role='article']:visible
            """).all()
            
            logger.debug(f"  Found {len(product_cards)} product card candidates")
            
            candidates = []
            for card in product_cards:
                try:
                    text = await card.inner_text(timeout=500)  # Reduced from 1000ms
                    if text and len(text) > 10:  # Product cards have substantial text
                        text_lower = text.lower()
                        
                        # Check if in viewport (with error handling)
                        try:
                            in_viewport = await card.evaluate("""el => {
                                const rect = el.getBoundingClientRect();
                                return (
                                    rect.top >= 0 &&
                                    rect.left >= 0 &&
                                    rect.bottom <= window.innerHeight &&
                                    rect.right <= window.innerWidth
                                );
                            }""")
                        except:
                            in_viewport = False
                        
                        # Score against target
                        best_score = 0.0
                        for alias in target_aliases:
                            word_match_score = exact_word_match(alias, text)
                            full_score = similarity(text, alias)
                            partial_score = partial_similarity(alias, text)
                            
                            if alias in text_lower or text_lower in alias:
                                substring_score = 0.85
                            else:
                                substring_score = 0.0
                            
                            score = max(word_match_score, substring_score, full_score, partial_score)
                            best_score = max(best_score, score)
                        
                        # Apply product spec penalty for exact model match
                        if len(target) > 40 and len(text) > 40:
                            spec_penalty = _product_spec_penalty(target, text)
                            best_score *= spec_penalty
                        
                        # Boost for viewport
                        if in_viewport:
                            best_score *= 1.2
                        
                        # Lower threshold for product cards (they have more text)
                        if best_score > 0.3:
                            candidates.append((card, text[:100], best_score, in_viewport))
                except:
                    continue
            
            candidates.sort(key=lambda x: (x[2], x[3]), reverse=True)
            
            if candidates:
                logger.debug(f"  Found {len(candidates)} product card matches:")
                for i, (_, text, score, in_vp) in enumerate(candidates[:5], 1):
                    vp_marker = "📍" if in_vp else "  "
                    logger.debug(f"    {vp_marker}{i}. '{text}...' (score: {score:.2f})")
            
            # Try top 3 product cards
            for i, (card, text, score, in_viewport) in enumerate(candidates[:3], 1):
                try:
                    logger.debug(f"  Trying product card {i}: score: {score:.2f}, in_viewport: {in_viewport}")
                    await card.scroll_into_view_if_needed(timeout=2000)
                    await page.wait_for_timeout(300)
                    await card.click(timeout=3000)
                    logger.info(f"  ✅ Clicked product card using smart resolver (score: {score:.2f})")
                    return (True, None)
                except Exception as e:
                    logger.debug(f"  Product card {i} click failed: {e}")
                    continue
        
        logger.warning(f"  ❌ Smart resolver found no good matches for '{target}'")
        return (False, None)
        
    except Exception as e:
        error_msg = str(e).lower()
        if "execution context was destroyed" in error_msg or "navigation" in error_msg:
            logger.info(f"  ✅ Click succeeded (caused navigation)")
            return (True, None)
        logger.error(f"  ❌ Smart resolver error: {e}")
        return (False, None)


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
        # Get all input fields (visible first)
        inputs = await page.locator("input:visible, textarea:visible").all()
        logger.debug(f"  Found {len(inputs)} visible input fields")
        
        # Fallback: if 0 visible (LG overlay may use opacity/transform), try without :visible
        if len(inputs) == 0 and "search" in target.lower():
            inputs = await page.locator("input, textarea").all()
            logger.info(f"  ⚠️ 0 visible inputs; retrying with {len(inputs)} total inputs (no :visible filter)")
        
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
        input_debug = []  # For failure logging
        for inp in inputs:
            try:
                placeholder = await inp.get_attribute("placeholder") or ""
                aria_label = await inp.get_attribute("aria-label") or ""
                input_type = await inp.get_attribute("type") or "text"
                name = await inp.get_attribute("name") or ""
                input_id = await inp.get_attribute("id") or ""
                
                # Combine all attributes for fuzzy matching
                combined = f"{placeholder} {aria_label} {name} {input_id}".strip()
                input_debug.append(f"type={input_type} placeholder='{placeholder[:30]}' aria-label='{aria_label[:30]}'")
                
                # Boost score for search-type inputs if target mentions "search"
                base_score = similarity(combined, target) if combined else 0
                
                # Bonus for input type matching
                if "search" in target.lower() and input_type == "search":
                    base_score += 0.3
                elif "search" in target.lower() and input_type == "text" and not combined:
                    # LG/overlay search often uses type=text with no placeholder
                    base_score += 0.2
                elif "email" in target.lower() and input_type == "email":
                    base_score += 0.3
                    
                # Bonus for visible inputs with no disabled attribute
                is_enabled = await inp.is_enabled()
                if is_enabled:
                    base_score += 0.1
                
                if base_score > 0.25:  # Slightly lower threshold to catch overlay search inputs
                    candidates.append((inp, combined or f"[{input_type}]", base_score))
            except Exception as ex:
                logger.debug(f"  Input attr read failed: {ex}")
                continue
        
        candidates.sort(key=lambda x: x[2], reverse=True)
        
        for i, (inp, label, score) in enumerate(candidates[:3], 1):
            try:
                logger.info(f"  Trying candidate {i}: '{label}' (score: {score:.2f})")
                await inp.scroll_into_view_if_needed(timeout=2000)
                await inp.fill(value, timeout=3000)
                logger.info(f"  ✅ Typed using smart resolver: '{label}' (score: {score:.2f})")
                return True
            except Exception as e:
                logger.warning(f"  Candidate {i} type failed: {e}")
                continue
        
        # Fallback: for "search" target, try input[type="search"] or first text input (with or without :visible)
        if "search" in target.lower():
            try:
                search_inputs = page.locator("input[type='search'], input[type='text']")
                if await search_inputs.count() > 0:
                    search_input = search_inputs.first
                    logger.info("  🔄 Fallback: Trying input[type=search] or first text input")
                    await search_input.scroll_into_view_if_needed(timeout=2000)
                    await search_input.fill(value, timeout=3000)
                    logger.info("  ✅ Typed using search fallback (input[type=search/text])")
                    return True
            except Exception as ef:
                logger.warning(f"  Search fallback failed: {ef}")
        
        logger.warning(
            f"  ❌ Smart resolver found no good input matches for '{target}'. "
            f"Found {len(inputs)} visible inputs: {input_debug[:5]}"
        )
        return False
        
    except Exception as e:
        logger.error(f"  ❌ Smart resolver error: {e}")
        return False
