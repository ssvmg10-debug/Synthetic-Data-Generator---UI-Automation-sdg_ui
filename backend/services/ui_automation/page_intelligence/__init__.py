"""
Page Intelligence Engine – state-aware, component-aware execution.

Provides:
- PageModel: structured page type + components (product_cards, search_bar, cart, etc.)
- extract_page_model_sync(page) / extract_page_model_async(page): detect page type and extract components
- Component registry: page_type → extractor logic (extend via COMPONENT_EXTRACTORS)
"""
from .models import (
    PageModel,
    ProductCard,
    PageType,
    SearchBarComponent,
    CartComponent,
    DeliveryComponent,
    AddressFormComponent,
)
from .extractor import (
    extract_page_model_sync,
    extract_page_model_async,
    extract_page_model,
)

# Optional: register custom extractors per page_type for LG / other apps
COMPONENT_EXTRACTORS = {}

__all__ = [
    "PageModel",
    "ProductCard",
    "PageType",
    "SearchBarComponent",
    "CartComponent",
    "DeliveryComponent",
    "AddressFormComponent",
    "extract_page_model",
    "extract_page_model_sync",
    "extract_page_model_async",
    "COMPONENT_EXTRACTORS",
]
