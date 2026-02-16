"""
Page model types for component-aware execution.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class PageType(str, Enum):
    """DOM fingerprinting: detect page by components present."""
    UNKNOWN = "unknown"
    HOME = "home"
    SEARCH_RESULTS = "search_results"
    PRODUCT_LISTING = "product_listing"
    PRODUCT_DETAIL = "product_detail"
    CART = "cart"
    CHECKOUT = "checkout"
    DELIVERY_CHECK = "delivery_check"      # Pincode/delivery section visible
    LOGIN = "login"
    GUEST_CHECKOUT = "guest_checkout"
    ADDRESS_FORM = "address_form"           # Billing/shipping form visible


@dataclass
class ProductCard:
    """Single product card on listing/search page."""
    title: str = ""
    price: Optional[float] = None
    price_text: str = ""
    buy_button_selector: str = ""
    link_selector: str = ""
    index: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchBarComponent:
    """Search bar / search input area."""
    input_selector: str = ""
    submit_selector: str = ""
    is_visible: bool = False


@dataclass
class CartComponent:
    """Cart icon / cart summary."""
    link_selector: str = ""
    count_selector: str = ""
    count: Optional[int] = None
    is_visible: bool = False


@dataclass
class DeliveryComponent:
    """Pincode/delivery section."""
    pincode_input_selector: str = ""
    check_button_selector: str = ""
    delivery_options_visible: bool = False
    free_delivery_visible: bool = False


@dataclass
class AddressFormComponent:
    """Billing/shipping address form."""
    name_input_selector: str = ""
    address_input_selector: str = ""
    phone_input_selector: str = ""
    city_input_selector: str = ""
    submit_selector: str = ""
    is_visible: bool = False


@dataclass
class PageModel:
    """
    UI world model – structural grouping of what's on the page.
    Used for goal matching; not rule-based page_type transitions.
    """
    page_type: PageType = PageType.UNKNOWN
    url: str = ""
    product_cards: List[ProductCard] = field(default_factory=list)
    search_bar: Optional[SearchBarComponent] = None
    cart: Optional[CartComponent] = None
    checkout_visible: bool = False
    delivery_section: Optional[DeliveryComponent] = None
    address_form: Optional[AddressFormComponent] = None
    login_form_visible: bool = False
    guest_checkout_visible: bool = False
    error_message: str = ""
    raw_components: Dict[str, Any] = field(default_factory=dict)

    # Rich world model for goal matching (extracted by structural grouping)
    visible_buttons: List[str] = field(default_factory=list)  # button text/labels
    visible_inputs: List[Dict[str, str]] = field(default_factory=list)  # [{type, placeholder, name}]
    modals: bool = False
    cart_count: int = 0
    has_search_results: bool = False  # product_cards present after search

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_type": self.page_type.value,
            "url": self.url,
            "product_cards": [
                {
                    "title": p.title,
                    "price": p.price,
                    "price_text": p.price_text,
                    "buy_button_selector": p.buy_button_selector,
                    "link_selector": p.link_selector,
                    "index": p.index,
                }
                for p in self.product_cards
            ],
            "search_bar": {
                "input_selector": self.search_bar.input_selector,
                "submit_selector": self.search_bar.submit_selector,
                "is_visible": self.search_bar.is_visible,
            } if self.search_bar else None,
            "cart": {
                "link_selector": self.cart.link_selector,
                "count": self.cart.count,
                "is_visible": self.cart.is_visible,
            } if self.cart else None,
            "checkout_visible": self.checkout_visible,
            "delivery_section": bool(self.delivery_section),
            "address_form": bool(self.address_form),
            "login_form_visible": self.login_form_visible,
            "guest_checkout_visible": self.guest_checkout_visible,
            "error_message": self.error_message,
        }
