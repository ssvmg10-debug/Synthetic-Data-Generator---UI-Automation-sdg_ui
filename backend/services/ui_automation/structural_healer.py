"""
Structural Healing Engine - Enterprise-grade self-healing

Uses DOM structural similarity instead of brittle selector replacement.
Stores successful interaction snapshots and finds similar elements when selectors fail.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from services.ui_automation.perception.dom_graph import UINode, UIGraph
import logging
import difflib

logger = logging.getLogger(__name__)


@dataclass
class NodeSnapshot:
    """
    Snapshot of a successfully clicked UI node.
    Used for structural similarity matching when healing.
    """
    node_id: str
    tag: str
    role: Optional[str]
    text: str
    attributes: Dict[str, str]
    dom_depth: int
    aria_label: Optional[str]
    placeholder: Optional[str]
    parent_context: Dict[str, any]  # Parent/sibling info
    timestamp: datetime
    success_count: int = 1
    
    def to_dict(self) -> dict:
        """Convert to dictionary for database storage."""
        return {
            "node_id": self.node_id,
            "tag": self.tag,
            "role": self.role,
            "text": self.text,
            "attributes": self.attributes,
            "dom_depth": self.dom_depth,
            "aria_label": self.aria_label,
            "placeholder": self.placeholder,
            "parent_context": self.parent_context,
            "timestamp": self.timestamp.isoformat(),
            "success_count": self.success_count
        }


@dataclass
class HealingResult:
    """Result of healing attempt."""
    success: bool
    healed_node: Optional[UINode]
    similarity_score: float
    strategy: str
    reasoning: str


class StructuralHealer:
    """
    Enterprise-grade structural healing engine.
    
    Instead of replacing selectors, finds structurally similar elements
    using comprehensive similarity scoring.
    """
    
    # Similarity thresholds
    HIGH_SIMILARITY = 0.80
    MEDIUM_SIMILARITY = 0.60
    LOW_SIMILARITY = 0.40
    
    def __init__(self):
        self.snapshot_cache: Dict[str, NodeSnapshot] = {}  # In-memory cache
        # TODO: Add database persistence
    
    def store_success(self, node: UINode, graph: UIGraph):
        """
        Store successful interaction snapshot.
        
        Called after every successful action to build healing database.
        """
        try:
            # Get contextual information
            context = graph.get_node_context(node.id, depth=2)
            
            # Create snapshot
            snapshot = NodeSnapshot(
                node_id=node.id,
                tag=node.tag,
                role=node.role,
                text=node.text,
                attributes=node.attributes,
                dom_depth=node.dom_depth,
                aria_label=node.aria_label,
                placeholder=node.placeholder,
                parent_context=context,
                timestamp=datetime.utcnow()
            )
            
            # Store in cache
            cache_key = self._generate_cache_key(node)
            
            if cache_key in self.snapshot_cache:
                # Update success count
                self.snapshot_cache[cache_key].success_count += 1
            else:
                self.snapshot_cache[cache_key] = snapshot
            
            logger.debug(f"✅ Stored snapshot: {node.text[:30]} ({cache_key})")
            
        except Exception as e:
            logger.error(f"❌ Failed to store snapshot: {e}")
    
    def heal(
        self, 
        failed_snapshot: NodeSnapshot, 
        current_graph: UIGraph
    ) -> HealingResult:
        """
        Find structurally similar element in current graph.
        
        Uses comprehensive similarity scoring across multiple dimensions.
        
        Args:
            failed_snapshot: Snapshot of element that failed
            current_graph: Current UI graph to search
        
        Returns:
            HealingResult with best matching node or failure
        """
        logger.info(f"🔧 Healing: Looking for element like '{failed_snapshot.text[:30]}'")
        
        best_match: Optional[Tuple[UINode, float]] = None
        
        # Score all visible clickable nodes
        for node in current_graph.get_clickable_nodes():
            score = self._compute_similarity(failed_snapshot, node, current_graph)
            
            if score > self.LOW_SIMILARITY:
                logger.debug(f"  Candidate: '{node.text[:30]}' (score={score:.2f})")
            
            if best_match is None or score > best_match[1]:
                best_match = (node, score)
        
        if not best_match:
            return HealingResult(
                success=False,
                healed_node=None,
                similarity_score=0.0,
                strategy="structural_similarity",
                reasoning="No similar elements found"
            )
        
        node, score = best_match
        
        # Check if similarity is high enough
        if score < self.LOW_SIMILARITY:
            return HealingResult(
                success=False,
                healed_node=node,
                similarity_score=score,
                strategy="structural_similarity",
                reasoning=f"Best match too dissimilar (score={score:.2f})"
            )
        
        logger.info(
            f"✅ Healed: Found '{node.text[:30]}' "
            f"(similarity={score:.2f})"
        )
        
        return HealingResult(
            success=True,
            healed_node=node,
            similarity_score=score,
            strategy="structural_similarity",
            reasoning=f"Matched on text/role/structure (score={score:.2f})"
        )
    
    def _compute_similarity(
        self, 
        snapshot: NodeSnapshot, 
        node: UINode, 
        graph: UIGraph
    ) -> float:
        """
        Compute comprehensive similarity score.
        
        Scoring dimensions:
        - Text similarity: 40%
        - Role match: 20%
        - Attribute similarity: 20%
        - DOM depth similarity: 10%
        - Parent context similarity: 10%
        """
        score = 0.0
        
        # 1. Text Similarity (40%) - Most important
        text_sim = self._text_similarity(snapshot.text, node.text)
        score += text_sim * 0.40
        
        # 2. Role Match (20%)
        if snapshot.role and node.role and snapshot.role == node.role:
            score += 0.20
        elif not snapshot.role and not node.role:
            score += 0.10  # Both have no role
        
        # 3. Attribute Similarity (20%)
        attr_sim = self._attribute_similarity(snapshot.attributes, node.attributes)
        score += attr_sim * 0.20
        
        # 4. DOM Depth Similarity (10%)
        depth_diff = abs(snapshot.dom_depth - node.dom_depth)
        depth_sim = max(0, 1.0 - (depth_diff * 0.1))  # Penalty for each level difference
        score += depth_sim * 0.10
        
        # 5. Parent Context Similarity (10%)
        # Compare parent/sibling information
        context_sim = self._context_similarity(
            snapshot.parent_context, 
            graph.get_node_context(node.id)
        )
        score += context_sim * 0.10
        
        return min(score, 1.0)
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Compute text similarity using sequence matching.
        
        Handles partial matches and typos.
        """
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0
        
        # Normalize
        t1 = text1.lower().strip()
        t2 = text2.lower().strip()
        
        # Exact match
        if t1 == t2:
            return 1.0
        
        # Substring match
        if t1 in t2 or t2 in t1:
            return 0.8
        
        # Sequence matcher for fuzzy matching
        ratio = difflib.SequenceMatcher(None, t1, t2).ratio()
        return ratio
    
    def _attribute_similarity(self, attrs1: Dict[str, str], attrs2: Dict[str, str]) -> float:
        """
        Compute attribute similarity.
        
        Compares key attributes like class, id, data-testid.
        """
        if not attrs1 and not attrs2:
            return 1.0
        
        score = 0.0
        comparisons = 0
        
        # Compare key attributes
        key_attrs = ["id", "class", "data-testid", "name", "type"]
        
        for attr in key_attrs:
            if attr in attrs1 or attr in attrs2:
                comparisons += 1
                
                val1 = attrs1.get(attr, "")
                val2 = attrs2.get(attr, "")
                
                if val1 == val2:
                    score += 1.0
                elif val1 and val2:
                    # Partial match for class names
                    if attr == "class":
                        classes1 = set(val1.split())
                        classes2 = set(val2.split())
                        overlap = len(classes1 & classes2)
                        if overlap > 0:
                            score += overlap / max(len(classes1), len(classes2))
                    else:
                        # String similarity for other attributes
                        score += self._text_similarity(val1, val2)
        
        return score / comparisons if comparisons > 0 else 0.0
    
    def _context_similarity(self, context1: Dict, context2: Dict) -> float:
        """
        Compare parent/sibling context.
        
        Helps differentiate between similar elements in different parts of page.
        """
        if not context1 or not context2:
            return 0.5  # Neutral if context missing
        
        score = 0.0
        
        # Compare parent information
        parent1 = context1.get("node", {})
        parent2 = context2.get("node", {})
        
        if parent1 and parent2:
            # Compare parent tags
            if parent1.get("tag") == parent2.get("tag"):
                score += 0.3
            
            # Compare parent text
            p1_text = parent1.get("text", "")
            p2_text = parent2.get("text", "")
            if p1_text and p2_text:
                score += self._text_similarity(p1_text, p2_text) * 0.3
        
        # Compare sibling count (structural similarity)
        siblings1 = len(context1.get("siblings", []))
        siblings2 = len(context2.get("siblings", []))
        
        if siblings1 and siblings2:
            sibling_diff = abs(siblings1 - siblings2)
            sibling_sim = max(0, 1.0 - (sibling_diff * 0.1))
            score += sibling_sim * 0.4
        
        return min(score, 1.0)
    
    def _generate_cache_key(self, node: UINode) -> str:
        """Generate cache key for node."""
        # Use combination of tag, role, and text
        return f"{node.tag}:{node.role or 'none'}:{node.text[:50]}"


class HealingMemory:
    """
    Persistent healing memory.
    
    Stores successful healing outcomes to learn over time.
    TODO: Add database persistence and ML ranking.
    """
    
    def __init__(self):
        self.healing_history: List[Dict] = []
    
    def record_healing(
        self, 
        original_snapshot: NodeSnapshot, 
        healed_node: UINode, 
        success: bool, 
        similarity_score: float
    ):
        """
        Record healing outcome.
        
        Used to improve future healing decisions.
        """
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "original": original_snapshot.to_dict(),
            "healed_node_id": healed_node.id if healed_node else None,
            "healed_text": healed_node.text if healed_node else None,
            "success": success,
            "similarity_score": similarity_score
        }
        
        self.healing_history.append(record)
        logger.debug(f"📝 Recorded healing: success={success}, score={similarity_score:.2f}")
    
    def get_best_strategy(self, snapshot: NodeSnapshot) -> Optional[str]:
        """
        Get best healing strategy based on history.
        
        TODO: Implement ML-based strategy selection.
        """
        # For now, always use structural similarity
        return "structural_similarity"
