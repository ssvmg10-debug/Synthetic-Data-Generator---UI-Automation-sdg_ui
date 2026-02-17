"""
Deadlock Breaker & Exploration Engine

Prevents infinite loops and idle states with intelligent exploration.
Enterprise-grade stability mechanism.
"""

from dataclasses import dataclass
from typing import List, Optional, Set, Dict, Any
from services.ui_automation.perception.dom_graph import UINode, UIGraph
from services.ui_automation.state_manager import SessionState
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class StateSignature:
    """
    Signature representing unique page state.
    Used to detect when we're stuck in same state.
    """
    url: str
    clickable_count: int
    visible_text_hash: int
    timestamp: datetime
    
    def __eq__(self, other):
        return (
            self.url == other.url and 
            self.clickable_count == other.clickable_count and
            self.visible_text_hash == other.visible_text_hash
        )
    
    def __hash__(self):
        return hash((self.url, self.clickable_count, self.visible_text_hash))


class DeadlockBreaker:
    """
    Detects and breaks deadlock situations.
    
    Prevents infinite loops when:
    - No state change for N iterations
    - Revisiting same state repeatedly
    - All actions failing
    """
    
    # Thresholds
    NO_PROGRESS_THRESHOLD = 3  # Iterations without state change
    SAME_STATE_THRESHOLD = 2   # Times visiting same state
    MAX_FAILED_ACTIONS = 5     # Consecutive failed actions
    
    def __init__(self):
        self.state_history: List[StateSignature] = []
        self.visited_states: Set[StateSignature] = set()
        self.no_progress_count = 0
        self.failed_action_count = 0
        self.last_url: Optional[str] = None
    
    def check_for_deadlock(
        self, 
        graph: UIGraph, 
        state: SessionState
    ) -> Optional[str]:
        """
        Check if system is in deadlock.
        
        Returns:
            Deadlock reason if detected, None otherwise.
        """
        # Create current state signature
        current_sig = self._create_signature(graph)
        
        # Check 1: No URL change for too long
        if self.last_url and self.last_url == graph.url:
            self.no_progress_count += 1
        else:
            self.no_progress_count = 0
            self.last_url = graph.url
        
        if self.no_progress_count >= self.NO_PROGRESS_THRESHOLD:
            return f"No state change for {self.no_progress_count} iterations"
        
        # Check 2: Revisiting same state
        if current_sig in self.visited_states:
            # Count how many times we've seen this state
            revisit_count = sum(1 for s in self.state_history if s == current_sig)
            
            if revisit_count >= self.SAME_STATE_THRESHOLD:
                return f"Stuck in same state (visited {revisit_count} times)"
        
        # Check 3: Too many failed actions
        if self.failed_action_count >= self.MAX_FAILED_ACTIONS:
            return f"Too many failed actions ({self.failed_action_count})"
        
        # Update history
        self.state_history.append(current_sig)
        self.visited_states.add(current_sig)
        
        # Trim history to last 10 states
        if len(self.state_history) > 10:
            self.state_history = self.state_history[-10:]
        
        return None
    
    def record_action_result(self, success: bool):
        """Record whether last action succeeded."""
        if success:
            self.failed_action_count = 0
        else:
            self.failed_action_count += 1
    
    def get_recovery_action(self) -> str:
        """
        Get recovery action to break deadlock.
        
        Returns:
            Recovery strategy name.
        """
        # Strategy 1: Go back
        if self.no_progress_count >= self.NO_PROGRESS_THRESHOLD:
            return "navigate_back"
        
        # Strategy 2: Force exploration
        if self.failed_action_count >= 3:
            return "force_exploration"
        
        # Strategy 3: Restart from homepage
        if len(self.state_history) > 8:
            return "restart_homepage"
        
        return "force_exploration"
    
    def reset(self):
        """Reset deadlock state."""
        self.no_progress_count = 0
        self.failed_action_count = 0
    
    def _create_signature(self, graph: UIGraph) -> StateSignature:
        """Create unique signature for current state."""
        # Count clickable elements
        clickable_count = len(graph.get_clickable_nodes())
        
        # Hash visible text (simple approach)
        visible_texts = [n.text for n in graph.nodes.values() if n.is_visible and n.text]
        text_hash = hash(tuple(sorted(visible_texts[:50])))  # Limit to first 50
        
        return StateSignature(
            url=graph.url,
            clickable_count=clickable_count,
            visible_text_hash=text_hash,
            timestamp=datetime.utcnow()
        )


class ExplorationEngine:
    """
    Intelligent exploration when primary intents fail.
    
    Tries to discover new areas of the application systematically.
    """
    
    def __init__(self):
        self.visited_nodes: Set[str] = set()
        self.exploration_history: List[Dict] = []
    
    def explore(self, graph: UIGraph) -> Optional[UINode]:
        """
        Find next node to explore.
        
        Strategy:
        1. Try high-priority unvisited nodes (navigation, menu items)
        2. Try visible buttons not yet clicked
        3. Try scrolling to reveal more content
        4. Try expanding collapsed sections
        
        Returns:
            Node to click, or None if exhausted
        """
        logger.info("🔍 Entering exploration mode")
        
        # Get all clickable nodes
        candidates = graph.get_clickable_nodes()
        
        # Filter to unvisited
        unvisited = [n for n in candidates if n.id not in self.visited_nodes]
        
        if not unvisited:
            logger.warning("⚠️ All nodes visited - resetting exploration")
            self.visited_nodes.clear()
            unvisited = candidates
        
        if not unvisited:
            return None
        
        # Prioritize by type
        node = self._prioritize_exploration_target(unvisited)
        
        if node:
            self.visited_nodes.add(node.id)
            logger.info(f"🔍 Exploring: '{node.text[:40]}' ({node.tag})")
        
        return node
    
    def _prioritize_exploration_target(self, nodes: List[UINode]) -> Optional[UINode]:
        """
        Prioritize exploration targets.
        
        Order:
        1. Navigation links (nav, menu)
        2. Prominent buttons (large, centered)
        3. Links with meaningful text
        4. Any other clickable element
        """
        # Priority 1: Navigation elements
        nav_nodes = [n for n in nodes if n.role == "navigation" or "nav" in n.tag]
        if nav_nodes:
            return nav_nodes[0]
        
        # Priority 2: Buttons with action words
        action_keywords = ["view", "see", "browse", "explore", "shop", "learn"]
        action_buttons = [
            n for n in nodes 
            if n.tag == "button" and any(kw in n.text.lower() for kw in action_keywords)
        ]
        if action_buttons:
            return action_buttons[0]
        
        # Priority 3: Links with substantial text
        substantial_links = [
            n for n in nodes 
            if n.tag == "a" and len(n.text) > 3
        ]
        if substantial_links:
            return substantial_links[0]
        
        # Priority 4: Any button
        buttons = [n for n in nodes if n.tag == "button"]
        if buttons:
            return buttons[0]
        
        # Priority 5: Any clickable
        return nodes[0] if nodes else None
    
    def should_stop_exploration(self, iterations: int) -> bool:
        """Check if we should stop exploring."""
        # Stop after 5 exploration attempts
        return iterations >= 5


class StabilityMonitor:
    """
    Monitors overall execution stability.
    
    Provides health metrics and warnings.
    """
    
    def __init__(self):
        self.total_actions = 0
        self.successful_actions = 0
        self.failed_actions = 0
        self.deadlock_recoveries = 0
        self.exploration_count = 0
        self.start_time = datetime.utcnow()
    
    def record_action(self, success: bool, is_exploration: bool = False):
        """Record action result."""
        self.total_actions += 1
        
        if success:
            self.successful_actions += 1
        else:
            self.failed_actions += 1
        
        if is_exploration:
            self.exploration_count += 1
    
    def record_deadlock_recovery(self):
        """Record deadlock recovery attempt."""
        self.deadlock_recoveries += 1
    
    def get_health_score(self) -> float:
        """
        Get overall health score (0.0 to 1.0).
        
        Considers:
        - Success rate
        - Deadlock frequency
        - Exploration frequency
        """
        if self.total_actions == 0:
            return 1.0
        
        success_rate = self.successful_actions / self.total_actions
        deadlock_penalty = min(0.3, self.deadlock_recoveries * 0.1)
        exploration_penalty = min(0.2, self.exploration_count * 0.05)
        
        health = success_rate - deadlock_penalty - exploration_penalty
        return max(0.0, min(1.0, health))
    
    def get_metrics(self) -> Dict[str, any]:
        """Get execution metrics."""
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        
        return {
            "total_actions": self.total_actions,
            "successful_actions": self.successful_actions,
            "failed_actions": self.failed_actions,
            "success_rate": self.successful_actions / max(1, self.total_actions),
            "deadlock_recoveries": self.deadlock_recoveries,
            "exploration_count": self.exploration_count,
            "health_score": self.get_health_score(),
            "elapsed_seconds": elapsed,
            "actions_per_minute": (self.total_actions / elapsed) * 60 if elapsed > 0 else 0
        }
    
    def should_abort(self) -> Optional[str]:
        """Check if execution should abort."""
        # Abort if health too low
        if self.get_health_score() < 0.2:
            return "Health score too low"
        
        # Abort if too many deadlocks
        if self.deadlock_recoveries > 5:
            return "Too many deadlock recoveries"
        
        # Abort if stuck in exploration
        if self.exploration_count > 10:
            return "Excessive exploration attempts"
        
        return None
