# Add this new endpoint to backend/routers/ui_automation.py after the run-enterprise-v3 endpoint

@router.post("/run-enterprise-v4")
async def run_enterprise_v4_test(request: UITestRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    🚀 Enterprise v4 - Deterministic Instruction-Following Architecture
    
    Complete redesign for enterprise-grade deterministic execution:
    - Layer 1: Instruction Compiler → converts test case to executable queue
    - Layer 2: Strict Execution → no random exploration during instructions
    - Layer 3: Deterministic DOM Targeting → scored element matching
    - Layer 4: Proper DOM Graph → full structural awareness
    - Layer 5: Controlled Recovery → structured retry strategies
    - Layer 6: State Verification → verify changes after each step
    
    Works for:
    - B2C ecommerce (LG, Amazon, etc.)
    - B2B dashboards
    - D2C apps
    - Enterprise portals
    - Admin panels
    
    Returns:
    - Success/failure status
    - Steps executed
    - Instruction mode used
    - Health score
    """
    chat_id = None
    try:
        if not request.raw_input or not request.raw_input.strip():
            raise HTTPException(
                status_code=400,
                detail="raw_input is required. Send your test scenario or steps in the message."
            )
        
        chat_id = ensure_chat_and_append_user_message(
            db, request.chat_id, "ui-automation-enterprise-v4", request.raw_input
        )
        
        logger.info("="*80)
        logger.info("🚀 ENTERPRISE V4: DETERMINISTIC INSTRUCTION-FOLLOWING")
        logger.info("Raw Input: %s...", (request.raw_input[:100] if len(request.raw_input) > 100 else request.raw_input))
        logger.info("="*80)
        
        # Step 1: Plan
        logger.info("STEP 1: Planning test case...")
        planner = PlannerAgent()
        structured_plan = planner.plan(request.raw_input)
        logger.info("Test plan created with %s steps", len(structured_plan.get("steps", [])))
        append_agent_message(db, chat_id, f"Enterprise v4: planned test case into {len(structured_plan.get('steps', []))} steps.", {"stage": "plan", "steps": structured_plan.get("steps", [])})
        
        test_case = UITestCase(raw_input=request.raw_input, structured_json=structured_plan)
        db.add(test_case)
        db.commit()
        db.refresh(test_case)
        logger.info("Test case saved with ID: %s", test_case.id)
        _set_current_run(test_case.id, stage="enterprise_v4")
        
        # Step 2: Extract URL and headless mode
        url = structured_plan.get("url") or "https://www.lg.com/in"
        headed = True if request.visible_browser is None else bool(request.visible_browser)
        logger.info("URL: %s | Headed: %s", url, headed)
        
        # Step 3: Run Enterprise Flow Engine v4
        logger.info("STEP 2: Initializing Enterprise Flow Engine v4 (Deterministic)...")
        append_agent_message(db, chat_id, "Enterprise v4: starting deterministic instruction-following execution...", {"stage": "enterprise_v4_execute_start"})
        
        _update_current_run_stage("enterprise_v4_execute")
        
        # Generate unique run ID
        run_id = f"enterprise_v4_run_{test_case.id}_{uuid.uuid4().hex[:8]}"
        
        # Extract goal from plan (for compatibility)
        from services.ui_automation.goal_extractor import extract_goal
        goal = extract_goal(structured_plan, request.raw_input)
        
        # Initialize Enterprise Flow Engine v4 with all sources
        enterprise_engine = EnterpriseFlowEngine(
            goal=goal,
            raw_input=request.raw_input,
            structured_plan=structured_plan,
            headless=not headed,
            run_id=run_id
        )
        
        # Execute with Enterprise v4
        enterprise_result: EnterpriseFlowResult = await enterprise_engine.run(url=url)
        
        # Extract metrics
        logger.info("="*80)
        logger.info("📊 ENTERPRISE V4 METRICS:")
        logger.info("Success: %s", enterprise_result.success)
        logger.info("Mode: %s", "INSTRUCTION" if enterprise_result.instruction_mode else "AUTONOMOUS")
        logger.info("Instructions Compiled: %d", enterprise_result.instructions_compiled)
        logger.info("Steps Executed: %d", enterprise_result.steps_executed)
        logger.info("Health Score: %.2f", enterprise_result.health_score)
        logger.info("Execution Time: %.2fs", enterprise_result.execution_time)
        logger.info("="*80)
        
        # Prepare response
        result = {
            "status": "passed" if enterprise_result.success else "failed",
            "error": enterprise_result.error,
            "steps_executed": enterprise_result.steps_executed,
            "instruction_mode": enterprise_result.instruction_mode,
            "instructions_compiled": enterprise_result.instructions_compiled,
            "health_score": enterprise_result.health_score,
            "execution_time": enterprise_result.execution_time,
            "screenshots": enterprise_result.screenshots,
            "screenshot_path": enterprise_result.screenshots[0] if enterprise_result.screenshots else None,
            "logs_path": f"logs/enterprise_v4_run_{test_case.id}.log",
        }
        
        # Append success message
        append_agent_message(
            db, 
            chat_id, 
            f"Enterprise v4: execution finished with status '{result['status']}' (Mode: {'Instruction' if result['instruction_mode'] else 'Autonomous'}, Health: {result['health_score']:.2f}, Time: {result['execution_time']:.1f}s).", 
            {
                "stage": "enterprise_v4_execute_done", 
                "status": result["status"], 
                "error": result.get("error"),
                "metrics": {
                    "instruction_mode": result["instruction_mode"],
                    "instructions_compiled": result["instructions_compiled"],
                    "health_score": result["health_score"],
                    "execution_time": result["execution_time"]
                }
            }
        )
        
        _clear_current_run()
        
        return {
            "test_case_id": test_case.id,
            "result": result,
            "features": [
                "Instruction Compiler",
                "Deterministic DOM Targeting",
                "Strict Step Execution",
                "Controlled Recovery",
                "State Verification"
            ]
        }
        
    except HTTPException:
        _clear_current_run()
        raise
    except Exception as e:
        logger.error("="*80)
        logger.error("❌ ENTERPRISE V4 ERROR: %s", str(e))
        logger.error("="*80)
        import traceback
        logger.error(traceback.format_exc())
        if chat_id is not None:
            try:
                append_agent_message(db, chat_id, "Enterprise v4: error occurred - %s" % str(e), None)
            except Exception:
                pass
        _clear_current_run()
        raise HTTPException(status_code=500, detail=str(e))
