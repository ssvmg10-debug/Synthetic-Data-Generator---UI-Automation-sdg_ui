"""
Autonomous Loop - Goal-driven reasoning engine (OpenClaw style).

When deterministic execution fails, enters autonomous mode:
- Observes page state
- Generates possible actions
- Executes best action
- Validates progress toward goal
- Repeats until goal achieved

This is the "reasoning" layer that makes the system adaptive.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from playwright.async_api import Page
import logging
import asyncio

from .page_state_extractor import PageStateExtractor, PageState, InteractiveElement
from .smart_element_scorer import SmartElementScorer
from .goal_validator import GoalValidator, Goal, GoalType, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class PossibleAction:
    """Represents a possible action the autonomous agent could take."""
    action_type: str  # CLICK, TYPE, WAIT
    element: Optional[InteractiveElement]
    reasoning: str
    confidence: float
    priority: int


@dataclass
class AutonomousResult:
    """Result of autonomous execution."""
    success: bool
    actions_taken: List[str]
    final_state: PageState
    reasoning: str
    confidence: float


class AutonomousLoop:
    """
    Autonomous goal-driven execution engine.
    
    This is the "reasoning" mode that kicks in when deterministic execution fails.
    Instead of blindly executing instructions, it:
    1. Understands the goal
    2. Observes current state
    3. Generates possible actions
    4. Picks best action
    5. Validates progress
    6. Repeats until goal achieved
    """
    
    def __init__(self, page: Page, max_attempts: int = 5):
        self.page = page
        self.max_attempts = max_attempts
        self.state_extractor = PageStateExtractor(page)
        self.goal_validator = GoalValidator()
        
    async def achieve_goal(
        self, 
        goal: Goal, 
        context: Dict[str, any]
    ) -> AutonomousResult:
        """
        Autonomously achieve a goal.
        
        Args:
            goal: The goal to achieve
            context: Context dict with instruction details (action, target, value)
            
        Returns:
            AutonomousResult with outcome
        """
        logger.info("=" * 80)
        logger.info(f"🤖 AUTONOMOUS MODE: {goal.description}")
        logger.info("=" * 80)
        
        actions_taken = []
        attempt = 0
        
        # Extract initial state
        initial_state = await self.state_extractor.extract_state()
        current_state = initial_state
        
        while attempt < self.max_attempts:
            attempt += 1
            logger.info(f"\n🔄 Autonomous Attempt {attempt}/{self.max_attempts}")
            
            # Check if goal already achieved
            validation = await self.goal_validator.validate(goal, initial_state, current_state)
            if validation.success:
                logger.info(f"✅ Goal achieved: {validation.message}")
                return AutonomousResult(
                    success=True,
                    actions_taken=actions_taken,
                    final_state=current_state,
                    reasoning=f"Goal achieved after {len(actions_taken)} actions",
                    confidence=validation.confidence
                )
            
            # Generate possible actions
            possible_actions = await self._generate_possible_actions(
                current_state=current_state,
                goal=goal,
                context=context
            )
            
            if not possible_actions:
                logger.warning("❌ No possible actions generated")
                break
            
            # Pick best action
            best_action = self._select_best_action(possible_actions)
            logger.info(f"🎯 Selected action: {best_action.reasoning} (confidence: {best_action.confidence:.2f})")
            
            # Execute action
            before_state = current_state
            execution_success = await self._execute_action(best_action)
            
            if not execution_success:
                logger.warning(f"⚠️ Action execution failed: {best_action.reasoning}")
                actions_taken.append(f"FAILED: {best_action.reasoning}")
                # Try next action
                continue
            
            actions_taken.append(best_action.reasoning)
            
            # Wait for state to settle
            await asyncio.sleep(2)
            
            # Extract new state
            current_state = await self.state_extractor.extract_state()
            
            # Validate progress
            progress = self._assess_progress(before_state, current_state, goal)
            logger.info(f"📊 Progress assessment: {progress}")
            
        # Max attempts reached
        logger.warning(f"⚠️ Autonomous mode exhausted {self.max_attempts} attempts")
        
        # Final validation
        final_validation = await self.goal_validator.validate(goal, initial_state, current_state)
        
        return AutonomousResult(
            success=final_validation.success,
            actions_taken=actions_taken,
            final_state=current_state,
            reasoning=f"Attempted {len(actions_taken)} actions, goal {'achieved' if final_validation.success else 'not achieved'}",
            confidence=final_validation.confidence if final_validation.success else 0.3
        )
    
    async def _generate_possible_actions(
        self,
        current_state: PageState,
        goal: Goal,
        context: Dict[str, any]
    ) -> List[PossibleAction]:
        """
        Generate list of possible actions based on goal and current state.
        
        This is the "reasoning" step - what could we do to achieve the goal?
        """
        possible = []
        
        # Extract instruction context
        action = context.get('action', '').upper()
        target = context.get('target', '')
        value = context.get('value', '')
        
        logger.info(f"🧠 Generating actions for: {action}('{target}', '{value}')")
        logger.info(f"   Current page type: {current_state.page_type_hint}")
        logger.info(f"   Goal type: {goal.goal_type.value}")
        
        # Use smart scorer to find matching elements
        scorer = SmartElementScorer(current_state)
        
        if action == 'CLICK' or goal.goal_type == GoalType.NAVIGATION_OCCURRED:
            # Generate click actions
            click_actions = await self._generate_click_actions(scorer, target, goal, current_state)
            possible.extend(click_actions)
        
        if action == 'TYPE' or 'search' in target.lower():
            # Generate type actions
            type_actions = await self._generate_type_actions(scorer, target, value, current_state)
            possible.extend(type_actions)
        
        # Add smart fallback actions based on page type
        fallback_actions = await self._generate_fallback_actions(current_state, goal)
        possible.extend(fallback_actions)
        
        # Sort by confidence
        possible.sort(key=lambda x: (x.priority, x.confidence), reverse=True)
        
        logger.info(f"📋 Generated {len(possible)} possible actions")
        for i, pa in enumerate(possible[:5]):  # Log top 5
            logger.info(f"   {i+1}. {pa.reasoning} (conf: {pa.confidence:.2f}, pri: {pa.priority})")
        
        return possible
    
    async def _generate_click_actions(
        self,
        scorer: SmartElementScorer,
        target: str,
        goal: Goal,
        state: PageState
    ) -> List[PossibleAction]:
        """Generate possible click actions."""
        actions = []
        
        # Score elements for the target
        scored_elements = scorer.score_elements_for_click(target)
        
        # Take top 5 matches
        for se in scored_elements[:5]:
            actions.append(PossibleAction(
                action_type='CLICK',
                element=se.element,
                reasoning=f"Click '{se.element.text[:30]}' (matched target '{target}')",
                confidence=se.total_score,
                priority=1  # Direct match has high priority
            ))
        
        # Add context-based clicks
        if goal.goal_type == GoalType.RESULTS_VISIBLE:
            # Looking for search results - try clicking search buttons
            for elem in state.interactive_elements:
                if elem.element_type == 'button' and 'search' in elem.text.lower():
                    actions.append(PossibleAction(
                        action_type='CLICK',
                        element=elem,
                        reasoning=f"Click search button: '{elem.text[:30]}'",
                        confidence=0.75,
                        priority=2
                    ))
        
        elif goal.goal_type == GoalType.CART_UPDATED:
            # Looking for cart update - try "Add to Cart" buttons
            for elem in state.interactive_elements:
                elem_text_lower = elem.text.lower()
                if elem.element_type == 'button' and ('add' in elem_text_lower or 'cart' in elem_text_lower):
                    actions.append(PossibleAction(
                        action_type='CLICK',
                        element=elem,
                        reasoning=f"Click cart button: '{elem.text[:30]}'",
                        confidence=0.70,
                        priority=2
                    ))
        
        return actions
    
    async def _generate_type_actions(
        self,
        scorer: SmartElementScorer,
        target: str,
        value: str,
        state: PageState
    ) -> List[PossibleAction]:
        """Generate possible type actions."""
        actions = []
        
        # Score input elements
        scored_inputs = scorer.score_elements_for_type(target, value)
        
        # Take top 3 matches
        for se in scored_inputs[:3]:
            actions.append(PossibleAction(
                action_type='TYPE',
                element=se.element,
                reasoning=f"Type '{value}' into {se.element.attributes.get('placeholder', se.element.tag)}",
                confidence=se.total_score,
                priority=1
            ))
        
        return actions
    
    async def _generate_fallback_actions(
        self,
        state: PageState,
        goal: Goal
    ) -> List[PossibleAction]:
        """
        Generate smart fallback actions based on page context.
        
        These are heuristic-based actions when we don't have exact matches.
        """
        actions = []
        
        # If modal is open and we're trying to do something else, close it
        if state.has_modal and goal.goal_type not in [GoalType.MODAL_OPENED, GoalType.MODAL_CLOSED]:
            for elem in state.interactive_elements:
                elem_text = elem.text.lower()
                if 'close' in elem_text or 'dismiss' in elem_text or elem_text == '×':
                    actions.append(PossibleAction(
                        action_type='CLICK',
                        element=elem,
                        reasoning="Close modal (blocking interaction)",
                        confidence=0.60,
                        priority=3  # Lower priority - fallback
                    ))
                    break  # Only add one close action
        
        # If on product listing and goal is product detail, click first product
        if state.page_type_hint == 'listing' and goal.goal_type == GoalType.PRODUCT_SELECTED:
            # Find first product card
            for elem in state.interactive_elements:
                if 'product' in elem.attributes.get('class', '').lower():
                    actions.append(PossibleAction(
                        action_type='CLICK',
                        element=elem,
                        reasoning="Click first product card",
                        confidence=0.65,
                        priority=2
                    ))
                    break
        
        # If we need to search and we're on home page, look for search icon
        if goal.goal_type == GoalType.MODAL_OPENED and 'search' in goal.description.lower():
            for elem in state.interactive_elements:
                if elem.aria_label and 'search' in elem.aria_label.lower():
                    actions.append(PossibleAction(
                        action_type='CLICK',
                        element=elem,
                        reasoning=f"Click search icon (aria-label: {elem.aria_label})",
                        confidence=0.70,
                        priority=2
                    ))
        
        return actions
    
    def _select_best_action(self, possible_actions: List[PossibleAction]) -> PossibleAction:
        """Select the best action from possibilities (already sorted)."""
        return possible_actions[0]
    
    async def _execute_action(self, action: PossibleAction) -> bool:
        """
        Execute a single action.
        
        Returns:
            True if execution succeeded, False otherwise
        """
        try:
            if action.action_type == 'CLICK':
                if not action.element:
                    return False
                
                # Locate element by selector
                elem = self.page.locator(action.element.selector).first
                
                # Wait for it to be visible
                await elem.wait_for(state='visible', timeout=3000)
                
                # Scroll into view
                await elem.scroll_into_view_if_needed()
                
                # Click
                await elem.click(timeout=5000)
                logger.info(f"✅ Clicked: {action.element.text[:30]}")
                return True
                
            elif action.action_type == 'TYPE':
                if not action.element:
                    return False
                
                # Locate element
                elem = self.page.locator(action.element.selector).first
                
                # Wait for it
                await elem.wait_for(state='visible', timeout=3000)
                
                # Clear and type
                await elem.fill('')
                await elem.fill(action.reasoning.split("'")[1])  # Extract value from reasoning
                logger.info(f"✅ Typed into: {action.element.attributes.get('name', action.element.tag)}")
                return True
                
            elif action.action_type == 'WAIT':
                await asyncio.sleep(2)
                logger.info("✅ Waited")
                return True
                
            else:
                logger.warning(f"Unknown action type: {action.action_type}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Action execution failed: {e}")
            return False
    
    def _assess_progress(self, before: PageState, after: PageState, goal: Goal) -> str:
        """
        Assess if we made progress toward the goal.
        
        Returns human-readable progress assessment.
        """
        changes = []
        
        # URL changed?
        if before.url != after.url:
            changes.append(f"URL changed: {after.url}")
        
        # Page type changed?
        if before.page_type_hint != after.page_type_hint:
            changes.append(f"Page type: {before.page_type_hint} → {after.page_type_hint}")
        
        # Cart changed?
        if before.cart_count != after.cart_count:
            changes.append(f"Cart: {before.cart_count} → {after.cart_count}")
        
        # Modal state changed?
        if before.has_modal != after.has_modal:
            changes.append(f"Modal: {before.has_modal} → {after.has_modal}")
        
        # Products changed?
        if before.product_count != after.product_count:
            changes.append(f"Products: {before.product_count} → {after.product_count}")
        
        if changes:
            return "Progress: " + "; ".join(changes)
        else:
            return "No visible progress"
