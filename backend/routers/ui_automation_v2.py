"""
🚀 Combined UI Automation Workflow (default) + optional Agent-only mode:

  COMBINED (use_agents=False, DEFAULT): Planner + Generator hints + DeterministicExecutorV2 + Healer
    - PlannerAgent: natural language → structured plan.
    - GeneratorAgent: layered selectors per step (registry + step selectors) → generator_selectors in plan.
    - plan_to_test_case: plan → TestCase with metadata.generator_selectors.
    - DeterministicExecutorV2: tries generator_selectors first, then execution_memory, site_knowledge,
      element_resolver, resolution_decision_engine, healing_agent (core), Playwright HealerAgent.
    All execution in Python; no Node/JS.

  AGENT-ONLY (use_agents=True): Planner → Generator → run generated JS via Node
    Uses PlannerAgent, GeneratorAgent, PlaywrightExecutor (npx), HealerAgent on script.
    Does NOT use element_resolver, resolution_engine, enhanced_deterministic_executor.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import time
from pathlib import Path
from sqlalchemy.orm import Session

from db import get_db
from services.ui_automation.core.enhanced_deterministic_executor import DeterministicExecutorV2, ExecutionResult
from services.ui_automation.core.semantic_parser import SemanticTestParser
from services.ui_automation.core.test_model import StepType

logger = logging.getLogger(__name__)

router_v2 = APIRouter(prefix="/ui-automation-v2", tags=["ui-automation-v2"])


class TestRequestV2(BaseModel):
    """Request model for Enhanced Deterministic System V2"""
    
    # Input format options (choose one)
    natural_language: Optional[str] = None  # "Navigate to lg.com, Click Air Solutions, ..."
    enterprise_spec: Optional[Dict[str, Any]] = None  # {"Test Case ID": "TC001", "Steps": [...]}
    
    # Options
    visible_browser: bool = True
    start_url: Optional[str] = None
    use_agents: bool = False  # If True: Planner→Generator→Node/JS. If False: combined workflow (Planner + Generator hints + V2 + Healer).
    use_planner_agents: bool = True  # When use_agents=False: use PlannerAgent for NL→plan
    use_generator_hints: bool = True  # When use_agents=False: enrich plan with Generator's layered selectors; V2 tries them first
    use_healer_agent_in_v2: bool = True  # When use_agents=False: use Playwright HealerAgent inside V2
    
    # Tracking
    chat_id: Optional[str] = None


class TestResponseV2(BaseModel):
    """Response model for Enhanced Deterministic System V2"""
    
    test_id: str
    passed: bool
    total_steps: int
    executed_steps: int
    failed_step: Optional[int] = None
    error: Optional[str] = None
    duration_ms: int
    checkpoints: List[Dict[str, Any]]
    
    # Additional info
    assertion_count: int = 0
    action_count: int = 0
    
    # Test plan and script (for UI display)
    plan: Optional[Dict[str, Any]] = None
    script: Optional[str] = None


@router_v2.post("/run", response_model=TestResponseV2)
async def run_test_v2(request: TestRequestV2, db: Session = Depends(get_db)):
    """
    Execute test using Enhanced Deterministic System V2 or Agent flow (Planner → Generator → Healer).
    
    When use_agents=True (default) and natural_language is provided:
    - PlannerAgent plans the test, GeneratorAgent generates Playwright JS, PlaywrightExecutor runs it, HealerAgent heals on failure.
    
    Otherwise: semantic parser + DeterministicExecutorV2 (Python Playwright).
    """
    logger.info("="*80)
    logger.info("ENHANCED DETERMINISTIC SYSTEM V3 - REQUEST RECEIVED (use_agents=%s)", request.use_agents)
    logger.info("="*80)
    
    try:
        # Validate input
        if not request.natural_language and not request.enterprise_spec:
            raise HTTPException(
                status_code=400,
                detail="Either 'natural_language' or 'enterprise_spec' is required"
            )
        
        # Agent flow: Planner → Generator → Execute generated JS (Node) → Healer. Does NOT use element_resolver / resolution_engine / enhanced_deterministic_executor.
        if request.use_agents and request.natural_language:
            logger.info("Using agent workflow (Planner→Generator→Node/Playwright JS); Python resolver/healing stack not used")
            from agents.ui_automation.graph import run_ui_automation_workflow
            t0 = time.perf_counter()
            wf_result = await run_ui_automation_workflow(
                test_case=request.natural_language,
                db=db,
                max_healing_attempts=3,
            )
            duration_ms = int((time.perf_counter() - t0) * 1000)
            status = wf_result.get("status")
            passed = status == "passed"
            # Derive step counts from parsed natural language
            test_case = SemanticTestParser.parse_natural_language(request.natural_language)
            total_steps = len(test_case.steps)
            executed_steps = total_steps if passed else 0
            assertion_count = sum(1 for s in test_case.steps if s.type == StepType.ASSERTION)
            action_count = sum(1 for s in test_case.steps if s.type in [StepType.ACTION, StepType.INPUT, StepType.NAVIGATION])
            # Build plan for UI
            def _desc(s):
                intent = getattr(s.intent, "value", str(s.intent))
                if s.type == StepType.NAVIGATION:
                    return f"Navigate to {s.target or 'page'}"
                if s.type == StepType.ACTION:
                    return f"Click {s.target or s.value or 'element'}"
                if s.type == StepType.INPUT:
                    return f"Type/fill {s.value or s.target}"
                if s.type == StepType.ASSERTION:
                    return f"Verify {s.value or s.target}"
                return f"{s.target or s.value or intent}"
            plan = {
                "test_id": "agent-flow",
                "title": "UI Automation (Planner → Generator → Healer)",
                "steps": [
                    {"step": i + 1, "type": str(getattr(s.type, "value", s.type)).replace("StepType.", "").lower(), "description": _desc(s)}
                    for i, s in enumerate(test_case.steps)
                ],
            }
            checkpoints = []
            for shot in wf_result.get("step_screenshots") or []:
                step_id = shot.get("step", len(checkpoints) + 1)
                checkpoints.append({
                    "step_id": step_id,
                    "description": f"Step {step_id}",
                    "state": shot.get("path", "screenshot"),
                    "timestamp": "",
                    "success": True,
                    "error": None,
                })
            logger.info("Agent flow result: status=%s steps=%d/%d duration_ms=%d", status, executed_steps, total_steps, duration_ms)
            return TestResponseV2(
                test_id=str(wf_result.get("testcase_id") or "agent"),
                passed=passed,
                total_steps=total_steps,
                executed_steps=executed_steps,
                failed_step=None if passed else 1,
                error=None if passed else wf_result.get("error"),
                duration_ms=duration_ms,
                checkpoints=checkpoints,
                assertion_count=assertion_count,
                action_count=action_count,
                plan=plan,
                script=wf_result.get("script"),
            )
        
        # Combined workflow: Planner + Generator hints + DeterministicExecutorV3 (ELR, fingerprint, Mem0) + Healer
        logger.info(
            "Using combined workflow: Planner + Generator hints + DeterministicExecutorV3 "
            "(element_resolver, resolution_decision_engine, healing_agent, site_knowledge, flow_engine)"
        )
        from playwright.async_api import async_playwright
        from services.ui_automation.core.plan_adapter import (
            plan_to_test_case,
            enrich_plan_with_elr,
            enrich_plan_with_generator_selectors,
        )

        # Launch browser
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=not request.visible_browser)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()
            
            # Create executor (pass db so HealerAgent can run inside V2 when use_healer_agent_in_v2)
            executor = DeterministicExecutorV2(
                page,
                context,
                db=db if request.use_healer_agent_in_v2 else None,
                use_healer_agent=request.use_healer_agent_in_v2,
            )
            
            test_case_for_display = None
            if request.natural_language:
                logger.info("Input: Natural Language")
                logger.info("Text: %s", request.natural_language[:100] + "..." if len(request.natural_language) > 100 else request.natural_language)
                
                if request.use_planner_agents:
                    from services.ui_automation.agents.planner.agent import PlannerAgent
                    plan = PlannerAgent().plan(request.natural_language)
                    plan = enrich_plan_with_elr(plan, request.start_url)
                    if request.use_generator_hints and db:
                        plan = enrich_plan_with_generator_selectors(plan, db)
                    test_case_for_display = plan_to_test_case(plan, request.start_url)
                    result = await executor.execute_test_case(test_case_for_display)
                    logger.info(
                        "Combined workflow: Planner + %s Generator hints + DeterministicExecutorV3 + HealerAgent",
                        "with" if request.use_generator_hints else "without",
                    )
                else:
                    result = await executor.execute_natural_language(
                        request.natural_language,
                        start_url=request.start_url,
                    )
                    test_case_for_display = SemanticTestParser.parse_natural_language(
                        request.natural_language, request.start_url
                    )
                    logger.info(
                        "Combined workflow: Natural language (no planner) + DeterministicExecutorV3",
                    )
            
            elif request.enterprise_spec:
                logger.info("Input: Enterprise Format")
                logger.info("Test Case ID: %s", request.enterprise_spec.get("Test Case ID", "N/A"))
                result = await executor.execute_enterprise_format(request.enterprise_spec)
                test_case_for_display = SemanticTestParser.parse_enterprise_format(request.enterprise_spec)
            
            # Close browser
            await browser.close()
        
        # Count assertion vs action steps and build plan for UI
        test_case = test_case_for_display or (
            SemanticTestParser.parse_natural_language(request.natural_language, request.start_url)
            if request.natural_language
            else SemanticTestParser.parse_enterprise_format(request.enterprise_spec)
        )
        
        assertion_count = sum(1 for s in test_case.steps if s.type == StepType.ASSERTION)
        action_count = sum(1 for s in test_case.steps if s.type in [StepType.ACTION, StepType.INPUT, StepType.NAVIGATION])
        
        # Generate test plan for UI display
        def format_step_description(s):
            """Create user-friendly step descriptions"""
            intent = s.intent.value if hasattr(s.intent, 'value') else str(s.intent)
            
            if s.type == StepType.NAVIGATION:
                return f"Navigate to {s.target or 'page'}"
            elif s.type == StepType.ACTION:
                if intent == "CLICK":
                    return f"Click {s.target or 'element'}"
                elif intent == "BUY_NOW":
                    return f"Click Buy Now button for {s.target or 'product'}"
                elif intent == "ADD_TO_CART":
                    return f"Click Add to Cart for {s.target or 'product'}"
                elif intent == "CHECKOUT":
                    return "Click Checkout button"
                elif intent == "CONTINUE_AS_GUEST":
                    return "Click Continue as Guest"
                elif intent == "SELECT_OPTION":
                    return f"Select {s.target or s.value or 'option'} option"
                else:
                    return f"Click {s.target or s.value or 'element'}"
            elif s.type == StepType.INPUT:
                if intent == "FILL_PINCODE":
                    return f"Type {s.value} in pincode field"
                elif intent == "TYPE":
                    return f"Type {s.value or 'text'} in {s.target or 'field'}"
                elif intent == "SEARCH":
                    return f"Search for {s.value or s.target}"
                else:
                    return f"Fill {s.target or 'field'} with {s.value or 'value'}"
            elif s.type == StepType.WAIT:
                return f"Wait for {s.value or '5'} seconds"
            elif s.type == StepType.ASSERTION:
                return f"Verify {s.value or s.target or 'condition'}"
            else:
                return f"{s.target or s.value or intent}"
        
        plan = {
            "test_id": test_case.id,
            "title": test_case.title or "UI Automation Test",
            "steps": [
                {
                    "step": i + 1,
                    "type": str(s.type.value if hasattr(s.type, 'value') else s.type).replace("StepType.", "").lower(),
                    "intent": str(s.intent.value if hasattr(s.intent, 'value') else s.intent).replace("Intent.", ""),
                    "description": format_step_description(s)
                }
                for i, s in enumerate(test_case.steps)
            ]
        }
        
        # Generate test script for UI display
        script_lines = [
            "# Enhanced Deterministic System V2 Test Script",
            f"# Test ID: {test_case.id}",
            f"# Total Steps: {len(test_case.steps)}",
            "",
            "from playwright.async_api import async_playwright",
            "from services.ui_automation.core.enhanced_deterministic_executor import DeterministicExecutorV2",
            "",
            "async def test():",
            "    async with async_playwright() as p:",
            "        browser = await p.chromium.launch(headless=False)",
            "        context = await browser.new_context()",
            "        page = await context.new_page()",
            "        executor = DeterministicExecutorV2(page, context)",
            "",
        ]
        
        # Add natural language or enterprise spec
        if request.natural_language:
            script_lines.append(f'        test_case = """')
            script_lines.append(f"        {request.natural_language[:500]}")
            script_lines.append(f'        """')
            script_lines.append(f"        result = await executor.execute_natural_language(test_case)")
        else:
            script_lines.append(f"        spec = {request.enterprise_spec}")
            script_lines.append(f"        result = await executor.execute_enterprise_format(spec)")
        
        script_lines.extend([
            "",
            f"        print(f'Test: {{result.passed}}')",
            f"        print(f'Steps: {{result.executed_steps}}/{{result.total_steps}}')",
            "        await browser.close()"
        ])
        
        script = "\n".join(script_lines)
        
        # Log result
        logger.info("="*80)
        logger.info("EXECUTION RESULT:")
        logger.info("Status: %s", "✅ PASSED" if result.passed else "❌ FAILED")
        logger.info("Steps: %d/%d executed", result.executed_steps, result.total_steps)
        logger.info("Duration: %dms", result.duration_ms)
        logger.info("Assertions: %d (no UI clicks)", assertion_count)
        logger.info("Actions: %d (UI interactions)", action_count)
        if not result.passed:
            logger.error("Failed at step %d: %s", result.failed_step, result.error)
        logger.info("="*80)
        
        # Return response
        return TestResponseV2(
            test_id=result.test_id,
            passed=result.passed,
            total_steps=result.total_steps,
            executed_steps=result.executed_steps,
            failed_step=result.failed_step,
            error=result.error,
            duration_ms=result.duration_ms,
            checkpoints=[
                {
                    "step_id": cp.step_id,
                    "description": cp.step_description,
                    "state": cp.state,
                    "timestamp": cp.timestamp,
                    "success": cp.success,
                    "error": cp.error
                }
                for cp in result.checkpoints
            ],
            assertion_count=assertion_count,
            action_count=action_count,
            plan=plan,
            script=script
        )
    
    except Exception as e:
        logger.error(f"Execution failed with error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Execution failed: {str(e)}"
        )


@router_v2.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0",
        "system": "Enhanced Deterministic System V3",
        "features": [
            "Semantic parsing (English → JSON DSL)",
            "Assertion engine (never clicks)",
            "Deterministic execution",
            "State validation",
            "Smart waits"
        ]
    }
