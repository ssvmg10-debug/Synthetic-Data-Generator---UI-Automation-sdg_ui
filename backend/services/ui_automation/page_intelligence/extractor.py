"""
Page model extractor: DOM → PageModel.
Detects page_type and extracts components (product_cards, search_bar, cart) via DOM patterns.
Works for any site: uses URL patterns and structure, no app-specific hardcoding.
"""
import re
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .models import (
    PageModel,
    PageType,
    ProductCard,
    SearchBarComponent,
    CartComponent,
    DeliveryComponent,
    AddressFormComponent,
)

logger = logging.getLogger(__name__)

# URL substrings that commonly indicate a search/results/listing page (any site)
SEARCH_RESULTS_URL_INDICATORS = (
    "search", "q=", "query=", "keyword=", "keywords=",
    "results", "find", "s=", "term=", "query=",
)

def _url_looks_like_search_results(url: str) -> bool:
    """True if URL suggests we're on a search or listing results page (generic)."""
    if not url:
        return False
    u = url.lower()
    return any(ind in u for ind in SEARCH_RESULTS_URL_INDICATORS)


def _url_looks_like_base_or_home(url: str, in_checkout_url: bool) -> bool:
    """True if URL suggests we're on the site root/home (generic: no checkout/cart/product, minimal path)."""
    if not url or in_checkout_url:
        return False
    u = url.lower()
    if "product" in u or "/p/" in u:
        return False
    try:
        parsed = urlparse(u)
        path = (parsed.path or "").rstrip("/")
        segments = [s for s in path.split("/") if s]
        # Base/home: at most one path segment (e.g. /, /in, /us)
        return len(segments) <= 1
    except Exception:
        return False


def _url_looks_like_product_detail(url: str) -> bool:
    """True if URL suggests a product detail page (not cart/checkout/search). Used to prefer ADD_TO_CART before pincode."""
    if not url:
        return False
    u = url.lower()
    if "cart" in u or "checkout" in u or _url_looks_like_search_results(u):
        return False
    if "/product/" in u or "/p/" in u:
        return True
    try:
        parsed = urlparse(u)
        path = (parsed.path or "").rstrip("/")
        segments = [s for s in path.split("/") if s]
        # Deep path (e.g. /in/tv-soundbars/4k-uhd-tvs/43ua82006la/bu) = likely product page
        if len(segments) >= 4:
            return True
        # Path has a segment that looks like a model number (alphanumeric, 8+ chars)
        for seg in segments:
            if len(seg) >= 8 and any(c.isdigit() for c in seg) and any(c.isalpha() for c in seg):
                return True
    except Exception:
        pass
    return False


# JS run in browser to extract product cards (generic e‑commerce patterns)
EXTRACT_PRODUCTS_JS = """
() => {
  const cards = [];
  const selectors = [
    '[class*="product-card"]', '[class*="productCard"]', '[data-product]',
    '.cmp-productlist-item', '.product-item', '[class*="ProductCard"]',
    'article[class*="product"]', '.product-tile', '[itemtype*="Product"]'
  ];
  let roots = [];
  for (const sel of selectors) {
    try {
      document.querySelectorAll(sel).forEach(el => roots.push(el));
    } catch (e) {}
  }
  roots = [...new Set(roots)];
  roots.forEach((el, idx) => {
    let title = '';
    let priceText = '';
    let price = null;
    const titleEl = el.querySelector('[class*="title"], [class*="name"], h2, h3, a[href*="product"]');
    if (titleEl) title = (titleEl.textContent || '').trim().substring(0, 200);
    const priceEl = el.querySelector('[class*="price"], [class*="Price"], [data-price]');
    if (priceEl) {
      priceText = (priceEl.textContent || '').trim();
      const num = priceText.replace(/[^0-9.]/g, '');
      if (num) price = parseFloat(num);
    }
    let buyBtn = el.querySelector('a[href*="product"], .cmp-button, [class*="buy"]');
    if (!buyBtn) {
      el.querySelectorAll('button, a').forEach(b => {
        const t = (b.textContent || '').trim().toLowerCase();
        if (t.includes('buy') || t.includes('know more')) { buyBtn = buyBtn || b; }
      });
    }
    const buySelector = buyBtn ? (buyBtn.id ? '#' + buyBtn.id : '') : '';
    const link = el.querySelector('a[href*="/in/"], a[href*="product"]');
    const linkSelector = link && link.href ? 'a[href="' + link.getAttribute('href') + '"]' : '';
    cards.push({
      index: idx,
      title,
      priceText,
      price,
      buy_button_selector: buySelector,
      link_selector: linkSelector,
      tag: el.tagName + (el.className ? '.' + (el.className + '').split(/\\s+/).slice(0, 2).join('.') : '')
    });
  });
  return cards;
}
"""

EXTRACT_SEARCH_JS = """
() => {
  const inputs = document.querySelectorAll('input[type="search"], input[name="q"], input[name="search"], input[placeholder*="earch"], input[aria-label*="earch"]');
  for (const el of inputs) {
    if (el.offsetParent !== null) {
      const id = el.id ? '#' + el.id : '';
      const sel = id || 'input[type="search"]';
      const submit = document.querySelector('button[type="submit"], [aria-label*="Search"], button:has(svg)');
      return { input_selector: sel || 'input[type=search]', submit_selector: submit ? 'button[type=submit]' : '', is_visible: true };
    }
  }
  return null;
}
"""

EXTRACT_CART_JS = """
() => {
  const cart = document.querySelector('a[href*="cart"], [aria-label*="art"], .cart-icon');
  if (!cart) {
    const links = document.querySelectorAll('a');
    for (const a of links) { if ((a.textContent || '').toLowerCase().includes('cart')) return { link_selector: 'a[href*="cart"]', count: null, is_visible: true }; }
    return null;
  }
  const countEl = document.querySelector('[class*="cart-count"], .minicart-count, [data-cart-count]');
  let count = null;
  if (countEl) { const t = (countEl.textContent || '').replace(/\\D/g, ''); if (t) count = parseInt(t, 10); }
  return { link_selector: 'a[href*="cart"]', count, is_visible: cart.offsetParent !== null };
}
"""

# DOM fingerprinting: detect delivery section, address form, login, guest checkout
# STRICT: address_form requires checkout URL + multiple visible address fields (avoids homepage false positive)
EXTRACT_DOM_FINGERPRINT_JS = """
() => {
  const url = (window.location.href || '').toLowerCase();
  const inCheckoutContext = /checkout|cart/.test(url);
  const body = (document.body && document.body.innerText) ? document.body.innerText.toLowerCase() : '';
  const html = document.documentElement ? document.documentElement.outerHTML.toLowerCase() : '';
  const txt = body + ' ' + html;
  const hasDelivery = /delivery|pincode|postal|zip|availability|check.*pincode/i.test(txt);
  const hasFreeDelivery = /free delivery|free shipping/i.test(txt);
  const hasLoginForm = /login|sign in|log in/i.test(txt) && document.querySelector('input[type="password"], input[name*="password"]');
  const hasGuestCheckout = /guest|continue as guest|checkout as guest/i.test(txt);
  const pincodeInput = document.querySelector('input[placeholder*="incode"], input[name*="zip"], input[name*="pincode"], input[id*="pincode"]');
  const checkBtn = Array.from(document.querySelectorAll('button, a, input[type="submit"]')).find(el => /check|verify|go/i.test((el.textContent || '').trim()));

  let addressFormVisible = false;
  if (inCheckoutContext) {
    const addressFields = [
      document.querySelector('input[name*="address"], input[placeholder*="address"], input[id*="address"]'),
      document.querySelector('input[name*="name"], input[placeholder*="name"], input[id*="name"]'),
      document.querySelector('input[name*="city"], input[placeholder*="city"], input[id*="city"]'),
      document.querySelector('input[name*="zip"], input[name*="pincode"], input[placeholder*="incode"]'),
      document.querySelector('input[name*="phone"], input[placeholder*="phone"], input[id*="phone"]')
    ];
    let visibleCount = 0;
    for (const el of addressFields) {
      if (el && el.offsetParent !== null) visibleCount++;
    }
    addressFormVisible = visibleCount >= 2 && /billing|shipping|address|delivery/.test(txt);
  }

  // Rich world model: visible buttons, inputs, modals
  const visibleButtons = [];
  document.querySelectorAll('button, [role="button"], input[type="submit"], a.btn').forEach(el => {
    if (el.offsetParent !== null) {
      const t = (el.textContent || el.value || el.getAttribute('aria-label') || '').trim().substring(0, 80);
      if (t) visibleButtons.push(t);
    }
  });
  const visibleInputs = [];
  document.querySelectorAll('input:not([type="hidden"]), textarea').forEach(el => {
    if (el.offsetParent !== null) {
      visibleInputs.push({
        type: el.type || 'text',
        placeholder: (el.placeholder || '').substring(0, 50),
        name: (el.name || '').substring(0, 50)
      });
    }
  });
  const modalEl = document.querySelector('[role="dialog"], .modal, [class*="modal"]');
  const modals = !!modalEl && modalEl.offsetParent !== null;

  return {
    delivery_section: hasDelivery,
    free_delivery_visible: hasFreeDelivery,
    address_form_visible: addressFormVisible,
    in_checkout_context: inCheckoutContext,
    login_form_visible: !!hasLoginForm,
    guest_checkout_visible: hasGuestCheckout,
    pincode_input_selector: pincodeInput ? (pincodeInput.id ? '#' + pincodeInput.id : 'input[placeholder*="incode"]') : '',
    check_button_text: checkBtn ? (checkBtn.textContent || '').trim().substring(0, 30) : '',
    visible_buttons: visibleButtons.slice(0, 30),
    visible_inputs: visibleInputs.slice(0, 20),
    modals: modals
  };
}
"""


def _parse_price_from_text(text: str) -> Optional[float]:
    if not text:
        return None
    cleaned = re.sub(r"[^\d.]", "", text)
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _detect_page_type(
    model: PageModel,
    fingerprint: Optional[Dict[str, Any]] = None,
) -> PageType:
    """
    DOM fingerprinting: infer page_type from components present.
    Order matters: most specific (address form) before generic (home).
    CRITICAL: Never classify homepage as checkout/guest_checkout – require URL context (checkout/cart)
    so that flow can start from HOME and progress (accept cookies → search → …).
    """
    url_lower = (model.url or "").lower()
    fp = fingerprint or {}
    product_count = len(model.product_cards)
    in_checkout_url = "checkout" in url_lower or "cart" in url_lower

    # Homepage / base URL (generic: minimal path, no checkout/cart/product) → return HOME first
    # So flow can accept cookies and search; avoids misclassifying home as checkout due to footer text
    if _url_looks_like_base_or_home(url_lower, in_checkout_url):
        return PageType.HOME

    # Address form (billing/shipping) - STRICT: requires checkout/cart URL + multiple signals
    if (fp.get("address_form_visible") or (model.address_form and model.address_form.is_visible)) and in_checkout_url:
        return PageType.ADDRESS_FORM

    # Login vs guest checkout choice – ONLY when we are actually in checkout/cart context
    # (otherwise homepage with footer "guest" gets misclassified and flow never starts)
    if fp.get("login_form_visible") and not fp.get("guest_checkout_visible"):
        if "login" in url_lower or "signin" in url_lower:
            return PageType.LOGIN
    if fp.get("guest_checkout_visible") and in_checkout_url:
        return PageType.GUEST_CHECKOUT

    # Delivery section (pincode check, free delivery) - require cart/product context
    in_cart_or_product = "cart" in url_lower or "checkout" in url_lower or product_count > 0 or "/product/" in url_lower
    if (fp.get("delivery_section") or model.delivery_section) and in_cart_or_product:
        return PageType.DELIVERY_CHECK

    # Checkout / cart
    if "checkout" in url_lower or model.checkout_visible:
        return PageType.CHECKOUT
    if "cart" in url_lower and (model.cart or product_count == 0):
        return PageType.CART

    # Product detail: single product view (URL or structure)
    if "/product/" in url_lower or "/p/" in url_lower:
        return PageType.PRODUCT_DETAIL
    if product_count == 1 and model.product_cards and model.product_cards[0].buy_button_selector:
        return PageType.PRODUCT_DETAIL

    # Search results / product listing (generic URL indicators)
    url_is_search_results = _url_looks_like_search_results(model.url or "")
    if product_count > 1 or (product_count > 0 and url_is_search_results):
        return PageType.SEARCH_RESULTS if url_is_search_results else PageType.PRODUCT_LISTING
    if product_count > 0:
        return PageType.PRODUCT_LISTING
    # URL indicates search/results page even if product_cards weren't extracted (any site)
    if url_is_search_results:
        return PageType.SEARCH_RESULTS

    # Home
    if model.search_bar and model.search_bar.is_visible:
        return PageType.HOME
    return PageType.HOME


def _build_product_cards(rows: List[Dict[str, Any]]) -> List[ProductCard]:
    cards = []
    for i, r in enumerate(rows or []):
        if not isinstance(r, dict):
            continue
        price = r.get("price")
        if price is None and r.get("priceText"):
            price = _parse_price_from_text(str(r["priceText"]))
        cards.append(
            ProductCard(
                title=(r.get("title") or "").strip()[:300],
                price=price,
                price_text=(r.get("priceText") or "").strip()[:50],
                buy_button_selector=(r.get("buy_button_selector") or "").strip(),
                link_selector=(r.get("link_selector") or "").strip(),
                index=r.get("index", i),
                raw=r,
            )
        )
    return cards


def extract_page_model_sync(page: Any) -> PageModel:
    """
    Extract PageModel from current page using sync Playwright page.
    Use from sync execution context (e.g. thread on Windows).
    """
    model = PageModel(url=page.url or "")
    try:
        # Product cards
        try:
            raw_cards = page.evaluate(EXTRACT_PRODUCTS_JS)
            model.product_cards = _build_product_cards(raw_cards if isinstance(raw_cards, list) else [])
        except Exception as e:
            logger.debug("Extract product cards (sync) failed: %s", e)

        # Search bar
        try:
            search_raw = page.evaluate(EXTRACT_SEARCH_JS)
            if search_raw and isinstance(search_raw, dict):
                model.search_bar = SearchBarComponent(
                    input_selector=search_raw.get("input_selector", "input[type='search']"),
                    submit_selector=search_raw.get("submit_selector", ""),
                    is_visible=bool(search_raw.get("is_visible")),
                )
        except Exception as e:
            logger.debug("Extract search bar (sync) failed: %s", e)

        # Cart
        try:
            cart_raw = page.evaluate(EXTRACT_CART_JS)
            if cart_raw and isinstance(cart_raw, dict):
                model.cart = CartComponent(
                    link_selector=cart_raw.get("link_selector", "a[href*='cart']"),
                    count=cart_raw.get("count"),
                    is_visible=bool(cart_raw.get("is_visible")),
                )
        except Exception as e:
            logger.debug("Extract cart (sync) failed: %s", e)

        fingerprint = None
        try:
            fingerprint = page.evaluate(EXTRACT_DOM_FINGERPRINT_JS)
            if fingerprint:
                model.delivery_section = DeliveryComponent(
                    pincode_input_selector=fingerprint.get("pincode_input_selector", ""),
                    delivery_options_visible=bool(fingerprint.get("delivery_section")),
                    free_delivery_visible=bool(fingerprint.get("free_delivery_visible")),
                ) if fingerprint.get("delivery_section") else None
                model.address_form = AddressFormComponent(is_visible=bool(fingerprint.get("address_form_visible"))) if fingerprint.get("address_form_visible") else None
                model.login_form_visible = bool(fingerprint.get("login_form_visible"))
                model.guest_checkout_visible = bool(fingerprint.get("guest_checkout_visible"))
                model.visible_buttons = fingerprint.get("visible_buttons") or []
                model.visible_inputs = fingerprint.get("visible_inputs") or []
                model.modals = bool(fingerprint.get("modals"))
        except Exception as e:
            logger.debug("DOM fingerprint (sync) failed: %s", e)

        if model.cart:
            model.cart_count = model.cart.count or 0
        model.has_search_results = len(model.product_cards) > 0 and ("search" in (model.url or "").lower() or "q=" in (model.url or "").lower())
        model.page_type = _detect_page_type(model, fingerprint)
    except Exception as e:
        logger.warning("Page model extraction failed: %s", e)
    return model


async def extract_page_model_async(page: Any) -> PageModel:
    """
    Extract PageModel from current page using async Playwright page.
    """
    model = PageModel(url=page.url or "")
    try:
        try:
            raw_cards = await page.evaluate(EXTRACT_PRODUCTS_JS)
            model.product_cards = _build_product_cards(raw_cards if isinstance(raw_cards, list) else [])
        except Exception as e:
            logger.debug("Extract product cards (async) failed: %s", e)

        try:
            search_raw = await page.evaluate(EXTRACT_SEARCH_JS)
            if search_raw and isinstance(search_raw, dict):
                model.search_bar = SearchBarComponent(
                    input_selector=search_raw.get("input_selector", "input[type='search']"),
                    submit_selector=search_raw.get("submit_selector", ""),
                    is_visible=bool(search_raw.get("is_visible")),
                )
        except Exception as e:
            logger.debug("Extract search bar (async) failed: %s", e)

        try:
            cart_raw = await page.evaluate(EXTRACT_CART_JS)
            if cart_raw and isinstance(cart_raw, dict):
                model.cart = CartComponent(
                    link_selector=cart_raw.get("link_selector", "a[href*='cart']"),
                    count=cart_raw.get("count"),
                    is_visible=bool(cart_raw.get("is_visible")),
                )
        except Exception as e:
            logger.debug("Extract cart (async) failed: %s", e)

        fingerprint = None
        try:
            fingerprint = await page.evaluate(EXTRACT_DOM_FINGERPRINT_JS)
            if fingerprint:
                model.delivery_section = DeliveryComponent(
                    pincode_input_selector=fingerprint.get("pincode_input_selector", ""),
                    delivery_options_visible=bool(fingerprint.get("delivery_section")),
                    free_delivery_visible=bool(fingerprint.get("free_delivery_visible")),
                ) if fingerprint.get("delivery_section") else None
                model.address_form = AddressFormComponent(is_visible=bool(fingerprint.get("address_form_visible"))) if fingerprint.get("address_form_visible") else None
                model.login_form_visible = bool(fingerprint.get("login_form_visible"))
                model.guest_checkout_visible = bool(fingerprint.get("guest_checkout_visible"))
                model.visible_buttons = fingerprint.get("visible_buttons") or []
                model.visible_inputs = fingerprint.get("visible_inputs") or []
                model.modals = bool(fingerprint.get("modals"))
        except Exception as e:
            logger.debug("DOM fingerprint (async) failed: %s", e)

        if model.cart:
            model.cart_count = model.cart.count or 0
        model.has_search_results = len(model.product_cards) > 0 and ("search" in (model.url or "").lower() or "q=" in (model.url or "").lower())
        model.page_type = _detect_page_type(model, fingerprint)
    except Exception as e:
        logger.warning("Page model extraction failed: %s", e)
    return model


def extract_page_model(page: Any, *, sync: bool = False) -> PageModel:
    """
    Extract PageModel from current page.
    Use sync=True when calling from sync Playwright context (e.g. thread).
    """
    if sync:
        return extract_page_model_sync(page)
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop:
        # Called from async context: must use async version; caller should use extract_page_model_async
        raise RuntimeError("Use extract_page_model_async(page) when in async context")
    return extract_page_model_sync(page)
