"""
Product Similarity Engine - Matches product descriptions intelligently.

Uses fuzzy matching and semantic understanding to find products
even when exact text doesn't match.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from fuzzywuzzy import fuzz
import re

logger = logging.getLogger(__name__)


@dataclass
class ProductMatch:
    """Represents a product match with score and locator."""
    element_handle: Any
    product_name: str
    similarity_score: float
    locator: str
    additional_info: Dict[str, Any]
    
    def __repr__(self):
        return f"ProductMatch(name='{self.product_name[:50]}', score={self.similarity_score:.2f})"


class ProductSimilarityEngine:
    """
    Matches products using fuzzy matching and semantic understanding.
    
    Handles cases where:
    - Product names are truncated
    - Different word order
    - Missing model numbers
    - Variations in description
    """
    
    def __init__(self):
        self.match_threshold = 0.60  # 60% similarity minimum
        self.excellent_threshold = 0.85  # 85% for excellent match
    
    def normalize_product_name(self, name: str) -> str:
        """
        Normalize product name for comparison.
        
        Args:
            name: Raw product name
        
        Returns:
            Normalized name
        """
        # Convert to lowercase
        name = name.lower()
        
        # Remove extra whitespace
        name = re.sub(r'\s+', ' ', name).strip()
        
        # Remove special characters but keep numbers and letters
        name = re.sub(r'[^\w\s.-]', ' ', name)
        
        # Normalize common abbreviations
        replacements = {
            'tv': 'television',
            'ac': 'air conditioner',
            'cm': 'cm',
            'inch': 'inch',
            'l': 'litre',
            'kg': 'kilogram',
        }
        
        for abbr, full in replacements.items():
            name = re.sub(rf'\b{abbr}\b', full, name)
        
        return name
    
    def extract_key_features(self, name: str) -> Dict[str, List[str]]:
        """
        Extract key features from product name.
        
        Returns:
            Dictionary with extracted features (numbers, brand, model, capacity)
        """
        features = {
            "numbers": [],
            "brand": [],
            "model": [],
            "capacity": [],
            "keywords": []
        }
        
        # Extract numbers (including decimals)
        numbers = re.findall(r'\d+(?:\.\d+)?', name)
        features["numbers"] = numbers
        
        # Extract brand (common brands)
        brands = ['lg', 'samsung', 'sony', 'panasonic', 'whirlpool', 'bosch']
        name_lower = name.lower()
        for brand in brands:
            if brand in name_lower:
                features["brand"].append(brand)
        
        # Extract capacity (e.g., "108cm", "1.5 ton", "2TB")
        capacity_patterns = [
            r'\d+(?:\.\d+)?\s*(?:cm|inch|"|ton|tb|gb|l|litre|kg)',
            r'\d+(?:\.\d+)?\s*star',
        ]
        for pattern in capacity_patterns:
            matches = re.findall(pattern, name_lower, re.IGNORECASE)
            features["capacity"].extend(matches)
        
        # Extract model identifiers (alphanumeric codes)
        models = re.findall(r'\b[A-Z]{2,}\d+[A-Z0-9]*\b', name, re.IGNORECASE)
        features["model"] = models
        
        # Extract important keywords
        important_keywords = [
            'split', 'window', 'inverter', 'smart', 'led', 'oled', 'qled',
            'uhd', '4k', '8k', 'refrigerator', 'washing', 'dryer', 'front',
            'top', 'load', 'automatic', 'semi', 'frost', 'free', 'door'
        ]
        for keyword in important_keywords:
            if keyword in name_lower:
                features["keywords"].append(keyword)
        
        return features
    
    def calculate_similarity(
        self,
        search_term: str,
        product_name: str,
        use_feature_matching: bool = True
    ) -> float:
        """
        Calculate similarity score between search term and product name.
        
        Args:
            search_term: What user is looking for
            product_name: Product name from page
            use_feature_matching: Use feature-based matching
        
        Returns:
            Similarity score (0.0 to 1.0)
        """
        # Normalize both
        search_norm = self.normalize_product_name(search_term)
        product_norm = self.normalize_product_name(product_name)
        
        # Base fuzzy score (using multiple algorithms)
        ratio_score = fuzz.ratio(search_norm, product_norm) / 100.0
        partial_score = fuzz.partial_ratio(search_norm, product_norm) / 100.0
        token_sort_score = fuzz.token_sort_ratio(search_norm, product_norm) / 100.0
        token_set_score = fuzz.token_set_ratio(search_norm, product_norm) / 100.0
        
        # Weighted average of fuzzy scores
        fuzzy_score = (
            ratio_score * 0.2 +
            partial_score * 0.3 +
            token_sort_score * 0.25 +
            token_set_score * 0.25
        )
        
        if not use_feature_matching:
            return fuzzy_score
        
        # Feature-based matching (boosts score)
        search_features = self.extract_key_features(search_term)
        product_features = self.extract_key_features(product_name)
        
        feature_score = 0.0
        feature_weight = 0.0
        
        # Brand match (important)
        if search_features["brand"] and product_features["brand"]:
            if any(b in product_features["brand"] for b in search_features["brand"]):
                feature_score += 0.15
            feature_weight += 0.15
        
        # Model match (very important)
        if search_features["model"] and product_features["model"]:
            if any(m in product_features["model"] for m in search_features["model"]):
                feature_score += 0.20
            feature_weight += 0.20
        
        # Capacity match (important)
        if search_features["capacity"]:
            capacity_matches = sum(
                1 for c in search_features["capacity"]
                if any(c in pc for pc in product_features["capacity"])
            )
            if capacity_matches > 0:
                feature_score += 0.15 * (capacity_matches / len(search_features["capacity"]))
            feature_weight += 0.15
        
        # Number match (somewhat important)
        if search_features["numbers"]:
            number_matches = sum(
                1 for n in search_features["numbers"]
                if n in product_features["numbers"]
            )
            if number_matches > 0:
                feature_score += 0.10 * (number_matches / len(search_features["numbers"]))
            feature_weight += 0.10
        
        # Keyword match (helpful)
        if search_features["keywords"]:
            keyword_matches = sum(
                1 for k in search_features["keywords"]
                if k in product_features["keywords"]
            )
            if keyword_matches > 0:
                feature_score += 0.10 * (keyword_matches / len(search_features["keywords"]))
            feature_weight += 0.10
        
        # Combine fuzzy score with feature score
        if feature_weight > 0:
            # Boost fuzzy score based on feature matches
            final_score = fuzzy_score * 0.6 + (feature_score / feature_weight) * 0.4
        else:
            final_score = fuzzy_score
        
        return min(final_score, 1.0)
    
    async def find_best_product_match(
        self,
        page: Any,
        search_term: str,
        container_selector: str = '[class*="product"]'
    ) -> Optional[ProductMatch]:
        """
        Find best matching product on the page.
        
        Args:
            page: Playwright page object
            search_term: Product to search for
            container_selector: CSS selector for product containers
        
        Returns:
            ProductMatch or None
        """
        logger.info(f"🔍 Finding product: '{search_term}'")
        
        try:
            # Find all product containers
            containers = await page.locator(container_selector).all()
            
            if not containers:
                logger.warning(f"No product containers found with selector: {container_selector}")
                return None
            
            logger.info(f"Found {len(containers)} product containers")
            
            matches = []
            
            for idx, container in enumerate(containers):
                try:
                    # Extract product name from container
                    product_name = await self._extract_product_name(container)
                    
                    if not product_name:
                        continue
                    
                    # Calculate similarity
                    score = self.calculate_similarity(search_term, product_name)
                    
                    if score >= self.match_threshold:
                        # Extract additional info
                        price = await self._extract_price(container)
                        image = await self._extract_image(container)
                        
                        match = ProductMatch(
                            element_handle=container,
                            product_name=product_name,
                            similarity_score=score,
                            locator=f"{container_selector}:nth-child({idx + 1})",
                            additional_info={
                                "price": price,
                                "image": image,
                                "index": idx
                            }
                        )
                        matches.append(match)
                        
                        logger.debug(f"  Match {idx}: {product_name[:60]} (score: {score:.2f})")
                
                except Exception as e:
                    logger.debug(f"Error processing container {idx}: {e}")
                    continue
            
            if not matches:
                logger.warning(f"No products matched '{search_term}' (threshold: {self.match_threshold})")
                return None
            
            # Sort by score and return best match
            matches.sort(key=lambda m: m.similarity_score, reverse=True)
            best_match = matches[0]
            
            logger.info(f"✅ Best match: {best_match}")
            logger.info(f"   Top 3: {[f'{m.product_name[:40]}({m.similarity_score:.2f})' for m in matches[:3]]}")
            
            return best_match
        
        except Exception as e:
            logger.error(f"Error finding product: {e}")
            return None
    
    async def _extract_product_name(self, container: Any) -> Optional[str]:
        """Extract product name from container."""
        selectors = [
            'h1', 'h2', 'h3', 'h4',
            '[class*="product-name"]', '[class*="product-title"]',
            '[class*="title"]', '[data-product-name]',
            'a[title]', '[aria-label]'
        ]
        
        for selector in selectors:
            try:
                elem = container.locator(selector).first
                if await elem.count() > 0:
                    text = await elem.inner_text()
                    if text and len(text.strip()) > 3:
                        return text.strip()
                    # Try title attribute
                    title = await elem.get_attribute('title')
                    if title and len(title.strip()) > 3:
                        return title.strip()
            except:
                continue
        
        # Fallback: get all text
        try:
            text = await container.inner_text()
            if text:
                # Take first line or first 100 chars
                lines = text.strip().split('\n')
                return lines[0][:100]
        except:
            pass
        
        return None
    
    async def _extract_price(self, container: Any) -> Optional[str]:
        """Extract price from container."""
        selectors = [
            '[class*="price"]', '[data-price]', '[itemprop="price"]',
            'span:has-text("₹")', 'span:has-text("$")'
        ]
        
        for selector in selectors:
            try:
                elem = container.locator(selector).first
                if await elem.count() > 0:
                    text = await elem.inner_text()
                    if text:
                        return text.strip()
            except:
                continue
        
        return None
    
    async def _extract_image(self, container: Any) -> Optional[str]:
        """Extract product image URL."""
        try:
            img = container.locator('img').first
            if await img.count() > 0:
                src = await img.get_attribute('src')
                return src
        except:
            pass
        return None
