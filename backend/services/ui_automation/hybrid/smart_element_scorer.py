"""
Smart Element Scorer - Mathematical scoring engine for element matching.

Replaces blind strategy loops with probabilistic scoring model.
Uses feature vectors and weighted scoring for intelligent element selection.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from fuzzywuzzy import fuzz
import logging
import re

from .page_state_extractor import InteractiveElement, PageState

logger = logging.getLogger(__name__)


@dataclass
class ScoredElement:
    """Element with computed match score."""
    element: InteractiveElement
    total_score: float
    score_breakdown: Dict[str, float]
    rank: int


class SmartElementScorer:
    """
    Mathematical scoring engine for element matching.
    
    Instead of 9 blind strategies, builds feature vector and scores each element.
    """
    
    # Scoring weights (sum to 1.0)
    WEIGHTS = {
        'text_similarity': 0.50,    # How well text matches
        'role_match': 0.20,          # Element role appropriateness
        'tag_weight': 0.10,          # Tag type priority
        'proximity': 0.10,           # Position on page
        'attributes': 0.10,          # Attribute matching
    }
    
    # Tag priorities for different action types
    TAG_PRIORITIES = {
        'click': {
            'button': 1.0,
            'a': 0.9,
            'div': 0.5,
            'span': 0.4,
        },
        'type': {
            'input': 1.0,
            'textarea': 0.9,
            'select': 0.5,
        },
    }
    
    # Role priorities
    ROLE_PRIORITIES = {
        'click': ['button', 'link', 'menuitem', 'tab'],
        'type': ['textbox', 'searchbox', 'combobox'],
    }
    
    def __init__(self, page_state: PageState):
        self.page_state = page_state
        self.threshold = 0.60  # Minimum score to be considered a match
        
    def score_elements_for_click(self, target_text: str) -> List[ScoredElement]:
        """
        Score all clickable elements for a CLICK action.
        
        Args:
            target_text: The text/label we're looking for
            
        Returns:
            List of ScoredElement, sorted by score (highest first)
        """
        logger.info(f"🎯 Scoring elements for CLICK: '{target_text}'")
        
        # Filter to clickable elements
        clickable_types = ['button', 'link']
        candidates = [e for e in self.page_state.interactive_elements 
                     if e.element_type in clickable_types]
        
        if not candidates:
            logger.warning("No clickable elements found")
            return []
        
        # Score each candidate
        scored = []
        for elem in candidates:
            score, breakdown = self._compute_click_score(elem, target_text)
            scored.append(ScoredElement(
                element=elem,
                total_score=score,
                score_breakdown=breakdown,
                rank=0  # Will set after sorting
            ))
        
        # Sort by score descending
        scored.sort(key=lambda x: x.total_score, reverse=True)
        
        # Set ranks
        for i, se in enumerate(scored):
            se.rank = i + 1
        
        # Log top matches
        logger.info(f"📊 Top 3 matches:")
        for se in scored[:3]:
            logger.info(f"  Rank {se.rank}: score={se.total_score:.2f}, "
                       f"text='{se.element.text[:50]}', tag={se.element.tag}")
        
        # Filter by threshold
        matches = [se for se in scored if se.total_score >= self.threshold]
        logger.info(f"✅ Found {len(matches)} elements above threshold {self.threshold}")
        
        return matches
    
    def score_elements_for_type(self, target_text: str, value: str) -> List[ScoredElement]:
        """
        Score all input elements for a TYPE action.
        
        Args:
            target_text: Description of the input field
            value: The value we want to type
            
        Returns:
            List of ScoredElement, sorted by score (highest first)
        """
        logger.info(f"⌨️ Scoring elements for TYPE: '{target_text}'")
        
        # Filter to input elements
        input_types = ['input', 'select']
        candidates = [e for e in self.page_state.interactive_elements 
                     if e.element_type in input_types]
        
        if not candidates:
            logger.warning("No input elements found")
            return []
        
        # Score each candidate
        scored = []
        for elem in candidates:
            score, breakdown = self._compute_type_score(elem, target_text, value)
            scored.append(ScoredElement(
                element=elem,
                total_score=score,
                score_breakdown=breakdown,
                rank=0
            ))
        
        # Sort and rank
        scored.sort(key=lambda x: x.total_score, reverse=True)
        for i, se in enumerate(scored):
            se.rank = i + 1
        
        # Log top matches
        logger.info(f"📊 Top 3 matches:")
        for se in scored[:3]:
            logger.info(f"  Rank {se.rank}: score={se.total_score:.2f}, "
                       f"text='{se.element.text[:30]}', "
                       f"placeholder='{se.element.attributes.get('placeholder', '')}', "
                       f"name={se.element.attributes.get('name', '')}")
        
        matches = [se for se in scored if se.total_score >= self.threshold]
        logger.info(f"✅ Found {len(matches)} elements above threshold {self.threshold}")
        
        return matches
    
    def _compute_click_score(self, elem: InteractiveElement, target: str) -> Tuple[float, Dict[str, float]]:
        """
        Compute score for a clickable element.
        
        Returns:
            (total_score, breakdown_dict)
        """
        breakdown = {}
        
        # 1. Text similarity (50%)
        text_score = self._text_similarity_score(elem, target)
        breakdown['text_similarity'] = text_score * self.WEIGHTS['text_similarity']
        
        # 2. Role match (20%)
        role_score = self._role_match_score(elem, 'click')
        breakdown['role_match'] = role_score * self.WEIGHTS['role_match']
        
        # 3. Tag weight (10%)
        tag_score = self._tag_weight_score(elem, 'click')
        breakdown['tag_weight'] = tag_score * self.WEIGHTS['tag_weight']
        
        # 4. Proximity (10%) - elements higher on page score better
        proximity_score = self._proximity_score(elem)
        breakdown['proximity'] = proximity_score * self.WEIGHTS['proximity']
        
        # 5. Attributes (10%)
        attr_score = self._attribute_match_score(elem, target)
        breakdown['attributes'] = attr_score * self.WEIGHTS['attributes']
        
        total = sum(breakdown.values())
        return total, breakdown
    
    def _compute_type_score(self, elem: InteractiveElement, target: str, value: str) -> Tuple[float, Dict[str, float]]:
        """Compute score for an input element."""
        breakdown = {}
        
        # Text similarity (check placeholder, label, name)
        text_score = self._input_text_similarity(elem, target, value)
        breakdown['text_similarity'] = text_score * self.WEIGHTS['text_similarity']
        
        # Role match
        role_score = self._role_match_score(elem, 'type')
        breakdown['role_match'] = role_score * self.WEIGHTS['role_match']
        
        # Tag weight
        tag_score = self._tag_weight_score(elem, 'type')
        breakdown['tag_weight'] = tag_score * self.WEIGHTS['tag_weight']
        
        # Proximity
        proximity_score = self._proximity_score(elem)
        breakdown['proximity'] = proximity_score * self.WEIGHTS['proximity']
        
        # Input type appropriateness
        input_type_score = self._input_type_score(elem, target, value)
        breakdown['attributes'] = input_type_score * self.WEIGHTS['attributes']
        
        total = sum(breakdown.values())
        return total, breakdown
    
    def _text_similarity_score(self, elem: InteractiveElement, target: str) -> float:
        """
        Calculate text similarity using fuzzy matching.
        
        Returns score 0.0 to 1.0
        """
        # Normalize
        target_lower = target.lower().strip()
        
        # Check multiple text sources
        text_sources = [
            elem.text,
            elem.aria_label or '',
            elem.attributes.get('title', ''),
            elem.attributes.get('alt', ''),
        ]
        
        max_score = 0.0
        for text in text_sources:
            if not text:
                continue
            
            text_lower = text.lower().strip()
            
            # Try multiple fuzzy algorithms
            ratio = fuzz.ratio(target_lower, text_lower) / 100.0
            partial = fuzz.partial_ratio(target_lower, text_lower) / 100.0
            token_sort = fuzz.token_sort_ratio(target_lower, text_lower) / 100.0
            
            # Take best
            score = max(ratio, partial, token_sort)
            max_score = max(max_score, score)
            
            # Exact match bonus
            if target_lower == text_lower:
                max_score = 1.0
                break
            
            # Contains bonus
            if target_lower in text_lower or text_lower in target_lower:
                max_score = max(max_score, 0.85)
        
        return max_score
    
    def _input_text_similarity(self, elem: InteractiveElement, target: str, value: str) -> float:
        """Text similarity for input elements."""
        target_lower = target.lower()
        value_lower = value.lower()
        
        # Check placeholder
        placeholder = elem.attributes.get('placeholder', '').lower()
        if placeholder:
            score = fuzz.partial_ratio(target_lower, placeholder) / 100.0
            if score > 0.8:
                return score
        
        # Check name attribute
        name = elem.attributes.get('name', '').lower()
        if name:
            score = fuzz.partial_ratio(target_lower, name) / 100.0
            if score > 0.7:
                return score
        
        # Check aria-label
        if elem.aria_label:
            score = fuzz.partial_ratio(target_lower, elem.aria_label.lower()) / 100.0
            if score > 0.7:
                return score
        
        # Check for keywords in target matching input type
        keywords = {
            'search': 0.9,
            'email': 0.9,
            'password': 0.9,
            'pincode': 0.85,
            'zip': 0.85,
            'phone': 0.85,
            'name': 0.8,
            'address': 0.8,
        }
        
        for keyword, score in keywords.items():
            if keyword in target_lower and keyword in (name + placeholder):
                return score
        
        return 0.3  # Default for input elements
    
    def _role_match_score(self, elem: InteractiveElement, action_type: str) -> float:
        """Score based on element role."""
        if not elem.role:
            return 0.5  # Neutral
        
        role_lower = elem.role.lower()
        priorities = self.ROLE_PRIORITIES.get(action_type, [])
        
        for i, priority_role in enumerate(priorities):
            if priority_role in role_lower:
                # First match = 1.0, second = 0.8, third = 0.6, etc.
                return max(1.0 - (i * 0.2), 0.3)
        
        return 0.5
    
    def _tag_weight_score(self, elem: InteractiveElement, action_type: str) -> float:
        """Score based on tag priority."""
        tag = elem.tag.lower()
        priorities = self.TAG_PRIORITIES.get(action_type, {})
        
        return priorities.get(tag, 0.3)
    
    def _proximity_score(self, elem: InteractiveElement) -> float:
        """
        Score based on position on page.
        Elements higher/more visible score better.
        """
        # Elements in top 50% of viewport score higher
        y_position = elem.position.get('y', 0)
        
        # Normalize to 0-1 (assuming max page height of 5000px)
        normalized_y = min(y_position / 5000.0, 1.0)
        
        # Invert so top = 1.0, bottom = 0.0
        score = 1.0 - normalized_y
        
        # Boost visible elements in viewport
        if y_position < 1000:  # Likely in viewport
            score = min(score + 0.2, 1.0)
        
        return score
    
    def _attribute_match_score(self, elem: InteractiveElement, target: str) -> float:
        """Score based on attribute matching."""
        target_lower = target.lower()
        
        # Check class names
        class_attr = elem.attributes.get('class', '').lower()
        if any(word in class_attr for word in target_lower.split()):
            return 0.8
        
        # Check ID
        id_attr = elem.attributes.get('id', '').lower()
        if any(word in id_attr for word in target_lower.split()):
            return 0.9
        
        # Check data attributes
        for key, value in elem.attributes.items():
            if key.startswith('data-') and target_lower in value.lower():
                return 0.7
        
        return 0.3
    
    def _input_type_score(self, elem: InteractiveElement, target: str, value: str) -> float:
        """Score input element based on input type."""
        input_type = elem.attributes.get('type', 'text').lower()
        target_lower = target.lower()
        
        # Type appropriateness
        type_matches = {
            'email': ['email', 'mail'],
            'password': ['password', 'pass'],
            'tel': ['phone', 'mobile', 'tel'],
            'number': ['pincode', 'zip', 'code', 'number'],
            'search': ['search', 'query'],
            'text': ['name', 'address', 'city'],
        }
        
        for inp_type, keywords in type_matches.items():
            if input_type == inp_type:
                if any(kw in target_lower for kw in keywords):
                    return 0.9
        
        # If numeric value and number input
        if input_type == 'number' and value.isdigit():
            return 0.9
        
        return 0.5
    
    def find_best_match_for_click(self, target_text: str) -> Optional[InteractiveElement]:
        """
        Find single best matching element for click.
        
        Returns:
            InteractiveElement or None if no good match
        """
        scored = self.score_elements_for_click(target_text)
        
        if not scored:
            logger.warning(f"❌ No matches found for: {target_text}")
            return None
        
        best = scored[0]
        logger.info(f"✅ Best match: score={best.total_score:.2f}, "
                   f"text='{best.element.text[:50]}', selector={best.element.selector}")
        
        return best.element
    
    def find_best_match_for_type(self, target_text: str, value: str) -> Optional[InteractiveElement]:
        """Find single best matching input element."""
        scored = self.score_elements_for_type(target_text, value)
        
        if not scored:
            logger.warning(f"❌ No input matches found for: {target_text}")
            return None
        
        best = scored[0]
        logger.info(f"✅ Best input match: score={best.total_score:.2f}, "
                   f"placeholder='{best.element.attributes.get('placeholder', '')}', "
                   f"selector={best.element.selector}")
        
        return best.element
