"""
Intent-Based Action Engine - Probabilistic Decision Making

Replaces deterministic rule-based decisions with confidence-scored intent matching.
Enterprise-grade approach that eliminates dead loops and static behavior.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from services.ui_automation.perception.dom_graph import UIGraph, UINode
from services.ui_automation.goal_extractor import GoalObject
from services.ui_automation.state_manager import SessionState
import logging
import re

logger = logging.getLogger(__name__)


class ActionIntent(str, Enum):
    """
    High-level intent categories instead of fixed semantic actions.
    Scored probabilistically against current UI state.
    """
    SEARCH = "search"
    NAVIGATE_CATEGORY = "navigate_category"
    SELECT_PRODUCT = "select_product"
    ADD_TO_CART = "add_to_cart"
    CHECKOUT = "checkout"
    FILL_FORM = "fill_form"
    SUBMIT_FORM = "submit_form"
    ACCEPT_MODAL = "accept_modal"
    LOGIN = "login"
    EXPLORE = "explore"  # Exploration mode
    UNKNOWN = "unknown"


@dataclass
class ScoredIntent:
    """
    Intent with confidence score and candidate nodes.
    """
    intent: ActionIntent
    confidence: float  # 0.0 to 1.0
    candidate_nodes: List[UINode]
    reasoning: str  # Why this score
    
    def __repr__(self):
        return f"ScoredIntent({self.intent.value}, conf={self.confidence:.2f}, nodes={len(self.candidate_nodes)})"


@dataclass
class IntentAction:
    """
    Chosen action with execution details.
    """
    intent: ActionIntent
    confidence: float
    target_node: Optional[UINode]
    params: Dict[str, any]
    reasoning: str


class IntentScorer:
    """
    Scores UI graph against goal intents using probabilistic matching.
    
    Replaces brittle if-else rules with structural pattern matching.
    """
    
    # Confidence thresholds
    HIGH_CONFIDENCE = 0.75
    MEDIUM_CONFIDENCE = 0.50
    LOW_CONFIDENCE = 0.30
    
    def __init__(self):
        self.visited_nodes: set = set()  # Track exploration
    
    def score_all_intents(
        self, 
        graph: UIGraph, 
        goal: GoalObject, 
        state: SessionState
    ) -> List[ScoredIntent]:
        """
        Score all possible intents against current UI state.
        
        Returns sorted list by confidence (highest first).
        """
        scores = []
        
        # Score each intent
        scores.append(self._score_accept_modal(graph, goal, state))
        scores.append(self._score_search(graph, goal, state))
        scores.append(self._score_navigate_category(graph, goal, state))
        scores.append(self._score_select_product(graph, goal, state))
        scores.append(self._score_add_to_cart(graph, goal, state))
        scores.append(self._score_checkout(graph, goal, state))
        scores.append(self._score_fill_form(graph, goal, state))
        scores.append(self._score_login(graph, goal, state))
        
        # Sort by confidence
        scores.sort(key=lambda x: x.confidence, reverse=True)
        
        # Log top 3
        logger.info(f"🎯 Intent Scores:")
        for score in scores[:3]:
            logger.info(f"  {score.intent.value}: {score.confidence:.2f} - {score.reasoning}")
        
        return scores
    
    def _score_accept_modal(
        self, 
        graph: UIGraph, 
        goal: GoalObject, 
        state: SessionState
    ) -> ScoredIntent:
        """
        Score modal acceptance intent.
        
        Modals are blocking - highest priority if detected.
        """
        score = 0.0
        candidates = []
        reasoning = ""
        
        # Look for modal indicators
        modal_keywords = [
            "accept", "allow", "agree", "continue", "ok", "close", 
            "cookie", "consent", "dismiss", "got it"
        ]
        
        # Find buttons with modal keywords
        for node in graph.get_clickable_nodes():
            text_lower = node.text.lower()
            
            # Check for modal button patterns
            for keyword in modal_keywords:
                if keyword in text_lower:
                    score += 0.3
                    candidates.append(node)
                    reasoning = f"Found modal button: '{node.text}'"
                    break
            
            # Check for role="dialog" parents
            if node.role in ["dialog", "alertdialog"]:
                score += 0.4
                if node not in candidates:
                    candidates.append(node)
                reasoning += " | Dialog role detected"
        
        # Boost if modal overlay detected
        overlay_nodes = [n for n in graph.nodes.values() 
                        if "modal" in str(n.attributes.get("class", "")).lower()
                        or "overlay" in str(n.attributes.get("class", "")).lower()]
        
        if overlay_nodes:
            score += 0.2
            reasoning += " | Overlay element present"
        
        # Already dismissed?
        if state.modal_visible == False:
            score = max(0.0, score - 0.5)
            reasoning += " | Already dismissed"
        
        return ScoredIntent(
            intent=ActionIntent.ACCEPT_MODAL,
            confidence=min(score, 1.0),
            candidate_nodes=candidates[:5],
            reasoning=reasoning or "No modal indicators"
        )
    
    def _score_search(
        self, 
        graph: UIGraph, 
        goal: GoalObject, 
        state: SessionState
    ) -> ScoredIntent:
        """Score search intent."""
        score = 0.0
        candidates = []
        reasoning = ""
        
        # Need search query
        if not goal.has_search_goal():
            return ScoredIntent(ActionIntent.SEARCH, 0.0, [], "No search query in goal")
        
        # Already searched?
        if state.has_searched():
            return ScoredIntent(ActionIntent.SEARCH, 0.0, [], "Already searched")
        
        # Look for search box
        search_inputs = graph.get_by_role("searchbox")
        if search_inputs:
            score += 0.5
            candidates.extend(search_inputs)
            reasoning = f"Found {len(search_inputs)} searchbox"
        
        # Look for text inputs with search hints
        for node in graph.nodes.values():
            if node.tag == "input" and node.is_visible:
                # Check placeholder
                if node.placeholder and "search" in node.placeholder.lower():
                    score += 0.3
                    candidates.append(node)
                    reasoning += f" | Input placeholder: '{node.placeholder}'"
                
                # Check aria-label
                if node.aria_label and "search" in node.aria_label.lower():
                    score += 0.3
                    candidates.append(node)
                    reasoning += f" | ARIA label: '{node.aria_label}'"
        
        # Look for search buttons
        search_buttons = graph.get_by_text("search")
        if search_buttons:
            score += 0.2
            reasoning += f" | {len(search_buttons)} search buttons"
        
        return ScoredIntent(
            intent=ActionIntent.SEARCH,
            confidence=min(score, 1.0),
            candidate_nodes=candidates[:5],
            reasoning=reasoning or "No search UI found"
        )
    
    def _score_navigate_category(
        self, 
        graph: UIGraph, 
        goal: GoalObject, 
        state: SessionState
    ) -> ScoredIntent:
        """Score category navigation intent."""
        score = 0.0
        candidates = []
        reasoning = ""
        
        # Already navigated to products?
        if state.product_selected or len(state.action_history) > 5:
            return ScoredIntent(
                ActionIntent.NAVIGATE_CATEGORY, 
                0.0, 
                [], 
                "Already past navigation"
            )
        
        # Look for navigation links
        nav_nodes = graph.get_by_role("link")
        
        # Category keywords
        category_keywords = [
            "products", "category", "shop", "browse", "menu",
            "air solutions", "tv", "appliance", "electronics"
        ]
        
        for node in nav_nodes[:50]:  # Limit search
            text_lower = node.text.lower()
            
            # Check if navigation item
            if any(kw in text_lower for kw in category_keywords):
                score += 0.2
                candidates.append(node)
                reasoning = f"Found category link: '{node.text}'"
            
            # Check if in nav/header
            if node.role == "navigation" or "nav" in str(node.attributes.get("class", "")):
                score += 0.1
        
        # Boost if on homepage
        if "www." in graph.url and len(graph.url.split("/")) <= 4:
            score += 0.3
            reasoning += " | On homepage"
        
        return ScoredIntent(
            intent=ActionIntent.NAVIGATE_CATEGORY,
            confidence=min(score, 1.0),
            candidate_nodes=candidates[:10],
            reasoning=reasoning or "No category links found"
        )
    
    def _score_select_product(
        self, 
        graph: UIGraph, 
        goal: GoalObject, 
        state: SessionState
    ) -> ScoredIntent:
        """Score product selection intent."""
        score = 0.0
        candidates = []
        reasoning = ""
        
        # Already selected?
        if state.product_selected:
            return ScoredIntent(
                ActionIntent.SELECT_PRODUCT, 
                0.0, 
                [], 
                "Product already selected"
            )
        
        # Need purchase goal
        if not goal.complete_purchase:
            return ScoredIntent(
                ActionIntent.SELECT_PRODUCT, 
                0.0, 
                [], 
                "No purchase goal"
            )
        
        # Look for product CTA buttons
        cta_keywords = [
            "buy now", "add to cart", "purchase", "order", 
            "know more", "view details", "shop now", "learn more"
        ]
        
        for node in graph.get_clickable_nodes():
            text_lower = node.text.lower()
            
            # Check CTA patterns
            if any(kw in text_lower for kw in cta_keywords):
                score += 0.3
                candidates.append(node)
                reasoning = f"Found product CTA: '{node.text}'"
        
        # Look for product cards
        product_indicators = [
            n for n in graph.nodes.values()
            if "product" in str(n.attributes.get("class", "")).lower()
            or "item" in str(n.attributes.get("class", "")).lower()
        ]
        
        if product_indicators:
            score += 0.2
            reasoning += f" | {len(product_indicators)} product elements"
        
        # Check URL for product listing indicators
        if any(x in graph.url.lower() for x in ["product", "category", "shop", "collection"]):
            score += 0.2
            reasoning += " | Product listing URL"
        
        return ScoredIntent(
            intent=ActionIntent.SELECT_PRODUCT,
            confidence=min(score, 1.0),
            candidate_nodes=candidates[:10],
            reasoning=reasoning or "No product UI found"
        )
    
    def _score_add_to_cart(
        self, 
        graph: UIGraph, 
        goal: GoalObject, 
        state: SessionState
    ) -> ScoredIntent:
        """Score add to cart intent."""
        score = 0.0
        candidates = []
        reasoning = ""
        
        # Check if on product detail page
        if "product" not in graph.url.lower():
            return ScoredIntent(
                ActionIntent.ADD_TO_CART, 
                0.0, 
                [], 
                "Not on product page"
            )
        
        # Look for add to cart buttons
        cart_keywords = ["add to cart", "add to bag", "add", "buy"]
        
        for node in graph.get_clickable_nodes():
            text_lower = node.text.lower()
            
            if any(kw in text_lower for kw in cart_keywords):
                score += 0.4
                candidates.append(node)
                reasoning = f"Found cart button: '{node.text}'"
        
        return ScoredIntent(
            intent=ActionIntent.ADD_TO_CART,
            confidence=min(score, 1.0),
            candidate_nodes=candidates[:5],
            reasoning=reasoning or "No add to cart button"
        )
    
    def _score_checkout(
        self, 
        graph: UIGraph, 
        goal: GoalObject, 
        state: SessionState
    ) -> ScoredIntent:
        """Score checkout intent."""
        score = 0.0
        candidates = []
        reasoning = ""
        
        # Need purchase goal
        if not goal.complete_purchase:
            return ScoredIntent(ActionIntent.CHECKOUT, 0.0, [], "No purchase goal")
        
        # Already in checkout?
        if "checkout" in graph.url.lower():
            return ScoredIntent(ActionIntent.CHECKOUT, 0.0, [], "Already in checkout")
        
        # Look for cart/checkout buttons
        checkout_keywords = ["checkout", "proceed", "continue", "cart", "basket"]
        
        for node in graph.get_clickable_nodes():
            text_lower = node.text.lower()
            
            if any(kw in text_lower for kw in checkout_keywords):
                score += 0.3
                candidates.append(node)
                reasoning = f"Found checkout button: '{node.text}'"
        
        # Check if cart is visible (indicator we can checkout)
        cart_nodes = [n for n in graph.nodes.values() 
                     if "cart" in n.text.lower() or "cart" in str(n.attributes.get("class", "")).lower()]
        
        if cart_nodes:
            score += 0.2
            reasoning += " | Cart indicator present"
        
        return ScoredIntent(
            intent=ActionIntent.CHECKOUT,
            confidence=min(score, 1.0),
            candidate_nodes=candidates[:5],
            reasoning=reasoning or "No checkout UI"
        )
    
    def _score_fill_form(
        self, 
        graph: UIGraph, 
        goal: GoalObject, 
        state: SessionState
    ) -> ScoredIntent:
        """Score form filling intent."""
        score = 0.0
        candidates = []
        reasoning = ""
        
        # Look for visible form inputs
        inputs = [n for n in graph.nodes.values() 
                 if n.tag == "input" and n.is_visible and n.is_enabled]
        
        if inputs:
            score += 0.3
            candidates.extend(inputs)
            reasoning = f"Found {len(inputs)} form inputs"
        
        # Look for text areas
        textareas = [n for n in graph.nodes.values() 
                    if n.tag == "textarea" and n.is_visible]
        
        if textareas:
            score += 0.2
            candidates.extend(textareas)
            reasoning += f" | {len(textareas)} textareas"
        
        return ScoredIntent(
            intent=ActionIntent.FILL_FORM,
            confidence=min(score, 1.0),
            candidate_nodes=candidates[:10],
            reasoning=reasoning or "No form fields"
        )
    
    def _score_login(
        self, 
        graph: UIGraph, 
        goal: GoalObject, 
        state: SessionState
    ) -> ScoredIntent:
        """Score login intent."""
        score = 0.0
        candidates = []
        reasoning = ""
        
        # Look for login indicators
        login_keywords = ["login", "sign in", "log in", "username", "password"]
        
        for node in graph.nodes.values():
            if not node.is_visible:
                continue
            
            text_lower = node.text.lower()
            
            if any(kw in text_lower for kw in login_keywords):
                score += 0.2
                candidates.append(node)
                reasoning = f"Found login element: '{node.text}'"
        
        # Check for password input
        password_inputs = [n for n in graph.nodes.values() 
                          if n.tag == "input" 
                          and n.attributes.get("type") == "password"]
        
        if password_inputs:
            score += 0.4
            reasoning += " | Password field present"
        
        return ScoredIntent(
            intent=ActionIntent.LOGIN,
            confidence=min(score, 1.0),
            candidate_nodes=candidates[:5],
            reasoning=reasoning or "No login UI"
        )


class IntentDecisionEngine:
    """
    Confidence-based decision engine.
    
    Replaces deterministic rule chains with probabilistic intent matching.
    """
    
    def __init__(self):
        self.scorer = IntentScorer()
        self.exploration_threshold = 0.30  # Below this, enter exploration mode
    
    def decide(
        self, 
        graph: UIGraph, 
        goal: GoalObject, 
        state: SessionState
    ) -> IntentAction:
        """
        Decide next action based on intent confidence scores.
        
        Returns:
            IntentAction with highest confidence, or EXPLORE if all below threshold.
        """
        # Score all intents
        scored_intents = self.scorer.score_all_intents(graph, goal, state)
        
        # Get best intent
        best = scored_intents[0] if scored_intents else None
        
        if not best:
            logger.warning("⚠️ No intents scored - entering exploration")
            return self._create_exploration_action(graph, state)
        
        # Check confidence threshold
        if best.confidence < self.exploration_threshold:
            logger.info(f"🔍 Low confidence ({best.confidence:.2f}) - entering exploration")
            return self._create_exploration_action(graph, state)
        
        # Select target node
        target_node = best.candidate_nodes[0] if best.candidate_nodes else None
        
        # Create action
        action = IntentAction(
            intent=best.intent,
            confidence=best.confidence,
            target_node=target_node,
            params=self._extract_params(best, goal),
            reasoning=best.reasoning
        )
        
        logger.info(
            f"🎯 Decided: {action.intent.value} "
            f"(confidence={action.confidence:.2f}) - {action.reasoning}"
        )
        
        return action
    
    def _create_exploration_action(
        self, 
        graph: UIGraph, 
        state: SessionState
    ) -> IntentAction:
        """
        Create exploration action when confidence is low.
        
        Tries to click highest unvisited interactive element.
        """
        # Get unvisited clickable nodes
        clickable = [n for n in graph.get_clickable_nodes() 
                    if n.id not in self.scorer.visited_nodes]
        
        if not clickable:
            logger.warning("⚠️ No unvisited nodes - deadlock risk")
            # Reset visited and try again
            self.scorer.visited_nodes.clear()
            clickable = graph.get_clickable_nodes()
        
        # Pick first visible clickable element
        target = clickable[0] if clickable else None
        
        if target:
            self.scorer.visited_nodes.add(target.id)
        
        return IntentAction(
            intent=ActionIntent.EXPLORE,
            confidence=0.25,
            target_node=target,
            params={},
            reasoning=f"Exploration: click '{target.text if target else 'unknown'}'"
        )
    
    def _extract_params(self, scored: ScoredIntent, goal: GoalObject) -> Dict[str, any]:
        """Extract execution parameters for intent."""
        params = {}
        
        if scored.intent == ActionIntent.SEARCH:
            params["query"] = goal.search_query
        
        elif scored.intent == ActionIntent.SELECT_PRODUCT:
            params["price_max"] = goal.price_max
            params["price_min"] = goal.price_min
        
        elif scored.intent == ActionIntent.CHECKOUT:
            params["mode"] = goal.checkout_mode
        
        return params
