"""
Fuzzy Text Matcher for UI Automation
Handles text mismatches like "grey shirt" vs "Grey jacket" with intelligent similarity scoring.
"""
from difflib import SequenceMatcher
from typing import List, Tuple, Optional
import re
import logging

logger = logging.getLogger(__name__)


class FuzzyMatcher:
    """
    Intelligent text matching for UI element identification.
    
    Handles:
    - Case mismatches: "Login" vs "login"
    - Punctuation differences: "Add to Cart" vs "add-to-cart"
    - Partial matches: "grey shirt" vs "Grey jacket"
    - Whitespace variations: "Sign  In" vs "Sign In"
    
    Example:
        matcher = FuzzyMatcher(threshold=0.65)
        
        # Simple similarity
        score = matcher.similarity("grey shirt", "Grey jacket")  # 0.69
        
        # Find best match
        candidates = ["Add to Cart", "Add to Bag", "Buy Now"]
        match = matcher.find_best_match("add to cart", candidates)
        # Returns: ("Add to Cart", 0.95)
        
        # Find multiple matches
        matches = matcher.find_all_matches("checkout", candidates, top_n=3)
    """
    
    def __init__(self, threshold: float = 0.65):
        """
        Initialize fuzzy matcher.
        
        Args:
            threshold: Minimum similarity score (0.0-1.0) to consider a match.
                      Recommended values:
                      - 0.60-0.65: Lenient (catches more matches, more false positives)
                      - 0.70-0.75: Balanced (good for most cases)
                      - 0.80-0.85: Strict (fewer matches, higher confidence)
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        
        self.threshold = threshold
        logger.info(f"FuzzyMatcher initialized with threshold={threshold}")
    
    def normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison.
        
        Steps:
        1. Convert to lowercase
        2. Remove punctuation (except spaces)
        3. Collapse multiple spaces
        4. Strip leading/trailing whitespace
        
        Args:
            text: Input text
        
        Returns:
            Normalized text
        
        Examples:
            normalize_text("Add-to-Cart!") -> "add to cart"
            normalize_text("Sign  In") -> "sign in"
        """
        if not text:
            return ""
        
        # Lowercase
        text = text.lower()
        
        # Remove punctuation except spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Collapse multiple spaces
        text = ' '.join(text.split())
        
        return text.strip()
    
    def similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity score between two strings.
        
        Uses SequenceMatcher for Levenshtein-like distance calculation.
        Score is between 0.0 (completely different) and 1.0 (identical).
        
        Args:
            text1: First string
            text2: Second string
        
        Returns:
            Similarity score (0.0-1.0)
        
        Examples:
            similarity("grey shirt", "Grey jacket") -> 0.69
            similarity("login", "Login") -> 1.0 (after normalization)
            similarity("cart", "checkout") -> 0.28
        """
        if not text1 or not text2:
            return 0.0
        
        norm1 = self.normalize_text(text1)
        norm2 = self.normalize_text(text2)
        
        if not norm1 or not norm2:
            return 0.0
        
        score = SequenceMatcher(None, norm1, norm2).ratio()
        
        logger.debug(f"Similarity: '{text1}' vs '{text2}' = {score:.2f}")
        
        return score
    
    def find_best_match(
        self,
        query: str,
        candidates: List[str]
    ) -> Optional[Tuple[str, float]]:
        """
        Find the best matching candidate above threshold.
        
        Args:
            query: Search query (e.g., "grey shirt")
            candidates: List of candidate strings to match against
        
        Returns:
            Tuple of (best_match, score) if found, None otherwise
        
        Examples:
            find_best_match("add to cart", ["Add to Cart", "Checkout"])
            -> ("Add to Cart", 0.95)
            
            find_best_match("missing", ["Available", "Options"])
            -> None (no match above threshold)
        """
        if not query or not candidates:
            return None
        
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            if not candidate:
                continue
            
            score = self.similarity(query, candidate)
            
            if score > best_score and score >= self.threshold:
                best_score = score
                best_match = candidate
        
        if best_match:
            logger.info(f"Best match for '{query}': '{best_match}' (score: {best_score:.2f})")
            return (best_match, best_score)
        
        logger.debug(f"No match found for '{query}' above threshold {self.threshold}")
        return None
    
    def find_all_matches(
        self,
        query: str,
        candidates: List[str],
        top_n: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Find top N matches above threshold, sorted by score.
        
        Useful for getting alternative selectors when primary fails.
        
        Args:
            query: Search query
            candidates: List of candidate strings
            top_n: Maximum number of matches to return
        
        Returns:
            List of (match, score) tuples, sorted by score descending
        
        Examples:
            find_all_matches("checkout", ["Checkout", "Proceed", "Complete Order"], top_n=3)
            -> [("Checkout", 1.0), ("Complete Order", 0.45), ...]
        """
        if not query or not candidates:
            return []
        
        matches = []
        
        for candidate in candidates:
            if not candidate:
                continue
            
            score = self.similarity(query, candidate)
            
            if score >= self.threshold:
                matches.append((candidate, score))
        
        # Sort by score descending
        matches.sort(key=lambda x: x[1], reverse=True)
        
        result = matches[:top_n]
        
        if result:
            logger.info(f"Found {len(result)} matches for '{query}': {[m[0] for m in result]}")
        else:
            logger.debug(f"No matches found for '{query}' above threshold {self.threshold}")
        
        return result
    
    def is_match(self, text1: str, text2: str) -> bool:
        """
        Check if two strings match above threshold.
        
        Args:
            text1: First string
            text2: Second string
        
        Returns:
            True if similarity >= threshold, False otherwise
        
        Examples:
            is_match("Grey Shirt", "grey shirt") -> True
            is_match("cart", "checkout") -> False
        """
        return self.similarity(text1, text2) >= self.threshold
    
    def get_threshold(self) -> float:
        """Get current similarity threshold."""
        return self.threshold
    
    def set_threshold(self, threshold: float):
        """
        Update similarity threshold.
        
        Args:
            threshold: New threshold (0.0-1.0)
        
        Raises:
            ValueError: If threshold not in valid range
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        
        old_threshold = self.threshold
        self.threshold = threshold
        logger.info(f"Threshold updated: {old_threshold} -> {threshold}")


# Convenience functions for quick usage
_default_matcher = None

def get_default_matcher(threshold: float = 0.65) -> FuzzyMatcher:
    """Get singleton instance of FuzzyMatcher with default threshold."""
    global _default_matcher
    if _default_matcher is None or _default_matcher.get_threshold() != threshold:
        _default_matcher = FuzzyMatcher(threshold)
    return _default_matcher


def fuzzy_match(text1: str, text2: str, threshold: float = 0.65) -> bool:
    """Quick fuzzy match check."""
    matcher = get_default_matcher(threshold)
    return matcher.is_match(text1, text2)


def find_fuzzy_match(query: str, candidates: List[str], threshold: float = 0.65) -> Optional[Tuple[str, float]]:
    """Quick best match finder."""
    matcher = get_default_matcher(threshold)
    return matcher.find_best_match(query, candidates)
