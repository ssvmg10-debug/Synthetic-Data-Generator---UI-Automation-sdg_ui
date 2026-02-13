"""
UI Automation Router
Endpoints for UI test automation with LangGraph agents
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from db import get_db
from models import UITestCase, UIExecutionRun, LocatorRegistry
from routers.chats import ensure_chat_and_append_user_message, append_agent_message
from services.ui_automation.agents.planner.agent import PlannerAgent
from services.ui_automation.agents.generator.agent import GeneratorAgent
from services.ui_automation.agents.validator.agent import ValidatorAgent
from services.ui_automation.agents.healer.agent import HealerAgent
from services.ui_automation.engine.executor import PlaywrightExecutor
from agents.ui_automation.graph import run_ui_automation_workflow
from datetime import datetime
from pathlib import Path
from threading import Lock
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Track the currently running UI test (for live screenshot streaming)
_current_run_lock: Lock = Lock()
_current_run: Optional[Dict[str, Any]] = None


def _set_current_run(test_case_id: int, stage: str = "plan") -> None:
    """Register the currently running UI test and optional stage for progress."""
    global _current_run
    with _current_run_lock:
        _current_run = {
            "test_case_id": test_case_id,
            "stage": stage,
            "started_at": datetime.utcnow().isoformat(),
        }


def _update_current_run_stage(stage: str) -> None:
    """Update the stage of the current run (e.g. generate, validate, execute, heal)."""
    global _current_run
    with _current_run_lock:
        if _current_run is not None:
            _current_run = {**_current_run, "stage": stage}


def _clear_current_run() -> None:
    """Clear the current run (no UI test in progress)."""
    global _current_run
    with _current_run_lock:
        _current_run = None


def _get_current_run() -> Optional[Dict[str, Any]]:
    """Return a shallow copy of the current run metadata, if any."""
    with _current_run_lock:
        return dict(_current_run) if _current_run is not None else None


# ========== REQUEST MODELS ==========

class UITestRequest(BaseModel):
    raw_input: Optional[str] = None
    feature_description: Optional[str] = None
    page_url: Optional[str] = None
    use_synthetic_data: bool = False
    synthetic_run_id: Optional[int] = None
    script_language: Optional[str] = "javascript"
    chat_id: Optional[int] = None  # If set, append to this chat; response includes chat_id
    visible_browser: Optional[bool] = True  # If false, run Playwright in headless mode

class UIExecuteRequest(BaseModel):
    test_case_id: int
    synthetic_data: Optional[List[Dict[str, Any]]] = None

# ========== ENDPOINTS ==========

@router.post("/run-workflow")
async def run_ui_automation_workflow_endpoint(request: UITestRequest, db: Session = Depends(get_db)):
    """
    Execute complete UI automation workflow with LangGraph agents and self-healing
    This is the main entry point for agent-based UI automation
    """
    try:
        logger.info("="*80)
        logger.info("🚀 UI AUTOMATION WORKFLOW REQUEST RECEIVED")
        logger.info("="*80)
        
        # Accept both formats
        if request.raw_input:
            test_input = request.raw_input
        elif request.feature_description and request.page_url:
            test_input = f"URL: {request.page_url}\n\nTest Description:\n{request.feature_description}"
        else:
            raise HTTPException(status_code=400, detail="Either raw_input OR (feature_description + page_url) is required")
        
        logger.info(f"📝 Test Case: {test_input[:100]}...")
        
        # Run LangGraph workflow with self-healing
        result = await run_ui_automation_workflow(
            test_case=test_input,
            db=db,
            max_healing_attempts=3
        )
        
        if result['status'] == 'passed':
            logger.info("="*80)
            logger.info("✅ WORKFLOW COMPLETED - TEST PASSED")
            logger.info("="*80)
            
            return {
                "success": True,
                "status": "passed",
                "test_case_id": result['testcase_id'],
                "healing_attempts": result['healing_attempts'],
                "healing_history": result['healing_history'],
                "script": result['script'],
                "logs": result.get("logs"),
                "logs_path": result.get("logs_path"),
                "step_screenshots": result.get("step_screenshots", []),
                "message": f"Test passed with {result['healing_attempts']} healing attempts"
            }
        else:
            logger.error("="*80)
            logger.error("❌ WORKFLOW FAILED")
            logger.error("="*80)
            
            return {
                "success": False,
                "status": "failed",
                "error": result.get('error'),
                "healing_attempts": result['healing_attempts'],
                "healing_history": result['healing_history'],
                "logs": result.get("logs"),
                "logs_path": result.get("logs_path"),
                "step_screenshots": result.get("step_screenshots", []),
                "message": f"Test failed after {result['healing_attempts']} healing attempts"
            }
        
    except Exception as e:
        logger.error(f"❌ Workflow error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plan")
async def plan_ui_test(request: UITestRequest, db: Session = Depends(get_db)):
    """Convert raw test case to structured JSON plan (LEGACY - direct agent call)"""
    try:
        logger.info("🎯 UI Automation: Creating test plan...")
        
        # Accept both formats: raw_input OR (feature_description + page_url)
        if request.raw_input:
            test_input = request.raw_input
        elif request.feature_description and request.page_url:
            test_input = f"URL: {request.page_url}\n\nTest Description:\n{request.feature_description}"
        else:
            raise HTTPException(status_code=400, detail="Either raw_input OR (feature_description + page_url) is required")
        
        logger.info(f"📋 Test input received: {test_input[:100]}...")
        
        planner = PlannerAgent()
        logger.info("🤖 Using Planner Agent to generate structured test plan...")
        structured_plan = planner.plan(test_input)
        
        logger.info(f"✅ Test plan created with {len(structured_plan.get('steps', []))} steps")
        
        # Save test case
        test_case = UITestCase(raw_input=test_input, structured_json=structured_plan)
        db.add(test_case)
        db.commit()
        db.refresh(test_case)
        
        logger.info(f"💾 Test case saved with ID: {test_case.id}")
        
        return {
            "success": True,
            "test_case_id": test_case.id,
            "plan": structured_plan,
            "message": "Test case planned successfully"
        }
    except Exception as e:
        logger.error(f"❌ Error in test planning: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

class UIGenerateRequest(BaseModel):
    test_plan: Optional[Dict[str, Any]] = None
    test_case_id: Optional[int] = None
    page_url: Optional[str] = None

@router.post("/generate")
async def generate_ui_script(request: UIGenerateRequest, db: Session = Depends(get_db)):
    """Generate Playwright script from structured plan"""
    try:
        logger.info("🔨 UI Automation: Generating Playwright script...")
        
        if request.test_case_id:
            logger.info(f"📂 Loading test case ID: {request.test_case_id}")
            test_case = db.query(UITestCase).filter(UITestCase.id == request.test_case_id).first()
            if not test_case:
                raise HTTPException(status_code=404, detail="Test case not found")
            plan = test_case.structured_json
        elif request.test_plan:
            logger.info("📋 Using provided test plan")
            plan = request.test_plan
            # Save test case
            test_case = UITestCase(raw_input=f"Generated from plan: {request.page_url}", structured_json=plan)
            db.add(test_case)
            db.commit()
            db.refresh(test_case)
        else:
            raise HTTPException(status_code=400, detail="Either test_case_id or test_plan is required")
        
        logger.info(f"🤖 Using Generator Agent to create Playwright script...")
        generator = GeneratorAgent()
        script = generator.generate(plan, db=db)
        
        logger.info(f"✅ Script generated ({len(script)} characters)")
        
        # Update test case with script
        test_case.script = {"language": "javascript", "content": script}
        db.commit()
        
        logger.info(f"💾 Script saved to test case ID: {test_case.id}")
        
        return {
            "success": True,
            "test_case_id": test_case.id,
            "script": script,
            "message": "Script generated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate")
async def validate_ui_script(test_case_id: int, db: Session = Depends(get_db)):
    """Validate selectors and steps in the script"""
    try:
        test_case = db.query(UITestCase).filter(UITestCase.id == test_case_id).first()
        if not test_case:
            raise HTTPException(status_code=404, detail="Test case not found")
        
        validator = ValidatorAgent()
        validation_result = validator.validate(test_case.structured_json)
        
        return {
            "test_case_id": test_case_id,
            "validation": validation_result,
            "is_valid": validation_result.get("is_valid", False),
            "message": "Validation completed"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/execute")
async def execute_ui_test(request: UIExecuteRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Execute UI test using Playwright"""
    try:
        logger.info(f"🎬 UI Automation: Starting test execution for test case {request.test_case_id}...")
        
        test_case = db.query(UITestCase).filter(UITestCase.id == request.test_case_id).first()
        if not test_case:
            raise HTTPException(status_code=404, detail="Test case not found")
        
        # Use existing script or generate new one
        if not test_case.script:
            logger.info("📝 No script found, generating new script...")
            generator = GeneratorAgent()
            script = generator.generate(test_case.structured_json, synthetic_data=request.synthetic_data, db=db)
            test_case.script = {"language": "javascript", "content": script}
            db.commit()
        else:
            logger.info("📋 Using existing script from database")
            script = test_case.script.get("content") if isinstance(test_case.script, dict) else test_case.script
        
        # Execute
        logger.info("🎭 Launching Playwright executor (HEADED mode)...")
        executor = PlaywrightExecutor()
        result = executor.execute(script, test_case_id=request.test_case_id)
        
        # Save execution run
        execution_run = UIExecutionRun(
            test_case_id=request.test_case_id,
            status=result.get("status", "failed"),
            logs_path=result.get("logs_path"),
            screenshot_path=result.get("screenshot_path")
        )
        db.add(execution_run)
        db.commit()
        db.refresh(execution_run)
        
        logger.info("Execution completed! Run ID: %s, Status: %s", execution_run.id, result.get("status"))

        return {
            "success": True,
            "execution_id": execution_run.id,
            "run_id": execution_run.id,
            "test_case_id": request.test_case_id,
            "status": result.get("status"),
            "logs": result.get("logs"),
            "screenshot": result.get("screenshot_path"),
            "message": "Test execution completed",
        }
    except Exception as e:
        logger.error(f"❌ Error in test execution: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run")
async def run_full_ui_test(request: UITestRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Full workflow: plan -> generate -> validate -> execute"""
    chat_id = None
    try:
        if not request.raw_input or not request.raw_input.strip():
            raise HTTPException(
                status_code=400,
                detail="raw_input is required. Send your test scenario or steps in the message."
            )
        chat_id = ensure_chat_and_append_user_message(
            db, request.chat_id, "ui-automation", request.raw_input
        )
        logger.info("="*80)
        logger.info("UI AUTOMATION REQUEST RECEIVED")
        logger.info("Raw Input: %s...", (request.raw_input[:100] if len(request.raw_input) > 100 else request.raw_input))
        logger.info("Use Synthetic Data: %s", request.use_synthetic_data)
        logger.info("Script Language: %s", request.script_language)
        headed = True if request.visible_browser is None else bool(request.visible_browser)
        logger.info("Visible browser (headed mode): %s", headed)
        logger.info("="*80)

        # Step 1: Plan
        logger.info("STEP 1: Planning test case...")
        planner = PlannerAgent()
        structured_plan = planner.plan(request.raw_input)
        logger.info("Test plan created with %s steps", len(structured_plan.get("steps", [])))
        append_agent_message(db, chat_id, f"UI: planned test case into {len(structured_plan.get('steps', []))} steps.", {"stage": "plan", "steps": structured_plan.get("steps", [])})

        test_case = UITestCase(raw_input=request.raw_input, structured_json=structured_plan)
        db.add(test_case)
        db.commit()
        db.refresh(test_case)
        logger.info("Test case saved with ID: %s", test_case.id)
        _set_current_run(test_case.id, stage="plan")

        # Step 2: Get synthetic data if needed
        synthetic_data = None
        if request.use_synthetic_data and request.synthetic_run_id:
            logger.info("STEP 2: Loading synthetic data from run %s...", request.synthetic_run_id)
            from models import SyntheticData
            data_rows = db.query(SyntheticData).filter(
                SyntheticData.run_id == request.synthetic_run_id
            ).all()
            synthetic_data = [d.row_json for d in data_rows]
            logger.info("Loaded %s synthetic data rows", len(synthetic_data))
            append_agent_message(db, chat_id, f"UI: loaded {len(synthetic_data)} synthetic data rows from run {request.synthetic_run_id}.", {"stage": "load_synthetic", "rows": len(synthetic_data)})
        else:
            logger.info("STEP 2: Skipped - No synthetic data requested")
            append_agent_message(db, chat_id, "UI: proceeding without external synthetic data.", {"stage": "load_synthetic", "rows": 0})
        _update_current_run_stage("generate")

        # Step 3: Generate script (with app-specific config for LG India, etc.)
        logger.info("STEP 3: Generating Playwright script...")
        try:
            from config.app_config import get_app_config_for_url
            plan_url = structured_plan.get("url") or ""
            app_config = get_app_config_for_url(plan_url)
            if app_config:
                logger.info("Using app config for: %s", app_config.get("name") or app_config.get("app_key"))
        except Exception:
            app_config = None
        generator = GeneratorAgent()
        language = (request.script_language or "javascript").lower()
        if language not in ("javascript", "typescript"):
            language = "javascript"
        script = generator.generate(structured_plan, synthetic_data=synthetic_data, language=language, db=db, app_config=app_config)
        logger.info("Script generated (%s characters)", len(script))
        append_agent_message(db, chat_id, f"UI: generated Playwright script ({len(script)} characters).", {"stage": "generate_script", "language": language})

        # Persist script on test case for traceability
        test_case.script = {"language": language, "content": script}
        db.commit()
        _update_current_run_stage("validate")

        # Step 4: Validate
        logger.info("STEP 4: Validating test plan...")
        validator = ValidatorAgent()
        validation = validator.validate(structured_plan)
        logger.info("Validation complete: %s", validation.get("is_valid", False))
        append_agent_message(db, chat_id, f"UI: validation {'passed' if validation.get('is_valid', False) else 'completed with issues'}.", {"stage": "validate", "result": validation})

        # Step 5: Execute
        logger.info("STEP 5: Executing Playwright script...")
        append_agent_message(
            db,
            chat_id,
            f"UI: executing Playwright script in {'headed' if headed else 'headless'} browser…",
            {"stage": "execute_start", "headed": headed},
        )
        executor = PlaywrightExecutor()
        _update_current_run_stage("execute")
        result = executor.execute(script, test_case_id=test_case.id, headed=headed)
        logger.info("Execution complete - Status: %s", result.get("status"))
        append_agent_message(db, chat_id, f"UI: initial execution finished with status '{result.get('status')}'.", {"stage": "execute_done", "status": result.get("status"), "error": result.get("error")})

        # Step 6: Heal if failed (up to 2 attempts with full context for healer)
        healer = HealerAgent()
        max_heal_attempts = 2
        current_script = script
        steps_list = structured_plan.get("steps") or []

        for attempt in range(max_heal_attempts):
            if result.get("status") != "failed":
                break
            logger.info("STEP 6: Self-healing (attempt %s/%s) - Test failed, attempting auto-heal...", attempt + 1, max_heal_attempts)
            _update_current_run_stage("heal")
            append_agent_message(db, chat_id, f"UI: healing attempt {attempt + 1}/{max_heal_attempts} for failing step.", {"stage": "heal_attempt", "attempt": attempt + 1, "status": result.get("status"), "error": result.get("error")})
            failed_idx = result.get("failed_step_index")
            # failed_step_index from executor is 1-based; steps before failure = indices 0..failed_idx-2
            steps_before = steps_list[: (failed_idx - 1)] if failed_idx is not None and isinstance(failed_idx, int) and failed_idx >= 1 else None
            healed = healer.heal(
                current_script,
                result.get("error") or "",
                db,
                failed_locator=result.get("failed_selector"),
                test_case_context={"raw_input": request.raw_input, "steps": steps_list},
                plan=structured_plan,
                failed_step_index=failed_idx,
                steps_before_failure=steps_before,
                failure_url=result.get("failure_url"),
                failure_page_elements=result.get("failure_page_elements"),
            )
            if healed.get("healed"):
                logger.info("Healing successful - Re-executing...")
                current_script = healed.get("script") or current_script
                result = executor.execute(current_script, test_case_id=test_case.id, headed=headed)
                result["healed"] = True
                logger.info("Re-execution complete - Status: %s", result.get("status"))
                append_agent_message(db, chat_id, f"UI: re-execution after healing finished with status '{result.get('status')}'.", {"stage": "heal_execute_done", "status": result.get("status"), "error": result.get("error")})
            else:
                logger.warning("Healing failed (no replacement selector found)")
                break

        if result.get("status") == "passed":
            logger.info("STEP 6: Test passed (with or without healing)")
            append_agent_message(db, chat_id, "UI: test passed (with or without healing).", {"stage": "complete", "status": result.get("status"), "healed": result.get("healed", False)})
        elif result.get("status") == "failed":
            logger.info("STEP 6: Test still failed after healing attempts")
            append_agent_message(db, chat_id, "UI: test still failed after healing attempts.", {"stage": "complete", "status": result.get("status"), "healed": result.get("healed", False), "error": result.get("error")})

        # Save execution
        execution_run = UIExecutionRun(
            test_case_id=test_case.id,
            status=result.get("status", "failed"),
            logs_path=result.get("logs_path"),
            screenshot_path=result.get("screenshot_path")
        )
        db.add(execution_run)
        db.commit()
        db.refresh(execution_run)

        logger.info("="*80)
        logger.info("SUCCESS: UI Test Complete")
        logger.info("Execution ID: %s | Status: %s", execution_run.id, result.get("status"))
        logger.info("="*80)

        agent_text = "UI automation %s for execution %s." % (result.get("status"), execution_run.id)
        payload = {
            "kind": "ui",
            "status": result.get("status"),
            "testCaseId": test_case.id,
            "executionId": execution_run.id,
            "plan": structured_plan,
            "script": script,
            "healingHistory": {
                "healed": result.get("healed", False),
                "screenshot": result.get("screenshot_path"),
            },
        }
        append_agent_message(db, chat_id, agent_text, payload)

        _clear_current_run()
        return {
            "execution_id": execution_run.id,
            "test_case_id": test_case.id,
            "status": result.get("status"),
            "validation": validation,
            "plan": structured_plan,
            "script": script,
            "healed": result.get("healed", False),
            "logs": result.get("logs"),
            "logs_path": result.get("logs_path"),
            "screenshot": result.get("screenshot_path"),
            "step_screenshots": result.get("step_screenshots", []),
            "message": "UI test completed",
            "chat_id": chat_id,
        }
    except HTTPException:
        _clear_current_run()
        raise
    except Exception as e:
        logger.error("="*80)
        logger.error("ERROR in UI test execution: %s", str(e))
        logger.error("="*80)
        import traceback
        logger.error(traceback.format_exc())
        if chat_id is not None:
            try:
                append_agent_message(db, chat_id, "Sorry, something went wrong: %s" % str(e), None)
            except Exception:
                pass
        _clear_current_run()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results/{execution_id}")
async def get_ui_results(execution_id: int, db: Session = Depends(get_db)):
    """Get UI test execution results"""
    execution = db.query(UIExecutionRun).filter(UIExecutionRun.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    test_case = db.query(UITestCase).filter(UITestCase.id == execution.test_case_id).first()
    
    return {
        "execution_id": execution.id,
        "test_case_id": execution.test_case_id,
        "status": execution.status,
        "logs_path": execution.logs_path,
        "screenshot_path": execution.screenshot_path,
        "created_at": execution.created_at,
        "test_plan": test_case.structured_json if test_case else None
    }


@router.get("/current-run/status")
async def get_current_run_status():
    """Return current run progress so the frontend can show Planning / Generating / Executing etc."""
    current = _get_current_run()
    if not current:
        return {"running": False, "stage": None, "test_case_id": None}
    return {
        "running": True,
        "stage": current.get("stage") or "plan",
        "test_case_id": current.get("test_case_id"),
    }


@router.get("/current-run/live-screenshot")
async def get_current_run_live_screenshot():
    """Return latest live or step screenshot for the current UI run (Cursor-style in-app browser view)."""
    current = _get_current_run()
    if not current:
        raise HTTPException(status_code=404, detail="No UI run in progress")

    test_case_id = current.get("test_case_id")
    if not isinstance(test_case_id, int):
        raise HTTPException(status_code=404, detail="No UI run in progress")

    backend_root = Path(__file__).resolve().parent.parent
    screenshot_dir = backend_root / "test_outputs" / f"run_{test_case_id}" / "step_screenshots"
    if not screenshot_dir.exists():
        raise HTTPException(status_code=404, detail="No screenshots yet")

    # Prefer live.png (updated every 2s during execution) for real-time browser view; fall back to latest step_*.png
    import time
    live_path = screenshot_dir / "live.png"
    if live_path.exists():
        try:
            mtime = live_path.stat().st_mtime
            if (time.time() - mtime) < 15:  # consider live if updated in last 15s
                return FileResponse(
                    live_path,
                    media_type="image/png",
                    headers={
                        "Cache-Control": "no-store, no-cache, must-revalidate",
                        "Pragma": "no-cache",
                        "Expires": "0",
                    },
                )
        except OSError:
            pass

    png_files = sorted(screenshot_dir.glob("step_*.png"))
    if not png_files:
        raise HTTPException(status_code=404, detail="No screenshots yet")

    latest = png_files[-1]
    return FileResponse(
        latest,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/locators")
async def get_locator_registry(db: Session = Depends(get_db)):
    """Get all locators from registry"""
    locators = db.query(LocatorRegistry).all()
    return {
        "locators": [
            {
                "element": loc.element,
                "primary": loc.primary_locator,
                "healed": loc.healed_locators
            }
            for loc in locators
        ]
    }


# ========== PLAYWRIGHT TEST AGENTS ENDPOINTS ==========

class PlaywrightAgentRequest(BaseModel):
    request: str
    base_url: Optional[str] = None
    prd: Optional[str] = None

class PlaywrightGeneratorRequest(BaseModel):
    plan_file: str

class PlaywrightHealerRequest(BaseModel):
    test_file: str
    error_message: str
    max_retries: int = 3


@router.post("/playwright-agents/init")
async def init_playwright_agents():
    """Initialize Playwright Test Agents (planner, generator, healer)"""
    try:
        from services.ui_automation.agents.playwright_test_agents import PlaywrightTestAgents
        
        logger.info("🎭 Initializing Playwright Test Agents...")
        agents = PlaywrightTestAgents()
        result = agents.init_agents()
        
        return {
            "success": result.get('success', False),
            "message": result.get('message', 'Initialization complete'),
            "output": result.get('output', '')
        }
    except Exception as e:
        logger.error(f"❌ Error initializing agents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/playwright-agents/planner")
async def playwright_planner_agent(request: PlaywrightAgentRequest):
    """
    🎭 Planner Agent
    Explores the app and produces a Markdown test plan
    """
    try:
        from services.ui_automation.agents.playwright_test_agents import PlaywrightTestAgents
        
        logger.info(f"🎭 Planner Agent: {request.request[:100]}...")
        agents = PlaywrightTestAgents()
        
        result = agents.planner_agent(
            request=request.request,
            base_url=request.base_url,
            prd=request.prd
        )
        
        if result['success']:
            return {
                "success": True,
                "plan_file": result['plan_file'],
                "plan_content": result['plan_content'],
                "message": "Test plan generated successfully"
            }
        else:
            raise HTTPException(status_code=500, detail=result.get('error'))
            
    except Exception as e:
        logger.error(f"❌ Planner agent error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/playwright-agents/generator")
async def playwright_generator_agent(request: PlaywrightGeneratorRequest):
    """
    🎭 Generator Agent
    Uses markdown plan to produce executable Playwright tests
    """
    try:
        from services.ui_automation.agents.playwright_test_agents import PlaywrightTestAgents
        
        logger.info(f"🎭 Generator Agent: {request.plan_file}")
        agents = PlaywrightTestAgents()
        
        result = agents.generator_agent(plan_file=request.plan_file)
        
        if result['success']:
            return {
                "success": True,
                "test_file": result['test_file'],
                "test_content": result['test_content'],
                "message": "Playwright test generated successfully"
            }
        else:
            raise HTTPException(status_code=500, detail=result.get('error'))
            
    except Exception as e:
        logger.error(f"❌ Generator agent error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/playwright-agents/healer")
async def playwright_healer_agent(request: PlaywrightHealerRequest):
    """
    🎭 Healer Agent
    Automatically repairs failing tests
    """
    try:
        from services.ui_automation.agents.playwright_test_agents import PlaywrightTestAgents
        
        logger.info(f"🎭 Healer Agent: {request.test_file}")
        agents = PlaywrightTestAgents()
        
        result = agents.healer_agent(
            test_file=request.test_file,
            error_message=request.error_message,
            max_retries=request.max_retries
        )
        
        if result['success']:
            return {
                "success": True,
                "healed": result.get('healed', False),
                "actions": result.get('actions', []),
                "message": result.get('message', 'Healing complete')
            }
        else:
            raise HTTPException(status_code=500, detail=result.get('error'))
            
    except Exception as e:
        logger.error(f"❌ Healer agent error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
