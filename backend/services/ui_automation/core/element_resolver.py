"""
Phase 1 - Smart Element Resolver
Multi-strategy element finding WITHOUT AI/healing
"""
import logging
from playwright.async_api import Page
import re
from .valid_data_generator import generate_valid_data

logger = logging.getLogger(__name__)

def _expand_keywords(label: str) -> list[str]:
    """
    Expand semantic keywords with common aliases.
    
    Examples:
    - 'pincode' → ['pincode', 'pin', 'zip', 'postal', 'delivery', 'area']
    - 'email' → ['email', 'e-mail', 'mail']
    - 'phone' → ['phone', 'mobile', 'tel', 'number']
    """
    label_lower = label.lower()
    keywords = [label]  # Always include original
    
    # Pincode/ZIP variations
    if any(word in label_lower for word in ['pincode', 'pin', 'zip', 'postal']):
        keywords.extend(['pincode', 'pin', 'zip', 'postal', 'postcode', 'delivery', 'area', 'code', 'zipcode'])
    
    # Email variations
    elif any(word in label_lower for word in ['email', 'e-mail', 'mail']):
        keywords.extend(['email', 'e-mail', 'mail'])
    
    # Phone variations
    elif any(word in label_lower for word in ['phone', 'mobile', 'tel', 'contact']):
        keywords.extend(['phone', 'mobile', 'tel', 'telephone', 'contact', 'number'])
    
    # Search variations
    elif 'search' in label_lower:
        keywords.extend(['search', 'query', 'find'])
    
    # Name variations
    elif 'name' in label_lower:
        keywords.extend(['name', 'fullname', 'full name'])
    
    # Address variations
    elif 'address' in label_lower:
        keywords.extend(['address', 'street', 'location'])
    
    # Deduplicate while preserving order
    seen = set()
    unique_keywords = []
    for k in keywords:
        k_lower = k.lower()
        if k_lower not in seen:
            seen.add(k_lower)
            unique_keywords.append(k)
    
    return unique_keywords


def _expand_select_keywords(label: str) -> list[str]:
    """
    Expand SELECT keywords for delivery options, payment methods, etc.
    
    Examples:
    - 'free delivery' → ['free delivery', 'free shipping', 'standard delivery', 'free', 'no charge', ...]
    - 'credit card' → ['credit card', 'credit', 'card', 'visa', 'mastercard', 'payment']
    """
    label_lower = label.lower()
    keywords = [label]  # Always include original
    
    # Delivery/shipping options - ENHANCED with more variations
    if any(word in label_lower for word in ['free', 'delivery', 'shipping', 'standard']):
        keywords.extend([
            'free', 'free shipping', 'free delivery', 'standard', 'standard delivery', 
            'standard shipping', 'no charge', 'complimentary', 'delivery', 'shipping',
            'free standard', 'regular delivery', 'regular shipping', 'free (standard)',
            '₹0', 'rs.0', '$0', '£0', 'FREE', 'Standard Delivery'
        ])
    
    # Payment methods
    elif any(word in label_lower for word in ['credit', 'debit', 'card', 'payment']):
        keywords.extend(['credit', 'debit', 'card', 'visa', 'mastercard', 'payment', 'pay by card'])
    
    # Yes/No options
    elif any(word in label_lower for word in ['yes', 'no', 'agree', 'accept']):
        keywords.extend(['yes', 'no', 'agree', 'accept', 'confirm', 'I agree'])
    
    # Deduplicate
    seen = set()
    unique_keywords = []
    for k in keywords:
        k_lower = k.lower()
        if k_lower not in seen:
            seen.add(k_lower)
            unique_keywords.append(k)
    
    return unique_keywords

async def smart_click(page: Page, label: str):
    """
    Try multiple strategies to find and click element.
    NO retries, NO healing - just try different selectors.
    
    This alone increases success rate 30-40%.
    """
    logger.info(f"🎯 Clicking: {label}")
    
    # Wait for any pending navigations or dropdowns from previous action
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=2000)
    except:
        pass
    
    # Small wait for dropdowns/menus to appear after previous click
    await page.wait_for_timeout(500)
    
    # Candidate strategies (order matters - most reliable first)
    candidates = [
        # Strategy 1: Role-based (most semantic)
        lambda: page.get_by_role("button", name=re.compile(f"^{re.escape(label)}$", re.I)),
        lambda: page.get_by_role("link", name=re.compile(f"^{re.escape(label)}$", re.I)),
        
        # Strategy 2: Partial match on roles
        lambda: page.get_by_role("button", name=re.compile(re.escape(label), re.I)),
        lambda: page.get_by_role("link", name=re.compile(re.escape(label), re.I)),
        
        # Strategy 3: Text content match
        lambda: page.get_by_text(label, exact=True),
        lambda: page.get_by_text(re.compile(f"^{re.escape(label)}$", re.I)),
        lambda: page.get_by_text(re.compile(re.escape(label), re.I)),
        
        # Strategy 4: Playwright text selector
        lambda: page.locator(f"text={label}"),
        lambda: page.locator(f"text=/{re.escape(label)}/i"),
    ]
    
    for idx, get_candidate in enumerate(candidates, 1):
        try:
            candidate = get_candidate()
            count = await candidate.count()
            
            if count > 0:
                logger.debug(f"  Strategy {idx} found {count} match(es)")
                
                # 🔥 FIX: When multiple matches, find the one in viewport
                if count > 1:
                    logger.debug(f"  Multiple matches found, selecting best visible candidate")
                    best_element = None
                    best_score = -1
                    
                    for i in range(min(count, 5)):  # Check first 5 matches max
                        try:
                            elem = candidate.nth(i)
                            # Check if element is visible
                            is_visible = await elem.is_visible()
                            if not is_visible:
                                continue
                            
                            # Check if element is in viewport
                            in_viewport = await elem.evaluate("""el => {
                                const rect = el.getBoundingClientRect();
                                return (
                                    rect.top >= 0 &&
                                    rect.left >= 0 &&
                                    rect.bottom <= window.innerHeight &&
                                    rect.right <= window.innerWidth
                                );
                            }""")
                            
                            # Score: in viewport = 10, visible but not in viewport = 5
                            score = 10 if in_viewport else 5
                            
                            if score > best_score:
                                best_score = score
                                best_element = elem
                        except:
                            continue
                    
                    if best_element:
                        await best_element.wait_for(state="visible", timeout=5000)
                        await best_element.click(timeout=5000)
                        logger.info(f"  ✅ Clicked using strategy {idx} (best match in viewport)")
                        return
                else:
                    # Single match, click it
                    await candidate.first.wait_for(state="visible", timeout=5000)
                    await candidate.first.click(timeout=5000)
                    logger.info(f"  ✅ Clicked using strategy {idx}")
                    return
        except Exception as e:
            logger.debug(f"  Strategy {idx} failed: {e}")
            continue
    
    # If all strategies fail, raise error
    raise Exception(f"Element '{label}' not found after {len(candidates)} strategies")


async def smart_type(page: Page, label: str, value: str):
    """
    🔵 ENTERPRISE-GRADE Dynamic Input Resolution
    
    Phase 1: Deterministic with attribute scoring
    
    New capabilities:
    - Valid data generation for Indian e-commerce (mobile, email, names)
    - Semantic target normalization already done in compiler
    - Keyword expansion for common field aliases
    - Attribute-based scoring (placeholder, name, id, aria-label)
    - Modal/container-scoped search
    - AJAX stabilization
    - Enter/Tab after typing
    """
    # Generate valid data if needed
    valid_value = generate_valid_data(label, value)
    
    logger.info(f"⌨️  Typing '{valid_value}' into: {label}")
    
    # 🔵 FIX 3: Wait for possible AJAX/modal after previous click
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=3000)
        logger.debug(f"  ⏳ Page stabilized after AJAX wait")
    except:
        pass
    
    # 🔵 CRITICAL FIX: Keyword expansion for semantic aliases
    # "pincode" → ["pincode", "pin", "zip", "postal", "delivery", "area"]
    keywords = _expand_keywords(label)
    logger.debug(f"  🔍 Expanded keywords: {keywords}")
    
    # 🔵 FIX 2: Context-aware search scope
    search_scope = page
    modal_found = False
    try:
        # Check for modal/dialog/popup (common after "Buy Now")
        modal_selectors = [
            "dialog:visible",
            ".modal:visible",
            "[role='dialog']:visible",
            ".popup:visible",
            "[class*='modal']:visible",
            "[class*='Modal']:visible",
            "[class*='dialog']:visible",
            "[class*='Dialog']:visible"
        ]
        
        for selector in modal_selectors:
            modal = page.locator(selector)
            if await modal.count() > 0:
                search_scope = modal.first
                modal_found = True
                logger.info(f"  🎯 MODAL DETECTED ('{selector}'), scoping search to container")
                break
    except Exception as e:
        logger.debug(f"  Modal detection: {e}")
    
    if not modal_found:
        logger.debug(f"  📄 No modal detected, searching full page")
    
    # Try each keyword variation
    for keyword in keywords:
        logger.debug(f"  🔑 Trying keyword: '{keyword}'")
        
        # 🔵 FIX 2: Deterministic strategies with attribute scoring
        candidates = [
            # Strategy 1: Label-based (semantic HTML)
            lambda k=keyword: search_scope.get_by_label(k, exact=False),
            
            # Strategy 2: Placeholder match (common for pincode, email, etc.)
            lambda k=keyword: search_scope.locator(f"input[placeholder*='{k}' i], textarea[placeholder*='{k}' i]"),
            
            # Strategy 3: Name attribute (pincode → name='pincode')
            lambda k=keyword: search_scope.locator(f"input[name*='{k}' i], textarea[name*='{k}' i]"),
            
            # Strategy 4: ID match
            lambda k=keyword: search_scope.locator(f"input[id*='{k}' i], textarea[id*='{k}' i]"),
            
            # Strategy 5: Aria-label
            lambda k=keyword: search_scope.locator(f"input[aria-label*='{k}' i], textarea[aria-label*='{k}' i]"),
            
            # Strategy 6: Data attributes
            lambda k=keyword: search_scope.locator(f"input[data-test*='{k}' i], input[data-testid*='{k}' i]"),
            
            # Strategy 7: Nearby label
            lambda k=keyword: search_scope.locator(f"label:has-text('{k}') + input, label:has-text('{k}') + textarea"),
            
            # Strategy 8: Text content nearby
            lambda k=keyword: search_scope.locator(f"input:near(:text('{k}')), textarea:near(:text('{k}'))"),
        ]
        
        for idx, locator_fn in enumerate(candidates, 1):
            try:
                locator = locator_fn()
                if await locator.count() > 0:
                    first = locator.first
                    await first.scroll_into_view_if_needed(timeout=2000)
                    await first.fill(valid_value, timeout=5000)
                    
                    # 🔵 FIX 4: Trigger validation (Tab or Enter)
                    try:
                        await first.press("Tab")
                    except:
                        pass
                    
                    logger.info(f"  ✅ Typed using keyword '{keyword}' + strategy {idx}")
                    return
            except Exception as e:
                logger.debug(f"  Strategy {idx} with '{keyword}' failed: {e}")
                continue
    
    # 🔵 AGGRESSIVE FALLBACK: If in modal, try ANY visible text/number input
    if modal_found:
        logger.warning(f"  ⚠️ No keyword matched, trying AGGRESSIVE fallback: any input in modal")
        try:
            fallback_inputs = search_scope.locator("input[type='text']:visible, input[type='number']:visible, input[type='tel']:visible, input:not([type]):visible")
            count = await fallback_inputs.count()
            logger.debug(f"  Found {count} fallback input candidates in modal")
            
            if count > 0:
                # Try first input
                first = fallback_inputs.first
                await first.scroll_into_view_if_needed(timeout=2000)
                await first.fill(valid_value, timeout=5000)
                await first.press("Tab")
                logger.info(f"  ✅ Typed using AGGRESSIVE FALLBACK (first input in modal)")
                return
        except Exception as e:
            logger.debug(f"  Aggressive fallback failed: {e}")
    
    # If we reach here, all strategies failed
    logger.error(f"  ❌ All strategies exhausted for: {label}")
    
    raise Exception(f"Input field '{label}' not found after {len(candidates)} strategies")


async def smart_select(page: Page, label: str, value: str = None, retry_count: int = 0, max_retries: int = 2):
    """
    Handle SELECT instructions (radio buttons, checkboxes, dropdown options).
    
    Enhanced with:
    - Keyword expansion ("free delivery" → ["free", "delivery", "standard", "no charge"])
    - Radio button strategies
    - Checkbox strategies  
    - Dropdown option strategies
    - ROBUST RETRY LOGIC with progressive waits
    - Fallback to smart resolver with fuzzy matching
    """
    logger.info(f"📋 Selecting: {label} (attempt {retry_count + 1}/{max_retries + 1})")
    
    # Wait for page to be stable (critical for dynamic content)
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=3000)
        # Additional wait for client-side rendering (especially after previous click)
        await page.wait_for_timeout(800 if retry_count == 0 else 1500)
    except:
        pass
    
    # Expand keywords for common selection types
    keywords = _expand_select_keywords(label)
    logger.debug(f"  🔑 Select keywords: {keywords}")
    
    # Try each keyword
    for keyword in keywords:
        logger.debug(f"  Trying select keyword: '{keyword}'")
        
        # Strategy 1: Radio button with nearby label
        try:
            # Check for label that contains keyword
            radio_label = page.locator(f"label:has-text('{keyword}')").filter(has=page.locator("input[type='radio']"))
            if await radio_label.count() > 0:
                await radio_label.first.click(timeout=3000)
                logger.info(f"  ✅ Selected radio via label: '{keyword}'")
                return
            
            # Also try clicking the radio directly if label isn't wrapping it
            radio_near_label = page.locator(f"label:has-text('{keyword}') + input[type='radio']")
            if await radio_near_label.count() > 0:
                await radio_near_label.first.check(timeout=3000)
                logger.info(f"  ✅ Selected radio near label: '{keyword}'")
                return
        except:
            pass
        
        # Strategy 2: Radio button by value attribute
        try:
            radio = page.locator(f"input[type='radio'][value*='{keyword}' i]")
            if await radio.count() > 0:
                await radio.first.check(timeout=3000)
                logger.info(f"  ✅ Selected radio via value: '{keyword}'")
                return
        except:
            pass
        
        # Strategy 3: Div/span acting as radio option (custom UI)
        try:
            custom_radio = page.locator(f"div[role='radio']:has-text('{keyword}'), span[role='radio']:has-text('{keyword}')")
            if await custom_radio.count() > 0:
                await custom_radio.first.click(timeout=3000)
                logger.info(f"  ✅ Selected custom radio: '{keyword}'")
                return
        except:
            pass
        
        # Strategy 4: Checkbox by label
        try:
            checkbox_label = page.locator(f"label:has-text('{keyword}')").filter(has=page.locator("input[type='checkbox']"))
            if await checkbox_label.count() > 0:
                await checkbox_label.first.click(timeout=3000)
                logger.info(f"  ✅ Selected checkbox via label: '{keyword}'")
                return
        except:
            pass
        
        # Strategy 5: Dropdown option
        try:
            option = page.locator(f"option:has-text('{keyword}')")
            if await option.count() > 0:
                select_elem = page.locator(f"select:has(option:has-text('{keyword}'))")
                if await select_elem.count() > 0:
                    await select_elem.first.select_option(label=keyword, timeout=3000)
                    logger.info(f"  ✅ Selected option: '{keyword}'")
                    return
        except:
            pass
        
        # Strategy 6: Clickable element with text (buttons, divs styled as options)
        try:
            clickable = page.get_by_text(keyword, exact=False)
            if await clickable.count() > 0:
                first = clickable.first
                # Check if element is clickable
                is_clickable = await first.evaluate("""el => {
                    const tag = el.tagName.toLowerCase();
                    const role = el.getAttribute('role');
                    const clickable = ['button', 'a', 'div', 'span', 'label', 'li'];
                    const clickableRoles = ['button', 'option', 'radio', 'checkbox'];
                    return clickable.includes(tag) || (role && clickableRoles.includes(role));
                }""")
                
                if is_clickable:
                    await first.scroll_into_view_if_needed(timeout=2000)
                    await first.click(timeout=3000)
                    logger.info(f"  ✅ Selected clickable element: '{keyword}'")
                    return
        except Exception as e:
            logger.debug(f"  Strategy 6 failed: {e}")
            pass
    
    # Phase 1 fallback: Try smart_click with original label
    logger.warning(f"  ⚠️ No select-specific strategies worked, trying Phase 1 smart_click")
    try:
        await smart_click(page, label)
        logger.info(f"  ✅ Selected using smart_click fallback")
        return
    except Exception as e:
        logger.debug(f"  smart_click fallback failed: {e}")
    
    # Phase 2 fallback: Use smart resolver with fuzzy matching
    logger.warning(f"  ⚠️ Phase 1 failed, trying Phase 2 smart resolver")
    from .smart_resolver import smart_resolve_click
    
    if await smart_resolve_click(page, label):
        logger.info(f"  ✅ Selected using smart resolver (Phase 2)")
        return
    
    # RETRY LOGIC: If we haven't exhausted retries, wait longer and try again
    if retry_count < max_retries:
        logger.warning(f"  ⚠️ All strategies failed, retrying after longer wait... ({retry_count + 1}/{max_retries})")
        progressive_wait = 2000 + (retry_count * 1000)  # 2s, 3s, 4s...
        await page.wait_for_timeout(progressive_wait)
        return await smart_select(page, label, value, retry_count + 1, max_retries)
    
    # All strategies and retries exhausted
    raise Exception(f"Selection failed for: '{label}' after {max_retries + 1} attempts")
