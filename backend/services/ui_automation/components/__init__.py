"""
Component Abstraction Layer – domain logic over selectors.

Instead of: click(selector)
Use: cart_page.proceed_to_checkout()

If UI changes internally → only component updated; flow logic stays stable.
"""
from .base import PageComponent
from .home import HomePageComponent
from .navigation import NavigationComponent
from .search_results import SearchResultsComponent
from .product_page import ProductPageComponent
from .cart_page import CartPageComponent
from .checkout_page import CheckoutPageComponent

__all__ = [
    "PageComponent",
    "HomePageComponent",
    "NavigationComponent",
    "SearchResultsComponent",
    "ProductPageComponent",
    "CartPageComponent",
    "CheckoutPageComponent",
]
