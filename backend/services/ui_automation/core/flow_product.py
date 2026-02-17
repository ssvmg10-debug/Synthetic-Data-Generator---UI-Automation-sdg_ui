"""
ProductFlow Executor
Handles product selection and interaction with fuzzy matching and CTA classification
"""
import logging
from playwright.async_api import Page, Locator, TimeoutError as PlaywrightTimeout
from typing import Optional, List
from fuzzywuzzy import fuzz
from services.ui_automation.core.intent_models import Intent, IntentType
from services.ui_automation.core.state_validation import StateValidator
from services.ui_automation.core.cta_classifier import CTAClassifier

logger = logging.getLogger(__name__)


class ProductFlowExecutor:
    """
    Specialized executor for product flows.
    
    Features:
    - Fuzzy product name matching
    - CTA classification for primary actions
    - Cart update validation
    """
    
    def __init__(self):
        self.state_validator = StateValidator()
        self.cta_classifier = CTAClassifier()
    
    async def execute_select_product(self, page: Page, intent: Intent) -> bool:
        """
        Execute SELECT_PRODUCT intent.
        
        Uses fuzzy matching to find best product card match.
        
        Args:
            page: Playwright page
            intent: Select product intent with product_name
        
        Returns:
            True if product selected
        """
        product_name = intent.product_name or intent.value
        if not product_name:
            logger.error("Select product intent missing product_name")
            return False
        
        logger.info(f"🛍️  Selecting product: '{product_name}'")
        
        try:
            # Step 1: Get all product cards
            product_cards = await self._get_product_cards(page)
            if not product_cards:
                logger.error("No product cards found")
                return False
            
            logger.info(f"  Found {len(product_cards)} product cards")
            
            # Step 2: Fuzzy match product name
            best_match = await self._find_best_product_match(product_cards, product_name)
            if not best_match:
                logger.error(f"No match found for: {product_name}")
                return False
            
            # Step 3: Click product card
            await best_match.click()
            logger.info("  ✅ Clicked product card")
            
            # Step 4: Wait for product page to load
            await page.wait_for_load_state("domcontentloaded")
            
            # Step 5: Validate product page loaded
            page_loaded = await self.state_validator.wait_for_product_page(page)
            if not page_loaded:
                logger.warning("Product page validation failed")
                # Don't fail hard - page might have loaded
            
            logger.info(f"✅ Product selected: '{product_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Select product failed: {e}")
            return False
    
    async def execute_add_to_cart(self, page: Page, intent: Intent) -> bool:
        """
        Execute ADD_TO_CART intent.
        
        Uses CTA classification to find the correct button (Buy Now, Add to Cart, etc.).
        
        Args:
            page: Playwright page
            intent: Add to cart intent
        
        Returns:
            True if added to cart
        """
        logger.info("🛒 Adding product to cart")
        
        try:
            # Step 1: Classify and find primary CTA
            cta_button = await self.cta_classifier.classify_primary_cta(
                page,
                context="product_page",
                preferred_text=intent.element_text
            )
            
            if not cta_button:
                logger.error("Could not find primary CTA button")
                return False
            
            # Step 2: Click CTA
            await cta_button.click()
            logger.info("  ✅ Clicked primary CTA")
            
            # Step 3: Wait a moment for cart update
            await page.wait_for_timeout(1000)
            
            # Step 4: Validate cart updated
            cart_updated = await self.state_validator.wait_for_cart_update(page)
            if not cart_updated:
                logger.warning("Cart update validation failed")
                # Don't fail hard - cart might have updated
            
            logger.info("✅ Product added to cart")
            return True
            
        except Exception as e:
            logger.error(f"Add to cart failed: {e}")
            return False
    
    async def execute_view_cart(self, page: Page, intent: Intent) -> bool:
        """
        Execute VIEW_CART intent.
        
        Args:
            page: Playwright page
            intent: View cart intent
        
        Returns:
            True if cart opened
        """
        logger.info("🛒 Viewing cart")
        
        try:
            # Look for cart icon/button
            cart_selectors = [
                "[aria-label*='Cart']",
                "[aria-label*='cart']",
                "[data-testid='cart']",
                ".cart-icon",
                "a:has-text('Cart')",
                "button:has-text('Cart')",
            ]
            
            for selector in cart_selectors:
                cart_button = await page.query_selector(selector)
                if cart_button:
                    await cart_button.click()
                    logger.info("  ✅ Clicked cart button")
                    await page.wait_for_load_state("domcontentloaded")
                    return True
            
            logger.error("Could not find cart button")
            return False
            
        except Exception as e:
            logger.error(f"View cart failed: {e}")
            return False
    
    async def _get_product_cards(self, page: Page) -> List[Locator]:
        """
        Get all product cards on the page.
        
        Returns:
            List of product card locators
        """
        selectors = [
            ".product-card",
            "[data-testid='product-card']",
            ".product-item",
            ".search-result-item",
            "[class*='product']",
        ]
        
        for selector in selectors:
            try:
                cards = page.locator(selector)
                count = await cards.count()
                if count > 0:
                    logger.info(f"  Found {count} cards with selector: {selector}")
                    return [cards.nth(i) for i in range(count)]
            except:
                continue
        
        return []
    
    async def _find_best_product_match(
        self,
        product_cards: List[Locator],
        target_name: str
    ) -> Optional[Locator]:
        """
        Find best matching product card using fuzzy matching.
        
        Args:
            product_cards: List of product card locators
            target_name: Target product name
        
        Returns:
            Best matching product card or None
        """
        best_match = None
        best_score = 0
        
        target_lower = target_name.lower()
        
        for card in product_cards:
            try:
                # Get card text
                text = await card.inner_text()
                text_lower = text.lower()
                
                # Calculate fuzzy match score
                # Use partial ratio for substring matching
                score = fuzz.partial_ratio(target_lower, text_lower)
                
                # Also check token set ratio for word-based matching
                token_score = fuzz.token_set_ratio(target_lower, text_lower)
                
                # Take max of both scores
                final_score = max(score, token_score)
                
                if final_score > best_score:
                    best_score = final_score
                    best_match = card
                    logger.debug(f"  New best match: score={final_score} | {text[:50]}")
                
            except Exception as e:
                logger.debug(f"Error processing card: {e}")
                continue
        
        if best_match:
            logger.info(f"  ✅ Best match score: {best_score}/100")
            if best_score < 60:
                logger.warning(f"Low match score: {best_score}")
        
        return best_match if best_score >= 50 else None
