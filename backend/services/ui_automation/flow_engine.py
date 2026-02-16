"""
Flow Engine – goal-driven autonomous loop.

Core loop (no page_type transitions, only goal matching):

    while not goal_completed:
        world = extract_page_model(page)
        action = decide_next_action(goal, world, state)
        if action is None: raise DeadEndError()
        await execute(action)
        validate_transition()
        update_session_state(world)
        if no_progress_for_N_loops: re-evaluate

Works for any test case, any future app. Dynamic & scalable.
"""
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import logging
import asyncio
import re
import os
from datetime import datetime

from playwright.async_api import async_playwright, Page, Browser

from .page_intelligence import extract_page_model_async, PageModel, PageType
from .state_manager import SessionState, LoginMode
from .decision_engine import DecisionEngine, NextAction, SemanticAction
from .goal_extractor import GoalObject, extract_goal
from .components import (
    HomePageComponent,
    SearchResultsComponent,
    ProductPageComponent,
    CartPageComponent,
    CheckoutPageComponent,
)
from .test_data_vault import get_synthetic_address

logger = logging.getLogger(__name__)

MAX_FLOW_ITERATIONS = 50
NO_PROGRESS_THRESHOLD = 3


class DeadEndError(Exception):
    """Raised when decision engine returns no actionable step and we're stuck."""


DeadlockError = DeadEndError  # Alias


@dataclass
class FlowResult:
    """Result of flow execution."""
    success: bool
    steps_executed: int
    goal_reached: bool
    final_page_type: str
    error: Optional[str] = None
    screenshots: List[str] = None

    def __post_init__(self):
        if self.screenshots is None:
            self.screenshots = []


class FlowEngine:
    """
    Goal-driven autonomous flow engine.
    No page_type transitions. Only goal matching.
    """

    def __init__(
        self,
        goal: str = "complete_guest_checkout",
        goal_obj: Optional[GoalObject] = None,
        constraints: Optional[Dict[str, Any]] = None,
        headless: bool = False,
        run_id: str = "flow",
        screenshot_dir: Optional[str] = None,
    ):
        self.goal_text = goal
        self.constraints = constraints or {}
        self.headless = headless
        self.run_id = run_id
        self.screenshot_dir = screenshot_dir or f"screenshots/flow_{run_id}"
        self.goal = goal_obj
        self.decision_engine = DecisionEngine(goal=goal_obj)
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def run(
        self,
        url: str,
        plan: Optional[Dict[str, Any]] = None,
        raw_input: Optional[str] = None,
    ) -> FlowResult:
        """
        Execute flow: goal-driven loop until goal reached or max iterations.
        """
        steps_executed = 0
        screenshots = []
        error = None
        state = SessionState(current_url=url)
        no_progress_count = 0

        # Extract structured goal from plan/raw_input; override with explicit constraints
        if not self.goal:
            self.goal = extract_goal(plan=plan, raw_input=raw_input, url=url)
            if self.constraints.get("search_query"):
                self.goal.search_query = self.constraints["search_query"]
            if self.constraints.get("product_price_max") is not None:
                self.goal.price_max = int(self.constraints["product_price_max"])
            if self.constraints.get("pincode"):
                self.goal.pincode = self.constraints["pincode"]
            self.decision_engine.goal = self.goal
        goal = self.goal

        try:
            async with async_playwright() as p:
                self.browser = await p.chromium.launch(headless=self.headless)
                self.page = await self.browser.new_page()

                await self.page.goto(url, timeout=60000, wait_until="domcontentloaded")
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                await self.page.wait_for_timeout(500)
                state.current_url = self.page.url or url

                for iteration in range(MAX_FLOW_ITERATIONS):
                    # 1. Extract world model (page intelligence)
                    world = await extract_page_model_async(self.page)
                    state.page_type = world.page_type
                    state.current_url = self.page.url or state.current_url
                    state.modal_visible = world.modals
                    if world.cart:
                        state.cart_count = world.cart.count or 0

                    logger.info(
                        "[%s] Flow iter %d: page_type=%s url=%s steps=%d",
                        self.run_id,
                        iteration + 1,
                        world.page_type.value,
                        (state.current_url or "")[:60],
                        steps_executed,
                    )

                    # 2. Check goal (requires flow state, not just structure)
                    if self._is_goal_reached(goal, world, state, steps_executed):
                        state.mark_goal_reached()
                        logger.info("[%s] Goal reached at page_type=%s", self.run_id, world.page_type.value)
                        return FlowResult(
                            success=True,
                            steps_executed=steps_executed,
                            goal_reached=True,
                            final_page_type=world.page_type.value,
                            screenshots=screenshots,
                        )

                    # 3. Decide next action (goal matching)
                    next_action = self.decision_engine.decide(goal, world, state)

                    if next_action.action == SemanticAction.DONE:
                        state.mark_goal_reached()
                        return FlowResult(True, steps_executed, True, world.page_type.value, screenshots=screenshots)

                    # RULE 3: If no rule matched (RETRY/UNKNOWN), use recovery strategy instead of idling
                    if next_action.action in (SemanticAction.UNKNOWN, SemanticAction.RETRY):
                        logger.warning("[%s] No decision → attempting recovery", self.run_id)
                        next_action = self.decision_engine.get_recovery_action(goal, world, state)
                        if next_action.action in (SemanticAction.UNKNOWN, SemanticAction.RETRY):
                            no_progress_count += 1
                            if no_progress_count >= NO_PROGRESS_THRESHOLD:
                                raise DeadEndError("Deadlock: recovery strategy returned no actionable step")
                            await self.page.wait_for_timeout(1000)
                            continue

                    # 4. Execute semantic action
                    success = await self._execute_action(next_action, world)
                    if success:
                        steps_executed += 1
                        no_progress_count = 0
                    else:
                        no_progress_count += 1
                        if no_progress_count >= NO_PROGRESS_THRESHOLD:
                            raise DeadEndError(
                                f"Deadlock: no progress for {no_progress_count} consecutive iterations"
                            )

                    self._update_state_after_action(state, next_action, world, success=success)

                    # Screenshot on every attempt (including failed) for debugging
                    path = await self._take_screenshot(
                        f"step_{steps_executed}_{next_action.action.value}_{'ok' if success else 'failed'}"
                    )
                    if path:
                        screenshots.append(path)

                    # 5. Validate transition (mandatory)
                    validated = await self._validate_after_action(world, state, success)
                    if not validated and success:
                        logger.debug("[%s] Post-action validation: state change not detected", self.run_id)

                    await self.page.wait_for_timeout(500)

        except DeadEndError as e:
            error = str(e)
            logger.error("[%s] %s", self.run_id, e)
        except Exception as e:
            error = str(e)
            logger.error("[%s] Flow error: %s", self.run_id, e, exc_info=True)
        finally:
            if self.browser:
                await self.browser.close()

        return FlowResult(
            success=False,
            steps_executed=steps_executed,
            goal_reached=state.goal_reached,
            final_page_type=state.page_type.value if hasattr(state.page_type, "value") else str(state.page_type),
            error=error,
            screenshots=screenshots,
        )

    def _is_goal_reached(
        self,
        goal: GoalObject,
        world: PageModel,
        state: SessionState,
        steps_executed: int,
    ) -> bool:
        """Goal requires flow completion + state, not just page structure."""
        if steps_executed < 3:
            return False
        if goal.wants_address_filled():
            return (
                state.checkout_started
                and state.login_mode == LoginMode.GUEST
                and (state.address_filled or (world.address_form and world.address_form.is_visible))
            )
        if goal.complete_purchase:
            return state.checkout_started and state.login_mode == LoginMode.GUEST
        return False

    async def _execute_action(self, next_action: NextAction, world: PageModel) -> bool:
        """Execute semantic action via component API."""
        action = next_action.action
        params = next_action.params

        if action == SemanticAction.ACCEPT_COOKIES:
            comp = HomePageComponent(self.page)
            return await comp.accept_cookies()

        if action == SemanticAction.SEARCH:
            comp = HomePageComponent(self.page)
            return await comp.search(params.get("query", ""))

        if action == SemanticAction.SELECT_PRODUCT:
            comp = SearchResultsComponent(self.page)
            return await comp.select_product_under_price(params.get("price_max"))

        if action == SemanticAction.ADD_TO_CART:
            comp = ProductPageComponent(self.page)
            return await comp.add_to_cart()

        if action == SemanticAction.FILL_PINCODE:
            comp = CartPageComponent(self.page)
            return await comp.fill_pincode_and_check(params.get("pincode", "500032"))

        if action == SemanticAction.SELECT_FREE_DELIVERY:
            comp = CartPageComponent(self.page)
            return await comp.select_free_delivery()

        if action == SemanticAction.PROCEED_TO_CHECKOUT:
            comp = CartPageComponent(self.page)
            return await comp.proceed_to_checkout()

        if action == SemanticAction.CONTINUE_AS_GUEST:
            comp = CheckoutPageComponent(self.page)
            return await comp.continue_as_guest()

        if action == SemanticAction.FILL_ADDRESS:
            comp = CheckoutPageComponent(self.page)
            # Use Test Data Vault (env/defaults); params from decision can override
            addr = get_synthetic_address(override=params or {})
            return await comp.fill_billing_address(
                name=addr.get("name", "Test User"),
                address=addr.get("address", "123 Test St"),
                phone=addr.get("phone", "9876543210"),
                city=addr.get("city", "Hyderabad"),
            )

        if action == SemanticAction.CLOSE_MODAL:
            try:
                btn = self.page.get_by_role("button", name="Close").first
                await btn.click(timeout=5000)
                return True
            except Exception:
                pass
            return False

        if action == SemanticAction.EXPLORATORY_CLICK:
            return await self._execute_exploratory_click(params)

        return False

    async def _execute_exploratory_click(self, params: Dict[str, Any]) -> bool:
        """Recovery: click first visible button matching candidates."""
        candidates = params.get("candidates", ["Search", "Buy", "Know More", "Continue", "Proceed"])
        visible = params.get("visible_buttons", [])
        # Prefer visible buttons that match candidates
        for kw in candidates:
            try:
                loc = self.page.get_by_role("button", name=re.compile(re.escape(kw), re.I))
                if await loc.count() > 0:
                    await loc.first.scroll_into_view_if_needed(timeout=3000)
                    await loc.first.click(timeout=8000)
                    await self.page.wait_for_timeout(1500)
                    return True
            except Exception:
                pass
            try:
                loc = self.page.get_by_role("link", name=re.compile(re.escape(kw), re.I))
                if await loc.count() > 0:
                    await loc.first.scroll_into_view_if_needed(timeout=3000)
                    await loc.first.click(timeout=8000)
                    await self.page.wait_for_timeout(1500)
                    return True
            except Exception:
                pass
        # Fallback: try first visible from visible_buttons list
        for txt in visible[:5]:
            if len(txt) < 3 or len(txt) > 60:
                continue
            try:
                loc = self.page.get_by_role("button", name=re.compile(re.escape(txt[:30]), re.I))
                if await loc.count() > 0:
                    await loc.first.click(timeout=5000)
                    await self.page.wait_for_timeout(1500)
                    return True
            except Exception:
                pass
        return False

    async def _validate_after_action(
        self,
        world_before: PageModel,
        state: SessionState,
        action_success: bool,
    ) -> bool:
        """
        Validate that action produced expected state change.
        Did URL change? DOM change? Cart increase?
        """
        if not action_success:
            return False
        try:
            await self.page.wait_for_timeout(500)
            world_after = await extract_page_model_async(self.page)
            # Simple checks: URL changed, or cart count increased, or page_type changed
            url_changed = world_after.url != world_before.url
            cart_increased = (world_after.cart_count or 0) > (world_before.cart_count or 0)
            page_changed = world_after.page_type != world_before.page_type
            return url_changed or cart_increased or page_changed
        except Exception as e:
            logger.debug("Validation after action: %s", e)
            return False

    def _update_state_after_action(
        self,
        state: SessionState,
        next_action: NextAction,
        world: PageModel,
        success: bool = True,
    ) -> None:
        """Update session state after action."""
        action = next_action.action
        state.last_action = action.value
        state.last_action_ok = success
        state.action_history.append(action.value)
        state.current_url = self.page.url if self.page else ""
        state.page_type = world.page_type
        if world.cart:
            state.cart_count = world.cart.count or 0

        if action == SemanticAction.SEARCH and success:
            state.search_succeeded = True
        if action == SemanticAction.SELECT_PRODUCT and success:
            state.product_selected = True
        if action in (SemanticAction.FILL_PINCODE, SemanticAction.SELECT_FREE_DELIVERY) and success:
            state.delivery_selected = True
        if action == SemanticAction.PROCEED_TO_CHECKOUT and success:
            state.checkout_started = True
        if action == SemanticAction.CONTINUE_AS_GUEST and success:
            state.login_mode = LoginMode.GUEST
        if action == SemanticAction.FILL_ADDRESS and success:
            state.address_filled = True

    async def _take_screenshot(self, name: str) -> str:
        """Take screenshot; ensure directory exists. Returns path or ''."""
        if not self.page:
            return ""
        try:
            os.makedirs(self.screenshot_dir, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = os.path.join(self.screenshot_dir, filename)
            await self.page.screenshot(path=filepath, full_page=False)
            return filepath
        except Exception as e:
            logger.debug("Flow screenshot failed: %s", e)
            return ""
