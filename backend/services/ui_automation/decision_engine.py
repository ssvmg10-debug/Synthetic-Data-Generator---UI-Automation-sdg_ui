"""
Decision Engine – goal matching, not page-type transitions.

Input: GoalObject + PageModel (world) + SessionState
Output: next semantic action

Logic: match goal requirements against current world + state.
No hardcoded transitions. Only goal matching.
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from enum import Enum
import logging

from .page_intelligence.models import PageModel, PageType
from .state_manager import SessionState, LoginMode
from .goal_extractor import GoalObject

logger = logging.getLogger(__name__)


class SemanticAction(str, Enum):
    """Domain-level semantic actions (not low-level click/fill)."""
    ACCEPT_COOKIES = "accept_cookies"
    NAVIGATE_MENU = "navigate_menu"  # Click on menu/navigation items
    SEARCH = "search"
    EXPLORATORY_CLICK = "exploratory_click"  # Recovery: click first visible primary button
    SELECT_PRODUCT = "select_product"
    ADD_TO_CART = "add_to_cart"
    FILL_PINCODE = "fill_pincode"
    SELECT_FREE_DELIVERY = "select_free_delivery"
    PROCEED_TO_CHECKOUT = "proceed_to_checkout"
    CONTINUE_AS_GUEST = "continue_as_guest"
    FILL_ADDRESS = "fill_address"
    CLOSE_MODAL = "close_modal"
    DONE = "done"
    RETRY = "retry"
    UNKNOWN = "unknown"


@dataclass
class NextAction:
    """Next action to execute."""
    action: SemanticAction
    params: Dict[str, Any]
    reason: str = ""


def _button_matches(buttons: List[str], *keywords: str) -> bool:
    """Check if any visible button text matches keywords."""
    txt = " ".join(buttons).lower()
    return any(kw.lower() in txt for kw in keywords)


def _normalize_url(u: Optional[str]) -> str:
    """Normalize URL for comparison (lower, strip trailing slash)."""
    if not u:
        return ""
    return (u.lower() or "").rstrip("/")


def _is_likely_listing_after_search(
    goal: GoalObject,
    world: PageModel,
    state: SessionState,
) -> bool:
    """
    True if we have searched and current page is likely a listing/results page (any site).
    Uses: page_type from extractor, or URL changed from start and not checkout/cart/product.
    No hardcoded URL substrings for specific sites.
    """
    if not state.has_searched() or state.product_selected:
        return False
    url = (world.url or "").lower()
    # Explicit page type from extractor (uses generic URL indicators)
    if world.page_type == PageType.SEARCH_RESULTS or world.page_type == PageType.PRODUCT_LISTING:
        return True
    # Not on checkout/cart/product-detail
    if "checkout" in url or "cart" in url or "/product/" in url or "/p/" in url:
        return False
    # URL changed from start → we navigated (e.g. to results); try select product
    start = _normalize_url(goal.start_url)
    current = _normalize_url(world.url)
    if start and current and current != start:
        return True
    return False


class DecisionEngine:
    """
    Goal-driven decision: given goal + world + state, decide best next action.
    No page_type transitions. Pure goal matching.
    """

    def __init__(self, goal: Optional[GoalObject] = None):
        self.goal = goal or GoalObject()

    def decide(
        self,
        goal: GoalObject,
        world: PageModel,
        state: SessionState,
    ) -> NextAction:
        """
        Decide next action from goal, current UI world, and session state.
        RULE 1: If no search yet and goal has search → always attempt SEARCH (regardless of page_type).
        RULE 2: Decisions depend on goal+state; page_type assists, never controls entirely.
        """
        # Blocking modal / overlay (must clear first)
        if world.modals or state.modal_visible:
            if _button_matches(world.visible_buttons, "Accept", "Close", "OK", "Dismiss"):
                return NextAction(SemanticAction.CLOSE_MODAL, {}, "Modal blocking; close first")
            return NextAction(SemanticAction.ACCEPT_COOKIES, {}, "Cookie/modal blocking; try accept")

        # RULE 1 — Forced first action: if no search performed and goal has search_query, ALWAYS attempt search
        if not state.has_searched() and goal.has_search_goal():
            return NextAction(
                SemanticAction.SEARCH,
                {"query": goal.search_query},
                "Forced search (goal+state: no search yet)",
            )

        # Cookie consent (only if we haven't already tried and Accept visible)
        hist = state.action_history or []
        if ("accept_cookies" not in hist and
            _button_matches(world.visible_buttons, "Accept all", "Accept", "OK", "Agree")):
            return NextAction(SemanticAction.ACCEPT_COOKIES, {}, "First visit: accept cookies")

        # Goal: select product (multiple product cards, none selected yet)
        if len(world.product_cards) > 1 and not state.product_selected:
            return NextAction(
                SemanticAction.SELECT_PRODUCT,
                {"price_max": goal.price_max},
                "Select product under price" if goal.price_max else "Select product",
            )
        # Already searched, likely on listing/results page (page_type or URL changed) → try SELECT_PRODUCT
        # Works for any site; component uses role/locator fallbacks, does not require product_cards
        if goal.complete_purchase and _is_likely_listing_after_search(goal, world, state):
            return NextAction(
                SemanticAction.SELECT_PRODUCT,
                {"price_max": goal.price_max},
                "Select product (post-search listing)",
            )

        # Goal: add to cart (product detail page) vs select product (listing with 1 result)
        if len(world.product_cards) == 1:
            url_lower = (world.url or "").lower()
            if "/product/" in url_lower or world.page_type == PageType.PRODUCT_DETAIL:
                return NextAction(SemanticAction.ADD_TO_CART, {}, "Add to cart")
            # Listing with 1 result: click to go to detail first
            return NextAction(SemanticAction.SELECT_PRODUCT, {"price_max": goal.price_max}, "Select product (1 result)")

        # Goal: checkout (cart visible OR in cart page, complete_purchase, not yet in checkout)
        # IMPORTANT: Only proceed to checkout if we actually have items in cart or are on cart page
        if goal.complete_purchase and not state.checkout_started:
            # Only try checkout if cart has items OR we're on the cart page
            in_cart_page = "cart" in (world.url or "").lower()
            has_cart_items = world.cart and world.cart.is_visible and (world.cart.count or 0) > 0
            
            if in_cart_page or has_cart_items:
                if _button_matches(world.visible_buttons, "Checkout", "Proceed", "Place order", "Buy now"):
                    return NextAction(SemanticAction.PROCEED_TO_CHECKOUT, {}, "Proceed to checkout")
                return NextAction(SemanticAction.PROCEED_TO_CHECKOUT, {}, "Proceed to checkout")

        # Delivery / pincode (in cart or product, delivery section visible)
        if world.delivery_section and not state.delivery_selected:
            if goal.pincode:
                return NextAction(
                    SemanticAction.FILL_PINCODE,
                    {"pincode": goal.pincode},
                    "Fill pincode and check delivery",
                )
            return NextAction(SemanticAction.SELECT_FREE_DELIVERY, {}, "Select free delivery")

        # Guest checkout: only after user has proceeded to checkout (on checkout page)
        # Do not use "Continue as guest" on home/cart — it appears there in footer/menu and would be wrong place
        in_checkout_context = (
            state.checkout_started
            or world.page_type in (PageType.CHECKOUT, PageType.GUEST_CHECKOUT)
            or "checkout" in (world.url or "").lower()
        )
        if (
            goal.wants_guest_checkout()
            and state.login_mode != LoginMode.GUEST
            and in_checkout_context
        ):
            if world.guest_checkout_visible or _button_matches(world.visible_buttons, "Guest", "Continue as guest", "Checkout as guest"):
                return NextAction(SemanticAction.CONTINUE_AS_GUEST, {}, "Continue as guest (after checkout)")

        # Address form (goal wants address filled)
        if goal.wants_address_filled() and not state.address_filled:
            if world.address_form and world.address_form.is_visible:
                return NextAction(
                    SemanticAction.FILL_ADDRESS,
                    {"name": "Test User", "address": "123 Test St", "phone": "9876543210", "city": "Hyderabad"},
                    "Fill billing/shipping address",
                )
            if (world.page_type == PageType.ADDRESS_FORM or
                (world.visible_inputs and "checkout" in (world.url or "").lower())):
                return NextAction(
                    SemanticAction.FILL_ADDRESS,
                    {"name": "Test User", "address": "123 Test St", "phone": "9876543210", "city": "Hyderabad"},
                    "Fill address form",
                )

        # Fallback: page_type assists (RULE 2 - never control entirely)
        result = self._decide_by_page_type_fallback(world, state)
        if result.action != SemanticAction.RETRY:
            return result
        # RULE 3: No rule matched → return RETRY so flow engine invokes recovery_strategy
        return result

    def _decide_by_page_type_fallback(self, world: PageModel, state: SessionState) -> NextAction:
        """Fallback when goal matching yields nothing – page_type assists only."""
        pt = world.page_type
        goal = self.goal

        if pt == PageType.HOME:
            # Likely on listing after search but classified as HOME (e.g. no product_cards extracted) → select product
            if _is_likely_listing_after_search(goal, world, state):
                return NextAction(SemanticAction.SELECT_PRODUCT, {"price_max": goal.price_max}, "Select product (post-search)")
            if goal.has_search_goal():
                return NextAction(SemanticAction.SEARCH, {"query": goal.search_query}, "Search (page_type assist)")
            
            # Try exploratory navigation if we need to buy something but haven't started yet
            if goal.complete_purchase and not state.product_selected:
                # Look for common category/navigation links
                return NextAction(SemanticAction.EXPLORATORY_CLICK, 
                    {"candidates": ["Products", "Shop", "Buy", "Air Solutions", "TVs", "Appliances"]},
                    "Navigate from home to find products")
            
            return NextAction(SemanticAction.ACCEPT_COOKIES, {}, "Try accept cookies")

        if pt == PageType.SEARCH_RESULTS:
            if not state.product_selected:
                return NextAction(SemanticAction.SELECT_PRODUCT, {"price_max": goal.price_max}, "Select product (page_type assist)")

        if pt in (PageType.SEARCH_RESULTS, PageType.PRODUCT_LISTING):
            if not state.product_selected:
                return NextAction(SemanticAction.SELECT_PRODUCT, {"price_max": goal.price_max}, "Select product")
            return NextAction(SemanticAction.SELECT_PRODUCT, {"price_max": goal.price_max}, "Select product (retry)")

        if pt == PageType.PRODUCT_DETAIL:
            return NextAction(SemanticAction.ADD_TO_CART, {}, "Add to cart")

        if pt == PageType.CART:
            return NextAction(SemanticAction.PROCEED_TO_CHECKOUT, {}, "Proceed to checkout")

        if pt == PageType.DELIVERY_CHECK:
            if not state.delivery_selected:
                return NextAction(SemanticAction.FILL_PINCODE, {"pincode": goal.pincode or "500032"}, "Fill pincode")
            return NextAction(SemanticAction.PROCEED_TO_CHECKOUT, {}, "Proceed after delivery")

        if pt in (PageType.CHECKOUT, PageType.GUEST_CHECKOUT):
            if state.login_mode != LoginMode.GUEST and goal.wants_guest_checkout():
                return NextAction(SemanticAction.CONTINUE_AS_GUEST, {}, "Continue as guest")
            return NextAction(SemanticAction.PROCEED_TO_CHECKOUT, {}, "Proceed in checkout")

        if pt == PageType.ADDRESS_FORM:
            return NextAction(
                SemanticAction.FILL_ADDRESS,
                {"name": "Test User", "address": "123 Test St", "phone": "9876543210", "city": "Hyderabad"},
                "Fill address",
            )

        if pt == PageType.LOGIN and goal.wants_guest_checkout():
            return NextAction(SemanticAction.CONTINUE_AS_GUEST, {}, "Try guest")

        return NextAction(SemanticAction.RETRY, {}, f"No rule matched for page_type={pt}")

    def get_recovery_action(
        self,
        goal: GoalObject,
        world: PageModel,
        state: SessionState,
    ) -> NextAction:
        """
        RULE 3: When no rule matches, force minimal exploratory action.
        Never idle. Try: close modal, accept cookies, navigate, search, click primary button.
        """
        # 1. Close modal / accept cookies
        if _button_matches(world.visible_buttons, "Accept", "Accept all", "Close", "OK", "Agree", "Dismiss"):
            return NextAction(SemanticAction.ACCEPT_COOKIES, {}, "Recovery: try accept/close")
        if world.modals:
            return NextAction(SemanticAction.CLOSE_MODAL, {}, "Recovery: close modal")

        # 2. If on home page and need to buy something, try navigating to product categories
        # Be smart: look at visible buttons to guess what categories are available
        if world.page_type == PageType.HOME and goal.complete_purchase and not state.product_selected:
            # Extract category keywords from visible buttons/links
            visible_categories = []
            for btn_text in (world.visible_buttons or [])[:30]:
                # Look for product category keywords in button text
                category_keywords = ["Air", "TV", "Television", "Appliance", "Refrigerator", 
                                    "Washer", "Dryer", "Microwave", "Monitor", "Product",
                                    "Shop", "Buy", "Split", "Window", "AC", "Conditioner"]
                for kw in category_keywords:
                    if kw.lower() in btn_text.lower():
                        visible_categories.append(btn_text)
                        break
            
            # Use visible categories if found, otherwise use common LG categories
            if visible_categories:
                return NextAction(
                    SemanticAction.NAVIGATE_MENU,
                    {"candidates": visible_categories[:10]},
                    f"Recovery: navigate to detected categories: {visible_categories[:3]}"
                )
            else:
                return NextAction(
                    SemanticAction.NAVIGATE_MENU,
                    {"candidates": ["Air Solutions", "Split AC", "Air Conditioners", "TVs", 
                                   "Televisions", "Appliances", "Products", "Shop", "Buy"]},
                    "Recovery: navigate from home to products"
                )

        # 3. Force search if goal has it and we haven't searched
        if goal.has_search_goal() and not state.has_searched():
            return NextAction(SemanticAction.SEARCH, {"query": goal.search_query}, "Recovery: force search")

        # 4. Try search icon / search (may open search bar)
        if _button_matches(world.visible_buttons, "Search", "search"):
            return NextAction(SemanticAction.SEARCH, {"query": goal.search_query or ""}, "Recovery: click search icon")

        # 5. Try checkout/proceed first; guest only after we're on checkout page
        # But DON'T try checkout if we're on home page without products
        on_home_no_products = world.page_type == PageType.HOME and (not world.cart or not world.cart.count)
        if goal.complete_purchase and not state.checkout_started and not on_home_no_products:
            if _button_matches(world.visible_buttons, "Checkout", "Proceed", "Place order"):
                return NextAction(SemanticAction.PROCEED_TO_CHECKOUT, {}, "Recovery: click checkout")
        in_checkout_context = (
            state.checkout_started
            or world.page_type in (PageType.CHECKOUT, PageType.GUEST_CHECKOUT)
            or "checkout" in (world.url or "").lower()
        )
        if (
            goal.wants_guest_checkout()
            and state.login_mode != LoginMode.GUEST
            and in_checkout_context
            and _button_matches(world.visible_buttons, "Guest", "Continue as guest")
        ):
            return NextAction(SemanticAction.CONTINUE_AS_GUEST, {}, "Recovery: click guest (after checkout)")

        # 5. Exploratory: click first visible primary button
        candidates = ["Search", "Buy", "Buy Now", "Know More", "Continue", "Add to cart", "Proceed", "Checkout"]
        return NextAction(
            SemanticAction.EXPLORATORY_CLICK,
            {"candidates": candidates, "visible_buttons": (world.visible_buttons or [])[:15]},
            "Recovery: exploratory click",
        )
