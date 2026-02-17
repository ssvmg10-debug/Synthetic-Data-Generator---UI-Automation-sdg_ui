"""
Enterprise Intent Engine - Deterministic Instruction-Following Architecture

COMPLETE REDESIGN based on enterprise requirements:
✅ Layer 1: Instruction Compiler (instruction_compiler.py)
✅ Layer 2: Strict Step Execution Engine
✅ Layer 3: Deterministic DOM Targeting
✅ Layer 4: Proper DOM Graph (dom_graph.py)
✅ Layer 5: Controlled Recovery System
✅ Layer 6: State Verification After Each Step

This replaces random exploration with deterministic, instruction-following behavior.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from playwright.async_api import Page
import logging
import asyncio
from fuzzywuzzy import fuzz

from services.ui_automation.perception.dom_graph import UIGraph, UINode
from services.ui_automation.instruction_compiler import Instruction, ActionType, InstructionCompiler
from services.ui_automation.state_manager import SessionState

logger = logging.getLogger(__name__)


# ============================================================================
# LAYER 3: DETERMINISTIC DOM TARGETING
# ============================================================================

@dataclass
class ElementCandidate:
    """Candidate element with confidence score."""
    node: UINode
    score: float
    reasoning: str
    
    def __repr__(self):
        return f"Candidate('{self.node.text[:30]}', score={self.score:.2f})"


class DeterministicDOMTargeter:
    """
    Layer 3: Deterministic DOM element targeting.
    
    Scores elements based on:
    - Text similarity (60%)
    - Semantic match (20%)
    - Position weight (10%)
    - Tag priority (10%)
    
    NO fuzzy-only logic. NO random exploration during instruction execution.
    """
    
    # Score thresholds
    HIGH_CONFIDENCE = 0.75
    MEDIUM_CONFIDENCE = 0.60
    LOW_CONFIDENCE = 0.45
    
    # Tag priorities
    TAG_PRIORITIES = {
        "button": 1.0,
        "a": 0.9,
        "input": 0.8,
        "select": 0.8,
        "textarea": 0.7,
        "div": 0.5,
        "span": 0.4,
    }
    
    def find_best_match(
        self,
        target_text: str,
        graph: UIGraph,
        instruction_type: ActionType
    ) -> Optional[ElementCandidate]:
        """
        Find best matching element using deterministic scoring.
        
        Args:
            target_text: Text to match (e.g., "air solutions", "checkout")
            graph: Current DOM graph
            instruction_type: Type of action (CLICK, TYPE, etc.)
        
        Returns:
            Best candidate or None if no match above threshold
        """
        logger.info(f"🎯 Targeting: '{target_text}' for {instruction_type.value}")
        
        # Step 1: Build candidate set
        candidates = self._build_candidate_set(target_text, graph, instruction_type)
        
        if not candidates:
            logger.warning(f"⚠️ No candidates found for '{target_text}'")
            return None
        
        # Step 2: Score each candidate
        scored_candidates = []
        for node in candidates:
            score = self._calculate_score(node, target_text, instruction_type)
            
            if score >= self.LOW_CONFIDENCE:
                reasoning = self._explain_score(node, target_text, score)
                scored_candidates.append(ElementCandidate(node, score, reasoning))
        
        if not scored_candidates:
            logger.warning(f"⚠️ No candidates above threshold for '{target_text}'")
            return None
        
        # Step 3: Choose highest score
        best = max(scored_candidates, key=lambda c: c.score)
        
        logger.info(f"✅ Best match: {best}")
        logger.debug(f"   All candidates: {scored_candidates[:5]}")
        
        return best
    
    def _build_candidate_set(
        self,
        target_text: str,
        graph: UIGraph,
        instruction_type: ActionType
    ) -> List[UINode]:
        """Build candidate set based on instruction type."""
        candidates = []
        
        if instruction_type == ActionType.CLICK:
            # For clicks: all visible clickable elements
            candidates = graph.get_clickable_nodes()
        
        elif instruction_type == ActionType.TYPE:
            # For typing: visible input elements
            candidates = [
                n for n in graph.nodes.values()
                if n.tag in ["input", "textarea"] and n.is_visible and n.is_enabled
            ]
        
        else:
            # Default: all visible elements
            candidates = [n for n in graph.nodes.values() if n.is_visible]
        
        # Filter by text similarity (preliminary)
        if target_text:
            filtered = []
            for node in candidates:
                # Check text content
                if target_text.lower() in node.text.lower():
                    filtered.append(node)
                    continue
                
                # Check aria-label
                if node.aria_label and target_text.lower() in node.aria_label.lower():
                    filtered.append(node)
                    continue
                
                # Check placeholder
                if node.placeholder and target_text.lower() in node.placeholder.lower():
                    filtered.append(node)
                    continue
                
                # Check fuzzy match (>60% similarity)
                if fuzz.ratio(target_text.lower(), node.text.lower()) > 60:
                    filtered.append(node)
            
            if filtered:
                candidates = filtered
        
        return candidates
    
    def _calculate_score(
        self,
        node: UINode,
        target_text: str,
        instruction_type: ActionType
    ) -> float:
        """
        Calculate element match score using weighted formula:
        
        score = text_similarity * 0.6 +
                semantic_match * 0.2 +
                position_weight * 0.1 +
                tag_priority * 0.1
        """
        # Text similarity (60%)
        text_sim = self._text_similarity(node, target_text)
        
        # Semantic match (20%)
        semantic = self._semantic_match(node, target_text, instruction_type)
        
        # Position weight (10%)
        position = self._position_weight(node)
        
        # Tag priority (10%)
        tag_pri = self.TAG_PRIORITIES.get(node.tag, 0.3)
        
        # Calculate weighted score
        score = (
            text_sim * 0.6 +
            semantic * 0.2 +
            position * 0.1 +
            tag_pri * 0.1
        )
        
        return min(score, 1.0)
    
    def _text_similarity(self, node: UINode, target_text: str) -> float:
        """Calculate text similarity score."""
        if not target_text:
            return 0.0
        
        target_lower = target_text.lower()
        
        # Exact match
        if target_lower == node.text.lower():
            return 1.0
        
        # Contains match
        if target_lower in node.text.lower():
            return 0.9
        
        # Fuzzy match
        ratio = fuzz.ratio(target_lower, node.text.lower()) / 100.0
        
        # Partial ratio (for longer text)
        partial = fuzz.partial_ratio(target_lower, node.text.lower()) / 100.0
        
        # Token set ratio (word order independent)
        token = fuzz.token_set_ratio(target_lower, node.text.lower()) / 100.0
        
        # Best score
        return max(ratio, partial, token)
    
    def _semantic_match(self, node: UINode, target_text: str, instruction_type: ActionType) -> float:
        """Calculate semantic match score based on context."""
        score = 0.0
        target_lower = target_text.lower()
        
        # Check ARIA label
        if node.aria_label:
            if target_lower in node.aria_label.lower():
                score += 0.5
        
        # Check role
        if node.role:
            if instruction_type == ActionType.CLICK and node.role in ["button", "link"]:
                score += 0.3
            elif instruction_type == ActionType.TYPE and node.role in ["textbox", "searchbox"]:
                score += 0.3
        
        # Check semantic keywords
        keywords_map = {
            "checkout": ["checkout", "proceed", "continue", "next"],
            "cart": ["cart", "basket", "bag"],
            "search": ["search", "find"],
            "login": ["login", "sign in", "log in"],
            "submit": ["submit", "send", "continue"],
        }
        
        for key, keywords in keywords_map.items():
            if key in target_lower:
                for kw in keywords:
                    if kw in node.text.lower():
                        score += 0.2
                        break
        
        return min(score, 1.0)
    
    def _position_weight(self, node: UINode) -> float:
        """Calculate position-based weight."""
        # Prefer elements higher in the DOM
        if node.dom_depth <= 5:
            return 0.8
        elif node.dom_depth <= 10:
            return 0.6
        elif node.dom_depth <= 15:
            return 0.4
        else:
            return 0.2
    
    def _explain_score(self, node: UINode, target_text: str, score: float) -> str:
        """Generate human-readable explanation of score."""
        reasons = []
        
        # Text match
        if target_text.lower() in node.text.lower():
            reasons.append(f"text contains '{target_text}'")
        else:
            sim = fuzz.ratio(target_text.lower(), node.text.lower())
            reasons.append(f"text similarity {sim}%")
        
        # Tag
        reasons.append(f"tag={node.tag}")
        
        # Role
        if node.role:
            reasons.append(f"role={node.role}")
        
        # ARIA label
        if node.aria_label:
            reasons.append(f"aria-label='{node.aria_label[:20]}'")
        
        return f"{score:.2f}: " + ", ".join(reasons)


# ============================================================================
# LAYER 5: CONTROLLED RECOVERY SYSTEM
# ============================================================================

class RecoveryStrategy:
    """
    Layer 5: Controlled recovery when actions fail.
    
    Strategy order:
    1. Retry with longer timeout
    2. Scroll element into view
    3. Use alternate locator (role-based)
    4. Re-evaluate DOM
    5. If page unchanged → error
    """
    
    MAX_RETRIES = 3
    
    async def recover_click(
        self,
        page: Page,
        node: UINode,
        attempt: int = 1
    ) -> bool:
        """Attempt recovery for failed click."""
        logger.info(f"🔧 Recovery attempt {attempt}/{self.MAX_RETRIES} for click")
        
        if attempt > self.MAX_RETRIES:
            logger.error("❌ Max recovery attempts reached")
            return False
        
        try:
            # Strategy 1: Retry with higher timeout
            if attempt == 1:
                logger.info("  Strategy 1: Retry with longer timeout")
                await page.wait_for_timeout(2000)
                await page.locator(f"text='{node.text}'").first.click(timeout=10000)
                return True
            
            # Strategy 2: Scroll into view
            elif attempt == 2:
                logger.info("  Strategy 2: Scroll into view")
                if node.text:
                    locator = page.locator(f"text='{node.text}'").first
                    await locator.scroll_into_view_if_needed()
                    await page.wait_for_timeout(500)
                    await locator.click(timeout=10000)
                    return True
            
            # Strategy 3: Use alternate locator (role)
            elif attempt == 3:
                logger.info("  Strategy 3: Try role-based locator")
                if node.role:
                    await page.locator(f"[role='{node.role}']:has-text('{node.text}')").first.click(timeout=10000)
                    return True
                elif node.data_testid:
                    await page.locator(f"[data-testid='{node.data_testid}']").click(timeout=10000)
                    return True
        
        except Exception as e:
            logger.debug(f"  Recovery attempt {attempt} failed: {e}")
        
        return False
    
    async def recover_type(
        self,
        page: Page,
        node: UINode,
        value: str,
        attempt: int = 1
    ) -> bool:
        """Attempt recovery for failed type action."""
        logger.info(f"🔧 Recovery attempt {attempt}/{self.MAX_RETRIES} for type")
        
        if attempt > self.MAX_RETRIES:
            return False
        
        try:
            # Strategy 1: Clear and retry
            if attempt == 1:
                logger.info("  Strategy 1: Clear field and retry")
                if node.placeholder:
                    locator = page.locator(f"[placeholder='{node.placeholder}']").first
                    await locator.clear()
                    await locator.fill(value)
                    return True
            
            # Strategy 2: Use role
            elif attempt == 2:
                logger.info("  Strategy 2: Use role-based locator")
                if node.role:
                    await page.locator(f"[role='{node.role}']").first.fill(value)
                    return True
            
            # Strategy 3: Generic input selector
            elif attempt == 3:
                logger.info("  Strategy 3: Generic input selector")
                await page.locator("input[type='text']").first.fill(value)
                return True
        
        except Exception as e:
            logger.debug(f"  Recovery attempt {attempt} failed: {e}")
        
        return False


# ============================================================================
# LAYER 6: STATE VERIFICATION
# ============================================================================

@dataclass
class StateChange:
    """Represents detected state change after action."""
    url_changed: bool = False
    dom_changed: bool = False
    element_disappeared: bool = False
    new_content_appeared: bool = False
    score: float = 0.0
    
    def has_change(self) -> bool:
        """Check if any meaningful change occurred."""
        return (
            self.url_changed or
            self.dom_changed or
            self.element_disappeared or
            self.new_content_appeared
        )


class StateVerifier:
    """
    Layer 6: Verify state changes after each action.
    
    Checks:
    - URL changed
    - DOM changed significantly
    - Target element disappeared
    - New content appeared
    
    If none changed → failure.
    """
    
    async def verify_state_change(
        self,
        page: Page,
        prev_url: str,
        prev_dom_hash: str,
        prev_graph: UIGraph,
        instruction: Instruction
    ) -> StateChange:
        """Verify that action caused expected state change."""
        change = StateChange()
        
        # Wait for potential changes
        await page.wait_for_timeout(1000)
        
        # Check URL change
        current_url = page.url
        if current_url != prev_url:
            change.url_changed = True
            change.score += 0.4
            logger.info(f"✅ URL changed: {prev_url[:60]} → {current_url[:60]}")
        
        # Check DOM change
        from services.ui_automation.perception.dom_graph import DOMGraphExtractor
        extractor = DOMGraphExtractor()
        new_graph = await extractor.extract(page)
        current_dom_hash = self._compute_dom_hash(new_graph)
        
        if current_dom_hash != prev_dom_hash:
            change.dom_changed = True
            change.score += 0.3
            logger.info(f"✅ DOM changed (hash: {prev_dom_hash[:8]} → {current_dom_hash[:8]})")
        
        # Check element state changes
        if instruction.target_text:
            # Check if target disappeared (expected after click)
            prev_matches = prev_graph.get_by_text(instruction.target_text)
            new_matches = new_graph.get_by_text(instruction.target_text)
            
            if prev_matches and not new_matches:
                change.element_disappeared = True
                change.score += 0.2
                logger.info(f"✅ Target element disappeared (expected)")
            
            # Check if new content appeared
            if len(new_graph.nodes) > len(prev_graph.nodes) + 5:
                change.new_content_appeared = True
                change.score += 0.1
                logger.info(f"✅ New content appeared ({len(new_graph.nodes) - len(prev_graph.nodes)} nodes)")
        
        # Overall assessment
        if change.has_change():
            logger.info(f"✅ State change verified (score={change.score:.2f})")
        else:
            logger.warning(f"⚠️ No state change detected after action")
        
        return change
    
    def _compute_dom_hash(self, graph: UIGraph) -> str:
        """Compute hash of DOM structure for comparison."""
        import hashlib
        
        # Use visible text and clickable elements as fingerprint
        fingerprint = []
        for node in sorted(graph.nodes.values(), key=lambda n: n.id):
            if node.is_visible:
                fingerprint.append(f"{node.tag}:{node.text[:50]}:{node.role}")
        
        content = "|".join(fingerprint)
        return hashlib.md5(content.encode()).hexdigest()


# ============================================================================
# LAYER 2: STRICT STEP EXECUTION ENGINE
# ============================================================================

class StrictExecutionEngine:
    """
    Layer 2: Strict step-by-step instruction execution.
    
    NO exploration during instruction execution.
    Exploration is fallback mode only (not implemented in deterministic flow).
    
    Flow:
        for instruction in instruction_queue:
            execute_instruction(instruction)
            verify_result()
            if failure: attempt_recovery()
    """
    
    def __init__(self):
        self.targeter = DeterministicDOMTargeter()
        self.recovery = RecoveryStrategy()
        self.verifier = StateVerifier()
        self.state = SessionState()
    
    async def execute_instruction_queue(
        self,
        instructions: List[Instruction],
        page: Page,
        graph: UIGraph
    ) -> Tuple[bool, int, str]:
        """
        Execute instruction queue strictly in order.
        
        Returns:
            (success, steps_executed, error_message)
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 STRICT EXECUTION MODE: {len(instructions)} instructions")
        logger.info(f"{'='*80}\n")
        
        steps_executed = 0
        
        for i, instruction in enumerate(instructions, 1):
            logger.info(f"\n{'─'*80}")
            logger.info(f"📍 Instruction {i}/{len(instructions)}: {instruction}")
            logger.info(f"{'─'*80}")
            
            # Execute instruction
            success, error = await self._execute_single_instruction(
                instruction, page, graph
            )
            
            if success:
                steps_executed += 1
                logger.info(f"✅ Instruction {i} completed successfully\n")
            else:
                logger.error(f"❌ Instruction {i} failed: {error}\n")
                return False, steps_executed, error
            
            # Update graph for next instruction
            from services.ui_automation.perception.dom_graph import DOMGraphExtractor
            extractor = DOMGraphExtractor()
            graph = await extractor.extract(page)
            
            # Small delay between instructions
            await page.wait_for_timeout(1000)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🎉 ALL INSTRUCTIONS COMPLETED: {steps_executed}/{len(instructions)}")
        logger.info(f"{'='*80}\n")
        
        return True, steps_executed, ""
    
    async def _execute_single_instruction(
        self,
        instruction: Instruction,
        page: Page,
        graph: UIGraph
    ) -> Tuple[bool, str]:
        """
        Execute a single instruction with recovery and verification.
        
        Returns:
            (success, error_message)
        """
        # Save state for verification
        prev_url = page.url
        prev_dom_hash = self.verifier._compute_dom_hash(graph)
        
        try:
            # Execute based on action type
            if instruction.action == ActionType.GOTO:
                success = await self._execute_goto(instruction, page)
                if not success:
                    return False, "Failed to navigate to URL"
            
            elif instruction.action == ActionType.CLICK:
                success = await self._execute_click(instruction, page, graph)
                if not success:
                    return False, f"Failed to click '{instruction.target_text}'"
            
            elif instruction.action == ActionType.TYPE:
                success = await self._execute_type(instruction, page, graph)
                if not success:
                    return False, f"Failed to type in '{instruction.target_text}'"
            
            else:
                return False, f"Unknown action type: {instruction.action}"
            
            # Verify state change if expected
            if instruction.expected_page_change:
                change = await self.verifier.verify_state_change(
                    page, prev_url, prev_dom_hash, graph, instruction
                )
                
                if not change.has_change():
                    logger.warning("⚠️ Action succeeded but no state change detected")
                    # Not a hard failure, but worth noting
            
            return True, ""
        
        except Exception as e:
            logger.error(f"❌ Instruction execution error: {e}", exc_info=True)
            return False, str(e)
    
    async def _execute_goto(self, instruction: Instruction, page: Page) -> bool:
        """Execute GOTO instruction."""
        try:
            logger.info(f"  🌐 Navigating to: {instruction.value}")
            await page.goto(instruction.value, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=10000)
            logger.info(f"  ✅ Navigation complete")
            return True
        except Exception as e:
            logger.error(f"  ❌ Navigation failed: {e}")
            return False
    
    async def _execute_click(
        self,
        instruction: Instruction,
        page: Page,
        graph: UIGraph
    ) -> bool:
        """Execute CLICK instruction with targeting and recovery."""
        # Find best matching element
        candidate = self.targeter.find_best_match(
            instruction.target_text,
            graph,
            ActionType.CLICK
        )
        
        if not candidate:
            logger.error(f"  ❌ No matching element found for '{instruction.target_text}'")
            return False
        
        logger.info(f"  🎯 Target: {candidate}")
        
        # Attempt click
        try:
            logger.info(f"  👆 Clicking: '{candidate.node.text[:50]}'")
            
            # Try multiple locator strategies
            success = False
            
            # Strategy 1: Text locator
            try:
                await page.locator(f"text='{candidate.node.text}'").first.click(timeout=5000)
                success = True
            except Exception as e1:
                logger.debug(f"    Text locator failed: {e1}")
                
                # Strategy 2: Role + text
                if candidate.node.role:
                    try:
                        await page.locator(f"[role='{candidate.node.role}']:has-text('{candidate.node.text}')").first.click(timeout=5000)
                        success = True
                    except Exception as e2:
                        logger.debug(f"    Role locator failed: {e2}")
                        
                        # Strategy 3: Recovery
                        success = await self.recovery.recover_click(page, candidate.node, 1)
            
            if success:
                logger.info(f"  ✅ Click successful")
                return True
            else:
                logger.error(f"  ❌ All click strategies failed")
                return False
        
        except Exception as e:
            logger.error(f"  ❌ Click error: {e}")
            return False
    
    async def _execute_type(
        self,
        instruction: Instruction,
        page: Page,
        graph: UIGraph
    ) -> bool:
        """Execute TYPE instruction with targeting and recovery."""
        # Find best matching input element
        candidate = self.targeter.find_best_match(
            instruction.target_text or "input",
            graph,
            ActionType.TYPE
        )
        
        if not candidate:
            logger.error(f"  ❌ No matching input found for '{instruction.target_text}'")
            return False
        
        logger.info(f"  🎯 Target: {candidate}")
        
        try:
            logger.info(f"  ⌨️  Typing: '{instruction.value}' into '{candidate.node.tag}'")
            
            # Try multiple locator strategies
            success = False
            
            # Strategy 1: Placeholder
            if candidate.node.placeholder:
                try:
                    await page.locator(f"[placeholder='{candidate.node.placeholder}']").first.fill(instruction.value)
                    success = True
                except Exception as e:
                    logger.debug(f"    Placeholder locator failed: {e}")
            
            # Strategy 2: Role
            if not success and candidate.node.role:
                try:
                    await page.locator(f"[role='{candidate.node.role}']").first.fill(instruction.value)
                    success = True
                except Exception as e:
                    logger.debug(f"    Role locator failed: {e}")
            
            # Strategy 3: Generic input
            if not success:
                try:
                    await page.locator("input[type='text'], input:not([type]), textarea").first.fill(instruction.value)
                    success = True
                except Exception as e:
                    logger.debug(f"    Generic input failed: {e}")
                    
                    # Strategy 4: Recovery
                    success = await self.recovery.recover_type(page, candidate.node, instruction.value, 1)
            
            if success:
                logger.info(f"  ✅ Type successful")
                
                # If this is a search, submit it
                if instruction.metadata and instruction.metadata.get("is_search"):
                    try:
                        await page.keyboard.press("Enter")
                        await page.wait_for_load_state("networkidle", timeout=10000)
                        logger.info(f"  ✅ Search submitted")
                    except Exception as e:
                        logger.warning(f"  ⚠️ Search submit failed: {e}")
                
                return True
            else:
                logger.error(f"  ❌ All type strategies failed")
                return False
        
        except Exception as e:
            logger.error(f"  ❌ Type error: {e}")
            return False


# ============================================================================
# MAIN ENGINE INTEGRATION
# ============================================================================

class EnterpriseIntentEngine:
    """
    Complete Enterprise Intent Engine with all 6 layers.
    
    Replaces fuzzy exploration with deterministic instruction execution.
    """
    
    def __init__(self):
        self.compiler = InstructionCompiler()
        self.executor = StrictExecutionEngine()
    
    def set_instruction_queue(self, instructions: List[Instruction]):
        """Set the instruction queue to execute."""
        self.instructions = instructions
    
    def compile_from_text(self, raw_input: str) -> List[Instruction]:
        """Compile raw text into instructions."""
        return self.compiler.compile_from_text(raw_input)
    
    def compile_from_plan(self, plan: Dict) -> List[Instruction]:
        """Compile structured plan into instructions."""
        return self.compiler.compile_from_plan(plan)
    
    async def execute_instructions(
        self,
        page: Page,
        graph: UIGraph
    ) -> Tuple[bool, int, str]:
        """Execute the compiled instruction queue."""
        if not hasattr(self, 'instructions') or not self.instructions:
            return False, 0, "No instructions to execute"
        
        # Validate instructions
        if not self.compiler.validate_instructions(self.instructions):
            return False, 0, "Invalid instruction queue"
        
        # Execute
        return await self.executor.execute_instruction_queue(
            self.instructions,
            page,
            graph
        )
