"""
Integrated Testing Router
Combines Synthetic Data Generation (SDV) + UI Automation (Playwright Test Agents)
End-to-end testing workflow
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

from services.synthetic.sdv_engine.generator import SDVGenerator
from services.ui_automation.agents.planner.agent import PlannerAgent
from services.ui_automation.agents.generator.agent import GeneratorAgent
from services.ui_automation.agents.healer.agent import HealerAgent
from services.ui_automation.agents.validator.agent import ValidatorAgent
from services.ui_automation.engine.executor import PlaywrightExecutor
from db import get_db
from models import TestCase, TestExecution

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrated", tags=["Integrated Testing"])


class IntegratedTestRequest(BaseModel):
    """Request for integrated testing (SDV + Playwright)"""
    test_cases: List[str]  # List of test case descriptions
    use_synthetic_data: bool = True
    schema_info: Optional[Dict[str, Any]] = None  # For SDV data generation
    num_records: int = 10


@router.post("/run-full-workflow")
async def run_integrated_workflow(request: IntegratedTestRequest):
    """
    🎯 Run complete end-to-end testing workflow:
    1. Generate synthetic data using SDV
    2. Run UI automation with Playwright Test Agents (headed mode)
    3. Self-heal any failures
    4. Return comprehensive results
    """
    
    logger.info("=" * 80)
    logger.info("🚀 INTEGRATED TESTING WORKFLOW STARTED")
    logger.info(f"📋 Test Cases: {len(request.test_cases)}")
    logger.info(f"💾 Synthetic Data: {request.use_synthetic_data}")
    logger.info("=" * 80)
    
    workflow_results = {
        "workflow_id": f"integrated_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "started_at": datetime.now().isoformat(),
        "test_cases": [],
        "synthetic_data": None,
        "summary": {
            "total_tests": len(request.test_cases),
            "passed": 0,
            "failed": 0,
            "healed": 0
        }
    }
    
    # STEP 1: Generate Synthetic Data (if requested)
    if request.use_synthetic_data and request.schema_info:
        logger.info("📊 STEP 1: Generating synthetic data using SDV...")
        try:
            sdv_generator = SDVGenerator()
            synthetic_data = sdv_generator.generate(
                schema=request.schema_info,
                num_rows=request.num_records
            )
            workflow_results["synthetic_data"] = {
                "status": "success",
                "records_generated": len(synthetic_data),
                "data": synthetic_data
            }
            logger.info(f"✅ Generated {len(synthetic_data)} synthetic records")
        except Exception as e:
            logger.error(f"❌ SDV generation failed: {str(e)}")
            workflow_results["synthetic_data"] = {
                "status": "failed",
                "error": str(e)
            }
    else:
        logger.info("⏭️  STEP 1: Skipped - No synthetic data requested")
    
    # STEP 2: Process each test case with Playwright Test Agents
    logger.info(f"\n🎭 STEP 2: Processing {len(request.test_cases)} test cases with Playwright...")
    
    for idx, test_case_description in enumerate(request.test_cases, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"🧪 Test Case {idx}/{len(request.test_cases)}")
        logger.info(f"📝 Description: {test_case_description[:100]}...")
        logger.info(f"{'='*60}")
        
        test_result = {
            "test_number": idx,
            "description": test_case_description,
            "stages": {}
        }
        
        try:
            # Stage 1: Planning (using Playwright Test Agents)
            logger.info("📋 Stage 1/4: Planning test case...")
            planner = PlannerAgent(use_playwright_agents=True)
            test_plan = planner.plan(test_case_description)
            test_result["stages"]["planning"] = {
                "status": "success",
                "plan": test_plan
            }
            logger.info(f"✅ Plan created with {len(test_plan.get('steps', []))} steps")
            
            # Save to database
            db = next(get_db())
            test_case_record = TestCase(
                name=f"Integrated Test {idx}",
                description=test_case_description,
                test_plan=str(test_plan)
            )
            db.add(test_case_record)
            db.commit()
            test_case_id = test_case_record.id
            db.close()
            
            # Stage 2: Code Generation (using Playwright Test Agents)
            logger.info("🤖 Stage 2/4: Generating Playwright script...")
            generator = GeneratorAgent(use_playwright_agents=True)
            script = generator.generate(test_plan)
            test_result["stages"]["generation"] = {
                "status": "success",
                "script_length": len(script)
            }
            logger.info(f"✅ Script generated ({len(script)} characters)")
            
            # Stage 3: Validation
            logger.info("🔍 Stage 3/4: Validating test plan...")
            validator = ValidatorAgent()
            is_valid = validator.validate(test_plan)
            test_result["stages"]["validation"] = {
                "status": "success" if is_valid else "failed",
                "is_valid": is_valid
            }
            logger.info(f"✅ Validation: {is_valid}")
            
            # Stage 4: Execution (HEADED MODE)
            logger.info("🎬 Stage 4/4: Executing in HEADED mode...")
            executor = PlaywrightExecutor()
            execution_result = executor.execute(test_case_id, script)
            
            # Save execution to database
            db = next(get_db())
            exec_record = TestExecution(
                test_case_id=test_case_id,
                status=execution_result["status"],
                logs=execution_result.get("logs", ""),
                error=execution_result.get("error")
            )
            db.add(exec_record)
            db.commit()
            execution_id = exec_record.id
            db.close()
            
            test_result["execution_id"] = execution_id
            test_result["status"] = execution_result["status"]
            test_result["stages"]["execution"] = execution_result
            
            if execution_result["status"] == "success":
                logger.info(f"✅ Test PASSED")
                workflow_results["summary"]["passed"] += 1
            else:
                logger.warning(f"❌ Test FAILED - Attempting self-healing...")
                
                # Stage 5: Self-Healing (using Playwright Test Agents)
                try:
                    healer = HealerAgent(use_playwright_agents=True)
                    healed_result = healer.heal(
                        test_case_id=test_case_id,
                        error_message=execution_result.get("error", "Unknown error")
                    )
                    test_result["stages"]["healing"] = healed_result
                    
                    if healed_result.get("status") == "success":
                        logger.info(f"🩹 Test HEALED successfully!")
                        workflow_results["summary"]["healed"] += 1
                        test_result["status"] = "healed"
                    else:
                        logger.error(f"⚠️ Healing failed")
                        workflow_results["summary"]["failed"] += 1
                except Exception as heal_error:
                    logger.error(f"❌ Healing error: {str(heal_error)}")
                    test_result["stages"]["healing"] = {"status": "error", "error": str(heal_error)}
                    workflow_results["summary"]["failed"] += 1
            
        except Exception as e:
            logger.error(f"❌ Test case {idx} failed: {str(e)}")
            test_result["status"] = "error"
            test_result["error"] = str(e)
            workflow_results["summary"]["failed"] += 1
        
        workflow_results["test_cases"].append(test_result)
    
    # Final Summary
    workflow_results["completed_at"] = datetime.now().isoformat()
    
    logger.info("\n" + "=" * 80)
    logger.info("🎉 INTEGRATED TESTING WORKFLOW COMPLETED")
    logger.info(f"📊 Results: {workflow_results['summary']['passed']} passed, "
                f"{workflow_results['summary']['failed']} failed, "
                f"{workflow_results['summary']['healed']} healed")
    logger.info("=" * 80)
    
    return workflow_results


@router.post("/run-single-test")
async def run_single_integrated_test(
    test_description: str,
    use_synthetic_data: bool = False,
    schema_info: Optional[Dict[str, Any]] = None,
    num_records: int = 5
):
    """
    🎯 Run a single test with integrated workflow
    Simplified version for testing one test case at a time
    """
    
    request = IntegratedTestRequest(
        test_cases=[test_description],
        use_synthetic_data=use_synthetic_data,
        schema_info=schema_info,
        num_records=num_records
    )
    
    result = await run_integrated_workflow(request)
    
    # Return just the first test case result
    if result["test_cases"]:
        return {
            "workflow_id": result["workflow_id"],
            "synthetic_data": result.get("synthetic_data"),
            "test_result": result["test_cases"][0],
            "summary": result["summary"]
        }
    else:
        raise HTTPException(status_code=500, detail="No test results generated")
