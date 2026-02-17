"""
CTA (Call-to-Action) Classification Engine
Intelligently ranks and selects primary action buttons using multiple scoring factors
"""
import logging
from playwright.async_api import Page, Locator
from typing import List, Dict, Any, Optional, Tuple
import re
from fuzzywuzzy import fuzz

logger = logging.getLogger(__name__)


class CTAClassifier:
    """
    Scores and ranks CTA buttons to find the primary action.
    
    Scoring factors:
    - Text similarity (40%)
    - Button size (20%)
    - Location proximity to price (20%)
    - CSS styling weight (20%)
    
    This replaces brittle text matching like:
        if text == "Buy Now"
    """
    
    def __init__(self):
        self.primary_keywords = [
            "buy", "add to cart", "add to bag", "purchase", "checkout",
            "proceed", "continue", "place order", "confirm"
        ]
    
    async def classify_primary_cta(
        self,
        page: Page,
        context: str = "product_page",
        preferred_text: Optional[str] = None
    ) -> Optional[Locator]:
        """
        Find and classify the primary CTA button.
        
        Args:
            page: Playwright page
            context: Context hint (product_page, cart, checkout)
            preferred_text: Preferred button text if known
        
        Returns:
            Locator for best matching CTA button or None
        """
        logger.info(f"🎯 Classifying primary CTA (context: {context})")
        
        try:
            # Step 1: Get all candidate buttons
            buttons = await self._get_candidate_buttons(page)
            if not buttons:
                logger.error("No candidate buttons found")
                return None
            
            logger.info(f"  Found {len(buttons)} candidate buttons")
            
            # Step 2: Score each button
            scored_buttons = []
            for button in buttons:
                score = await self._score_button(page, button, context, preferred_text)
                scored_buttons.append((button, score))
            
            # Step 3: Sort by score (descending)
            scored_buttons.sort(key=lambda x: x[1], reverse=True)
            
            # Step 4: Log top candidates
            for i, (button, score) in enumerate(scored_buttons[:3], 1):
                text = await button.inner_text()
                logger.info(f"  #{i} score={score:.2f} | '{text[:50]}'")
            
            # Step 5: Return highest scoring button
            best_button, best_score = scored_buttons[0]
            if best_score < 0.3:
                logger.warning(f"Best CTA score too low: {best_score:.2f}")
                return None
            
            logger.info(f"  ✅ Selected CTA with score: {best_score:.2f}")
            return best_button
            
        except Exception as e:
            logger.error(f"CTA classification failed: {e}")
            return None
    
    async def _get_candidate_buttons(self, page: Page) -> List[Locator]:
        """
        Get all visible, enabled buttons that could be CTAs.
        
        Returns:
            List of button locators
        """
        candidates = []
        
        # Query all buttons and button-like elements
        selectors = [
            "button:visible",
            "a[role='button']:visible",
            "[data-testid*='button']:visible",
            ".btn:visible",
        ]
        
        for selector in selectors:
            try:
                elements = page.locator(selector)
                count = await elements.count()
                for i in range(count):
                    elem = elements.nth(i)
                    # Check visibility and enabled state
                    if await elem.is_visible() and await elem.is_enabled():
                        candidates.append(elem)
            except:
                continue
        
        return candidates
    
    async def _score_button(
        self,
        page: Page,
        button: Locator,
        context: str,
        preferred_text: Optional[str]
    ) -> float:
        """
        Score a button based on multiple factors.
        
        Scoring breakdown:
        - text_similarity: 0-40 points
        - button_size: 0-20 points
        - proximity_to_price: 0-20 points
        - css_weight: 0-20 points
        
        Max score: 100
        Normalized to 0.0-1.0
        
        Returns:
            Score between 0.0 and 1.0
        """
        try:
            # Get button properties
            text = await button.inner_text()
            text = text.strip().lower()
            
            # Factor 1: Text similarity (40% weight)
            text_score = self._score_text_similarity(text, context, preferred_text)
            
            # Factor 2: Button size (20% weight)
            size_score = await self._score_button_size(button)
            
            # Factor 3: Proximity to price (20% weight)
            proximity_score = await self._score_proximity_to_price(page, button)
            
            # Factor 4: CSS styling weight (20% weight)
            style_score = await self._score_css_weight(button)
            
            # Compute weighted total
            total = (
                text_score * 0.4 +
                size_score * 0.2 +
                proximity_score * 0.2 +
                style_score * 0.2
            )
            
            return total
            
        except Exception as e:
            logger.debug(f"Error scoring button: {e}")
            return 0.0
    
    def _score_text_similarity(
        self,
        text: str,
        context: str,
        preferred_text: Optional[str]
    ) -> float:
        """
        Score based on text similarity to expected CTA text.
        
        Returns:
            Score 0.0-1.0
        """
        # If preferred text provided, use fuzzy match
        if preferred_text:
            similarity = fuzz.partial_ratio(text, preferred_text.lower()) / 100.0
            if similarity > 0.8:
                return similarity
        
        # Context-based keyword matching
        context_keywords = {
            "product_page": ["buy", "add to cart", "add to bag", "add"],
            "cart": ["checkout", "proceed", "continue"],
            "checkout": ["place order", "complete", "confirm", "pay"],
        }
        
        keywords = context_keywords.get(context, self.primary_keywords)
        
        # Check for keyword matches
        max_score = 0.0
        for keyword in keywords:
            if keyword in text:
                # Exact match: high score
                if text == keyword:
                    max_score = max(max_score, 1.0)
                # Contains match: moderate score
                else:
                    max_score = max(max_score, 0.7)
            else:
                # Fuzzy match
                similarity = fuzz.partial_ratio(text, keyword) / 100.0
                max_score = max(max_score, similarity * 0.6)
        
        return max_score
    
    async def _score_button_size(self, button: Locator) -> float:
        """
        Score based on button size (larger = more prominent).
        
        Returns:
            Score 0.0-1.0
        """
        try:
            box = await button.bounding_box()
            if not box:
                return 0.0
            
            area = box['width'] * box['height']
            
            # Normalize size score
            # Typical button: 100x40 = 4000px²
            # Large CTA: 200x50 = 10000px²
            if area > 8000:
                return 1.0
            elif area > 4000:
                return 0.7
            elif area > 2000:
                return 0.4
            else:
                return 0.2
        except:
            return 0.5
    
    async def _score_proximity_to_price(self, page: Page, button: Locator) -> float:
        """
        Score based on proximity to price element.
        Primary CTAs are usually near prices.
        
        Returns:
            Score 0.0-1.0
        """
        try:
            # Find price elements
            price_elem = await page.query_selector(
                ".price, [data-testid='price'], .product-price, [class*='price']"
            )
            if not price_elem:
                return 0.5  # Neutral score if no price found
            
            # Get positions
            button_box = await button.bounding_box()
            price_box = await price_elem.bounding_box()
            
            if not button_box or not price_box:
                return 0.5
            
            # Calculate distance
            button_center_y = button_box['y'] + button_box['height'] / 2
            price_center_y = price_box['y'] + price_box['height'] / 2
            
            distance = abs(button_center_y - price_center_y)
            
            # Closer = higher score
            if distance < 100:
                return 1.0
            elif distance < 200:
                return 0.7
            elif distance < 400:
                return 0.4
            else:
                return 0.2
        except:
            return 0.5
    
    async def _score_css_weight(self, button: Locator) -> float:
        """
        Score based on CSS styling (primary buttons have distinctive styling).
        
        Checks:
        - class contains 'primary', 'cta', 'main'
        - background color is prominent
        
        Returns:
            Score 0.0-1.0
        """
        try:
            # Get classes
            classes = await button.get_attribute("class") or ""
            classes_lower = classes.lower()
            
            # Check for primary indicators
            if any(kw in classes_lower for kw in ["primary", "cta", "main", "accent"]):
                return 1.0
            
            # Check for secondary indicators (lower score)
            if any(kw in classes_lower for kw in ["secondary", "outline", "ghost"]):
                return 0.3
            
            # Default: moderate score
            return 0.6
        except:
            return 0.5
