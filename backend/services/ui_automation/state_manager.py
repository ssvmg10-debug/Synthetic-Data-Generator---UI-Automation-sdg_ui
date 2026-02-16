"""
State Manager – full session memory for flow-based execution.

Tracks: current_page_type, cart_items, selected_product, delivery_selected,
checkout_stage, login_mode, modal_visibility, last_action, action_history.
Enables: detect wrong transitions, retry intelligently, skip satisfied steps.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

from .page_intelligence.models import PageType


class CheckoutStage(str, Enum):
    NONE = "none"
    CART = "cart"
    DELIVERY = "delivery"
    SHIPPING = "shipping"
    PAYMENT = "payment"
    REVIEW = "review"
    GUEST_ENTRY = "guest_entry"
    ADDRESS = "address"


class LoginMode(str, Enum):
    UNKNOWN = "unknown"
    GUEST = "guest"
    LOGGED_IN = "logged_in"


@dataclass
class CartItem:
    """Single item in cart (simplified)."""
    product_id: str = ""
    title: str = ""
    price: Optional[float] = None
    quantity: int = 1


@dataclass
class SelectedProduct:
    """Product selected for purchase."""
    title: str = ""
    price: Optional[float] = None
    index: int = 0


@dataclass
class SessionState:
    """
    Full session memory for flow-based execution.
    Updated after each transition; read by Decision Engine and Flow Engine.
    """
    current_url: str = ""
    page_type: PageType = PageType.UNKNOWN
    cart_count: int = 0
    cart_items: List[CartItem] = field(default_factory=list)
    selected_product: Optional[SelectedProduct] = None
    delivery_selected: bool = False
    checkout_stage: CheckoutStage = CheckoutStage.NONE
    login_mode: LoginMode = LoginMode.UNKNOWN
    is_logged_in: bool = False
    modal_visible: bool = False
    last_action: str = ""
    last_action_ok: bool = True
    action_history: List[str] = field(default_factory=list)
    last_page_model: Optional[Dict[str, Any]] = None
    goal_reached: bool = False
    product_selected: bool = False
    checkout_started: bool = False  # True after proceed_to_checkout or in checkout flow
    address_filled: bool = False
    search_succeeded: bool = False  # True after SEARCH action succeeded (allows retry if failed)

    def has_searched(self) -> bool:
        """True only when search was successful; failed attempts allow retry."""
        return self.search_succeeded

    def update_after_navigate(self, url: str, page_type: PageType) -> None:
        self.current_url = url or self.current_url
        self.page_type = page_type
        self.last_action = "navigate"
        self.last_action_ok = True
        self.action_history.append("navigate")

    def update_after_action(self, action: str, success: bool, **kwargs: Any) -> None:
        self.last_action = action
        self.last_action_ok = success
        self.action_history.append(action)
        if "url" in kwargs:
            self.current_url = kwargs["url"]
        if "page_type" in kwargs:
            self.page_type = kwargs["page_type"]
        if "cart_count" in kwargs:
            self.cart_count = kwargs["cart_count"]
        if "checkout_stage" in kwargs:
            self.checkout_stage = kwargs["checkout_stage"]
        if "modal_visible" in kwargs:
            self.modal_visible = kwargs["modal_visible"]
        if "delivery_selected" in kwargs:
            self.delivery_selected = kwargs["delivery_selected"]
        if "selected_product" in kwargs:
            self.selected_product = kwargs["selected_product"]
        if "login_mode" in kwargs:
            self.login_mode = kwargs["login_mode"]
            self.is_logged_in = kwargs["login_mode"] == LoginMode.LOGGED_IN
        if "goal_reached" in kwargs:
            self.goal_reached = kwargs["goal_reached"]
        if "product_selected" in kwargs:
            self.product_selected = kwargs["product_selected"]
        if "checkout_started" in kwargs:
            self.checkout_started = kwargs["checkout_started"]

    def mark_goal_reached(self) -> None:
        self.goal_reached = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_url": self.current_url,
            "page_type": self.page_type.value if isinstance(self.page_type, PageType) else str(self.page_type),
            "cart_count": self.cart_count,
            "selected_product": self.selected_product.__dict__ if self.selected_product else None,
            "delivery_selected": self.delivery_selected,
            "checkout_stage": self.checkout_stage.value,
            "login_mode": self.login_mode.value,
            "is_logged_in": self.is_logged_in,
            "modal_visible": self.modal_visible,
            "last_action": self.last_action,
            "last_action_ok": self.last_action_ok,
            "goal_reached": self.goal_reached,
        }
