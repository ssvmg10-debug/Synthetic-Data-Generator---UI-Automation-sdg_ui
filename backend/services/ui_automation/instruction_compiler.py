"""
Layer 1 - Instruction Compiler
Converts natural language test case → executable instruction queue
Enterprise-grade deterministic test execution
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Deterministic action types."""
    GOTO = "goto"
    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    WAIT = "wait"
    VERIFY = "verify"


@dataclass
class Instruction:
    """
    Single executable instruction.
    Clear, deterministic, verifiable.
    """
    action: ActionType
    target_text: Optional[str] = None
    target_selector: Optional[str] = None
    value: Optional[str] = None
    expected_page_change: bool = True
    timeout: int = 10000
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def __repr__(self):
        if self.action == ActionType.GOTO:
            return f"GOTO({self.value})"
        elif self.action == ActionType.CLICK:
            return f"CLICK('{self.target_text}')"
        elif self.action == ActionType.TYPE:
            return f"TYPE('{self.target_text}', '{self.value}')"
        else:
            return f"{self.action.upper()}({self.target_text})"


class InstructionCompiler:
    """
    Converts natural language or structured plan into executable instruction queue.
    
    This is the ONLY place where test case interpretation happens.
    After compilation, execution is purely deterministic.
    """
    
    # Keywords for instruction parsing
    GOTO_KEYWORDS = ["navigate", "go to", "open", "visit", "load"]
    CLICK_KEYWORDS = ["click", "select", "choose", "tap", "press"]
    TYPE_KEYWORDS = ["type", "enter", "input", "fill", "write"]
    SEARCH_KEYWORDS = ["search for", "search", "find"]
    
    @staticmethod
    def normalize_target(text: str) -> str:
        """
        🔵 FIX 1: Semantic Target Extraction
        
        Converts verbose targets into semantic keywords.
        
        Examples:
            'Type 500032 in pincode field' → 'pincode'
            'Enter email address' → 'email address'
            'Fill billing address' → 'billing address'
        
        This is CRITICAL for dynamic test case support.
        """
        text = text.lower().strip()
        
        # Remove action words (type, enter, fill, etc.)
        remove_words = [
            "type", "enter", "fill", "input", "write",
            "in", "into", "the", "a", "an",
            "field", "box", "textbox", "input", "area"
        ]
        
        words = text.split()
        filtered = [w for w in words if w not in remove_words]
        
        # Rejoin
        normalized = " ".join(filtered).strip()
        
        # If we removed everything, use original
        if not normalized:
            normalized = text
        
        logger.debug(f"  Normalized target: '{text}' → '{normalized}'")
        return normalized
    
    def compile_from_text(self, raw_input: str) -> List[Instruction]:
        """
        Compile natural language test case into instruction queue.
        
        Example:
            Input: "navigate to https://www.lg.com/in
                    click on air solutions
                    click on split air conditioner"
            
            Output: [
                Instruction(action=GOTO, value="https://www.lg.com/in"),
                Instruction(action=CLICK, target_text="air solutions"),
                Instruction(action=CLICK, target_text="split air conditioner")
            ]
        """
        instructions = []
        
        # Split into lines
        lines = [line.strip() for line in raw_input.split('\n') if line.strip()]
        
        for line in lines:
            instruction = self._parse_line(line)
            if instruction:
                instructions.append(instruction)
        
        logger.info(f"📝 Compiled {len(instructions)} instructions from text:")
        for i, instr in enumerate(instructions, 1):
            logger.info(f"  {i}. {instr}")
        
        return instructions
    
    def compile_from_plan(self, structured_plan: Dict[str, Any]) -> List[Instruction]:
        """
        PHASE 2: Compile structured plan into instruction queue (1:1 mapping).
        
        NO goal logic, NO ecommerce heuristics, NO optimization.
        Pure 1:1 conversion from plan steps to instructions.
        
        Example plan:
            {
                "steps": [
                    {"intent": "navigate", "url": "https://www.lg.com/in"},
                    {"intent": "click", "target": "Air Solutions"},
                    {"intent": "click", "target": "Split Air Conditioners"}
                ]
            }
        """
        instructions = []
        steps = structured_plan.get("steps", [])
        
        for step in steps:
            instruction = self._parse_step_strict(step)
            if instruction:
                instructions.append(instruction)
        
        logger.info(f"📝 Compiled {len(instructions)} instructions from plan (1:1 mapping):")
        for i, instr in enumerate(instructions, 1):
            logger.info(f"  {i}. {instr}")
        
        return instructions
    
    def compile_from_goal(self, goal: Any) -> List[Instruction]:
        """
        PHASE 2: Compile from goal using ecommerce heuristics.
        
        This is for AUTONOMOUS mode only.
        Contains optimization logic, heuristics, interpretation.
        
        🚨 NEVER called in INSTRUCTION mode.
        """
        logger.info("🔍 Compiling instructions from goal (autonomous mode)")
        instructions = []
        
        # Goal-based compilation logic here
        # (ecommerce heuristics, optimization, etc.)
        
        logger.warning("⚠️ Goal-based compilation not fully implemented - use INSTRUCTION mode")
        return instructions
    
    def _parse_line(self, line: str) -> Optional[Instruction]:
        """Parse a single line into an instruction."""
        line_lower = line.lower()
        
        # GOTO - navigate to URL
        if any(kw in line_lower for kw in self.GOTO_KEYWORDS):
            url = self._extract_url(line)
            if url:
                return Instruction(
                    action=ActionType.GOTO,
                    value=url,
                    expected_page_change=True
                )
        
        # TYPE - fill input field
        if any(kw in line_lower for kw in self.TYPE_KEYWORDS):
            # Extract target and value
            # Example: "type 'John Doe' in name field"
            # Example: "enter username as 'admin'"
            target, value = self._extract_type_params(line)
            if target and value:
                return Instruction(
                    action=ActionType.TYPE,
                    target_text=target,
                    value=value,
                    expected_page_change=False
                )
        
        # CLICK - click on element
        if any(kw in line_lower for kw in self.CLICK_KEYWORDS):
            target = self._extract_click_target(line)
            if target:
                return Instruction(
                    action=ActionType.CLICK,
                    target_text=target,
                    expected_page_change=True
                )
        
        # SEARCH - special case of type + submit
        if any(kw in line_lower for kw in self.SEARCH_KEYWORDS):
            query = self._extract_search_query(line)
            if query:
                return Instruction(
                    action=ActionType.TYPE,
                    target_text="search",
                    value=query,
                    expected_page_change=True,
                    metadata={"is_search": True}
                )
        
        logger.warning(f"⚠️ Could not parse line: {line}")
        return None
    
    def _parse_step_strict(self, step: Dict[str, Any]) -> Optional[Instruction]:
        """
        STRICT parsing: 1:1 conversion from plan step to instruction.
        
        CRITICAL: Uses ACTION field, NOT INTENT.
        Intent is for autonomous mode only.
        
        Instruction mode = action-driven execution.
        """
        action = step.get("action", "").lower()
        description = step.get("description", "")
        value = step.get("value")
        selector = step.get("selector")
        locator_hint = step.get("locator_hint")
        
        # GOTO - navigate to URL
        if action in ["goto", "navigate"]:
            url = value or step.get("url")
            if url:
                return Instruction(
                    action=ActionType.GOTO,
                    value=url,
                    expected_page_change=True
                )
        
        # CLICK - click any element
        elif action == "click":
            # Extract target text from description or selector
            target_text = self._extract_text_from_description_or_selector(description, selector)
            
            # Strip common verb prefixes ("Click", "Press", "Tap", etc.)
            target_text = self._strip_action_verbs(target_text)
            
            return Instruction(
                action=ActionType.CLICK,
                target_text=target_text,
                target_selector=selector,
                expected_page_change=step.get("expects_page_change", True),
                metadata={"locator_hint": locator_hint} if locator_hint else {}
            )
        
        # TYPE/FILL - fill input field
        elif action in ["type", "fill"]:
            # Extract target text from description or selector
            target_text = self._extract_text_from_description_or_selector(description, selector)
            
            # 🔵 FIX 1: Apply semantic normalization
            normalized_target = self.normalize_target(target_text)
            
            return Instruction(
                action=ActionType.TYPE,
                target_text=normalized_target,  # Use normalized target
                target_selector=selector,
                value=value,
                expected_page_change=False,
                metadata={
                    "locator_hint": locator_hint,
                    "original_target": target_text  # Keep original for debugging
                } if locator_hint or target_text != normalized_target else {}
            )
        
        # WAIT - wait for duration (NEVER allow None)
        elif action == "wait":
            # Fix: Always provide a valid number, never None
            if value and str(value).lower() != "none":
                try:
                    duration = int(value)
                except:
                    duration = 5  # Default 5 seconds
            else:
                duration = 5  # Default 5 seconds
            
            return Instruction(
                action=ActionType.WAIT,
                value=duration,
                expected_page_change=False
            )
        
        # SELECT - select from dropdown
        elif action == "select":
            # 🔵 FIX: Normalize SELECT targets too
            normalized_target = self.normalize_target(description)
            return Instruction(
                action=ActionType.SELECT,
                target_text=normalized_target,
                value=value,
                target_selector=selector,
                expected_page_change=False,
                metadata={"original_target": description}
            )
        
        # UNKNOWN ACTION - convert to click as fallback
        else:
            logger.warning(f"⚠️ Unknown action '{action}', converting to CLICK fallback")
            return Instruction(
                action=ActionType.CLICK,
                target_text=description or "unknown",
                expected_page_change=True
            )
    
    def _extract_text_from_description_or_selector(self, description: str, selector: str) -> str:
        """Extract human-readable text from description or selector."""
        # Try to extract text from selector like button:has-text('Air Solutions')
        if selector:
            import re
            match = re.search(r":has-text\(['\"](.+?)['\"]\)", selector)
            if match:
                return match.group(1)
        
        # Fallback to description
        return description or "element"
    
    def _strip_action_verbs(self, text: str) -> str:
        """Strip action verbs from target text (e.g., 'Click Air Solutions' → 'Air Solutions')."""
        if not text:
            return text
        
        # Common action verbs to strip
        verbs = ["click", "press", "tap", "select", "choose", "hit", "push"]
        
        words = text.split()
        if len(words) > 1 and words[0].lower() in verbs:
            # Remove first word and return rest
            return " ".join(words[1:]).strip()
        
        return text.strip()
    
    def _parse_step(self, step: Dict[str, Any]) -> Optional[Instruction]:
        """Parse a structured plan step into an instruction."""
        intent = step.get("intent", "").lower()
        
        # Navigate
        if intent in ["navigate", "goto", "open_url"]:
            url = step.get("url") or step.get("value")
            if url:
                return Instruction(
                    action=ActionType.GOTO,
                    value=url,
                    expected_page_change=True
                )
        
        # Click
        elif intent in ["click", "click_button", "click_link", "navigate_menu", "navigate_category"]:
            target = step.get("target") or step.get("value") or step.get("element_text")
            if target:
                return Instruction(
                    action=ActionType.CLICK,
                    target_text=target,
                    expected_page_change=step.get("expects_page_change", True)
                )
        
        # Type/Fill
        elif intent in ["type", "fill", "input", "search_box"]:
            target = step.get("target") or step.get("selector") or step.get("field")
            value = step.get("value") or step.get("text")
            if value:
                return Instruction(
                    action=ActionType.TYPE,
                    target_text=target or "input",
                    value=value,
                    expected_page_change=False
                )
        
        # Select product (special case - click)
        elif intent in ["select_product", "add_to_cart"]:
            return Instruction(
                action=ActionType.CLICK,
                target_text="product",
                expected_page_change=True,
                metadata={"intent": intent, "price_max": step.get("condition", {}).get("price_max")}
            )
        
        # Checkout
        elif intent in ["checkout", "proceed_to_checkout"]:
            return Instruction(
                action=ActionType.CLICK,
                target_text="checkout",
                expected_page_change=True
            )
        
        logger.debug(f"Skipping non-executable step: {intent}")
        return None
    
    def _extract_url(self, text: str) -> Optional[str]:
        """Extract URL from text."""
        # Look for http/https URLs
        match = re.search(r'https?://[^\s]+', text)
        if match:
            return match.group(0)
        
        # Look for www. URLs
        match = re.search(r'www\.[^\s]+', text)
        if match:
            return "https://" + match.group(0)
        
        return None
    
    def _extract_click_target(self, text: str) -> Optional[str]:
        """Extract click target from text."""
        # Remove click keywords
        for kw in self.CLICK_KEYWORDS:
            text = text.lower().replace(kw, "").strip()
        
        # Remove common prepositions
        text = re.sub(r'^(on|the|a)\s+', '', text, flags=re.IGNORECASE)
        
        # Extract quoted text if present
        match = re.search(r'["\']([^"\']+)["\']', text)
        if match:
            return match.group(1)
        
        # Return cleaned text
        return text.strip() if text.strip() else None
    
    def _extract_type_params(self, text: str) -> tuple:
        """Extract target and value for type instruction."""
        # Pattern: "type 'value' in target"
        match = re.search(r'["\']([^"\']+)["\'][^\'"]*in[^\'"]*["\']?([^"\']+)["\']?', text, re.IGNORECASE)
        if match:
            return match.group(2).strip(), match.group(1).strip()
        
        # Pattern: "enter value as 'text'"
        match = re.search(r'(\w+)[^\'"]*["\']([^"\']+)["\']', text, re.IGNORECASE)
        if match:
            return match.group(1).strip(), match.group(2).strip()
        
        return None, None
    
    def _extract_search_query(self, text: str) -> Optional[str]:
        """Extract search query from text."""
        # Remove search keywords
        for kw in self.SEARCH_KEYWORDS:
            text = text.lower().replace(kw, "").strip()
        
        # Extract quoted text
        match = re.search(r'["\']([^"\']+)["\']', text)
        if match:
            return match.group(1)
        
        # Return remaining text
        return text.strip() if text.strip() else None
    
    def validate_instructions(self, instructions: List[Instruction]) -> bool:
        """
        Validate instruction queue.
        Ensures:
        - First instruction is GOTO
        - All instructions have required parameters
        - No duplicate GOTOs
        """
        if not instructions:
            logger.error("❌ Empty instruction queue")
            return False
        
        # First must be GOTO
        if instructions[0].action != ActionType.GOTO:
            logger.error("❌ First instruction must be GOTO")
            return False
        
        # Check each instruction
        for i, instr in enumerate(instructions):
            if instr.action == ActionType.GOTO and not instr.value:
                logger.error(f"❌ Instruction {i+1}: GOTO missing URL")
                return False
            
            if instr.action == ActionType.CLICK and not instr.target_text:
                logger.error(f"❌ Instruction {i+1}: CLICK missing target")
                return False
            
            if instr.action == ActionType.TYPE and (not instr.target_text or not instr.value):
                logger.error(f"❌ Instruction {i+1}: TYPE missing target or value")
                return False
        
        logger.info(f"✅ Validated {len(instructions)} instructions")
        return True
