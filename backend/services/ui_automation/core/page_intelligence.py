"""
Page Intelligence Engine - Detects page types via DOM fingerprinting.

This is Layer 1 of the state-driven automation architecture.
Provides context awareness for all actions.
"""
import logging
from enum import Enum
from typing import Dict, Any, Optional, List
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class PageType(Enum):
    """Known page types for e-commerce sites."""
    HOME = "HOME"
    CATEGORY = "CATEGORY"
    PRODUCT_LISTING = "PRODUCT_LISTING"
    PRODUCT_DETAIL = "PRODUCT_DETAIL"
    CART = "CART"
    CHECKOUT = "CHECKOUT"
    LOGIN = "LOGIN"
    MODAL = "MODAL"
    SEARCH_RESULTS = "SEARCH_RESULTS"
    UNKNOWN = "UNKNOWN"


class PageState:
    """Represents the current page state."""
    
    def __init__(
        self,
        page_type: PageType,
        url: str,
        snapshot: Dict[str, Any],
        confidence: float = 1.0
    ):
        self.page_type = page_type
        self.url = url
        self.snapshot = snapshot
        self.confidence = confidence
        self.timestamp = None
    
    def __repr__(self):
        return f"PageState(type={self.page_type.value}, confidence={self.confidence:.2f}, url={self.url[:50]}...)"


class PageIntelligenceEngine:
    """
    Detects page type using DOM fingerprinting.
    
    This engine provides context awareness by understanding
    what type of page we're on before executing any action.
    """
    
    def __init__(self, page: Page):
        self.page = page
        self.current_state: Optional[PageState] = None
        self.state_history: List[PageState] = []
    
    async def detect_page_type(self) -> PageState:
        """
        Detect current page type using DOM fingerprinting.
        
        Returns:
            PageState with detected type and confidence
        """
        logger.info("🔍 Detecting page type...")
        
        url = self.page.url
        
        # Collect DOM signals
        signals = await self._collect_dom_signals()
        
        # Run detection rules
        page_type, confidence = await self._run_detection_rules(signals)
        
        # Create state snapshot
        snapshot = {
            "signals": signals,
            "url": url,
            "title": await self.page.title()
        }
        
        state = PageState(page_type, url, snapshot, confidence)
        self.current_state = state
        self.state_history.append(state)
        
        logger.info(f"✅ Detected: {state}")
        return state
    
    async def _collect_dom_signals(self) -> Dict[str, Any]:
        """
        Collect DOM signals for page type detection.
        
        Returns:
            Dictionary of signals and their presence/count
        """
        signals = {}
        
        try:
            # Product detail signals
            signals["has_add_to_cart"] = await self.page.locator(
                'button:has-text("Add to Cart"), button:has-text("Add to Basket"), button:has-text("Buy Now")'
            ).count() > 0
            
            signals["has_price"] = await self.page.locator(
                '[class*="price"], [data-price], .product-price, [itemprop="price"]'
            ).count() > 0
            
            signals["has_product_title"] = await self.page.locator(
                'h1:visible, [class*="product-title"], [class*="product-name"], [itemprop="name"]'
            ).first.count() > 0
            
            signals["has_product_description"] = await self.page.locator(
                '[class*="description"], [class*="details"], [itemprop="description"]'
            ).count() > 0
            
            signals["has_product_images"] = await self.page.locator(
                '[class*="product-image"], [class*="gallery"], img[class*="product"]'
            ).count() > 0
            
            # Listing page signals
            signals["product_card_count"] = await self.page.locator(
                '[class*="product-card"], [class*="product-item"], [data-product-id], .product, article[class*="product"]'
            ).count()
            
            signals["has_filters"] = await self.page.locator(
                '[class*="filter"], [class*="facet"], aside:has(input[type="checkbox"])'
            ).count() > 0
            
            signals["has_sorting"] = await self.page.locator(
                'select:has-text("Sort"), [class*="sort"]'
            ).count() > 0
            
            signals["has_pagination"] = await self.page.locator(
                '[class*="pagination"], .pager, nav[aria-label*="pagination"]'
            ).count() > 0
            
            # Cart signals
            signals["has_cart_items"] = await self.page.locator(
                '[class*="cart-item"], [class*="cart-product"], .cart-row, [data-cart-item]'
            ).count() > 0
            
            signals["has_cart_total"] = await self.page.locator(
                '[class*="cart-total"], [class*="order-total"], .total'
            ).count() > 0
            
            signals["has_checkout_button"] = await self.page.locator(
                'button:has-text("Checkout"), a:has-text("Checkout"), button:has-text("Proceed")'
            ).count() > 0
            
            signals["has_quantity_selector"] = await self.page.locator(
                'input[type="number"][class*="quantity"], select[class*="quantity"]'
            ).count() > 0
            
            # Checkout signals
            signals["has_billing_form"] = await self.page.locator(
                'form:has-text("Billing"), [class*="billing-address"], input[name*="billing"]'
            ).count() > 0
            
            signals["has_shipping_form"] = await self.page.locator(
                'form:has-text("Shipping"), [class*="shipping-address"], input[name*="shipping"]'
            ).count() > 0
            
            signals["has_payment_method"] = await self.page.locator(
                '[class*="payment"], input[type="radio"][name*="payment"], [name*="cardNumber"]'
            ).count() > 0
            
            signals["has_place_order"] = await self.page.locator(
                'button:has-text("Place Order"), button:has-text("Complete"), button:has-text("Pay Now")'
            ).count() > 0
            
            # Login signals
            signals["has_login_form"] = await self.page.locator(
                'form:has(input[type="password"]), input[name="email"][type="email"] + input[type="password"]'
            ).count() > 0
            
            signals["has_email_input"] = await self.page.locator(
                'input[type="email"], input[name*="email"], input[name="username"]'
            ).count() > 0
            
            signals["has_password_input"] = await self.page.locator(
                'input[type="password"]'
            ).count() > 0
            
            # Modal signals
            signals["has_modal"] = await self.page.locator(
                '[role="dialog"]:visible, .modal:visible, [class*="modal"]:visible'
            ).count() > 0
            
            signals["has_overlay"] = await self.page.locator(
                '[class*="overlay"]:visible, [class*="backdrop"]:visible'
            ).count() > 0
            
            # Search results signals
            signals["has_search_results"] = await self.page.locator(
                '[class*="search-results"], [data-search-results]'
            ).count() > 0
            
            signals["has_search_query_display"] = await self.page.locator(
                ':text-matches("results for", "i"), :text-matches("search results", "i")'
            ).count() > 0
            
            # Category signals
            signals["has_category_navigation"] = await self.page.locator(
                'nav[class*="category"], [class*="category-nav"], aside:has(a[class*="category"])'
            ).count() > 0
            
            signals["has_subcategories"] = await self.page.locator(
                '[class*="subcategory"], [class*="sub-category"]'
            ).count() > 0
            
            # Home page signals
            signals["has_hero_banner"] = await self.page.locator(
                '[class*="hero"], [class*="banner"], [class*="carousel"]:visible'
            ).count() > 0
            
            signals["has_featured_products"] = await self.page.locator(
                '[class*="featured"], [class*="trending"], [class*="popular"]'
            ).count() > 0
            
        except Exception as e:
            logger.warning(f"Error collecting signals: {e}")
        
        return signals
    
    async def _run_detection_rules(self, signals: Dict[str, Any]) -> tuple[PageType, float]:
        """
        Run detection rules to determine page type.
        
        Args:
            signals: DOM signals collected
        
        Returns:
            Tuple of (PageType, confidence_score)
        """
        # Modal check (highest priority)
        if signals.get("has_modal", False):
            return PageType.MODAL, 0.95
        
        # Checkout page (high specificity)
        checkout_score = 0
        if signals.get("has_billing_form", False):
            checkout_score += 0.4
        if signals.get("has_shipping_form", False):
            checkout_score += 0.3
        if signals.get("has_payment_method", False):
            checkout_score += 0.2
        if signals.get("has_place_order", False):
            checkout_score += 0.1
        
        if checkout_score >= 0.5:
            return PageType.CHECKOUT, checkout_score
        
        # Login page
        login_score = 0
        if signals.get("has_login_form", False):
            login_score += 0.5
        if signals.get("has_email_input", False) and signals.get("has_password_input", False):
            login_score += 0.5
        
        if login_score >= 0.8:
            return PageType.LOGIN, login_score
        
        # Cart page
        cart_score = 0
        if signals.get("has_cart_items", False):
            cart_score += 0.3
        if signals.get("has_cart_total", False):
            cart_score += 0.3
        if signals.get("has_checkout_button", False):
            cart_score += 0.2
        if signals.get("has_quantity_selector", False):
            cart_score += 0.2
        
        if cart_score >= 0.6:
            return PageType.CART, cart_score
        
        # Product detail page
        product_detail_score = 0
        if signals.get("has_add_to_cart", False):
            product_detail_score += 0.3
        if signals.get("has_price", False):
            product_detail_score += 0.2
        if signals.get("has_product_title", False):
            product_detail_score += 0.2
        if signals.get("has_product_description", False):
            product_detail_score += 0.15
        if signals.get("has_product_images", False):
            product_detail_score += 0.15
        
        # Disambiguate from listing page
        if product_detail_score >= 0.7 and signals.get("product_card_count", 0) < 3:
            return PageType.PRODUCT_DETAIL, product_detail_score
        
        # Search results page
        if signals.get("has_search_results", False) or signals.get("has_search_query_display", False):
            if signals.get("product_card_count", 0) > 0:
                return PageType.SEARCH_RESULTS, 0.9
        
        # Product listing page
        listing_score = 0
        product_count = signals.get("product_card_count", 0)
        if product_count >= 3:
            listing_score += min(0.4, product_count * 0.05)
        if signals.get("has_filters", False):
            listing_score += 0.25
        if signals.get("has_sorting", False):
            listing_score += 0.2
        if signals.get("has_pagination", False):
            listing_score += 0.15
        
        if listing_score >= 0.5:
            return PageType.PRODUCT_LISTING, listing_score
        
        # Category page (similar to listing but with category navigation)
        if signals.get("has_category_navigation", False) or signals.get("has_subcategories", False):
            if product_count > 0:
                return PageType.CATEGORY, 0.75
        
        # Home page (default for main page with hero/featured)
        if signals.get("has_hero_banner", False) or signals.get("has_featured_products", False):
            if product_count > 0 or signals.get("has_category_navigation", False):
                return PageType.HOME, 0.7
        
        # Unknown
        return PageType.UNKNOWN, 0.0
    
    async def validate_state_transition(
        self,
        expected_type: Optional[PageType] = None,
        timeout: int = 5000
    ) -> bool:
        """
        Validate that state has transitioned correctly after an action.
        
        Args:
            expected_type: Expected page type after transition
            timeout: Max wait time
        
        Returns:
            True if transition valid
        """
        logger.info("🔄 Validating state transition...")
        
        # Wait for any potential navigation/modal/changes
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=timeout)
        except:
            pass
        
        # Re-detect page type
        new_state = await self.detect_page_type()
        
        if expected_type:
            if new_state.page_type == expected_type:
                logger.info(f"✅ State transition valid: {expected_type.value}")
                return True
            else:
                logger.warning(
                    f"⚠️ State mismatch: expected {expected_type.value}, "
                    f"got {new_state.page_type.value}"
                )
                return False
        
        # Check if state changed at all
        if len(self.state_history) >= 2:
            prev_state = self.state_history[-2]
            if new_state.url != prev_state.url or new_state.page_type != prev_state.page_type:
                logger.info("✅ State changed")
                return True
        
        logger.info("ℹ️ State unchanged (may be OK)")
        return True
    
    def get_current_context(self) -> Dict[str, Any]:
        """
        Get current page context for decision making.
        
        Returns:
            Context dictionary with page type, url, signals
        """
        if not self.current_state:
            return {"page_type": "UNKNOWN", "signals": {}}
        
        return {
            "page_type": self.current_state.page_type.value,
            "url": self.current_state.url,
            "signals": self.current_state.snapshot.get("signals", {}),
            "confidence": self.current_state.confidence
        }
