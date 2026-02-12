"""
API Automation Router
Endpoints for API test automation
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from db import get_db
from models import APITestCase, APIExecutionRun, APISchemaCache
from services.api_automation.agents.planner.agent import APIPlannerAgent
from services.api_automation.agents.generator.agent import APIGeneratorAgent
from services.api_automation.engine.executor import APIExecutor
from services.api_automation.engine.validator import APIValidator
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# ========== REQUEST MODELS ==========

class APITestRequest(BaseModel):
    raw_input: str
    use_synthetic_data: bool = False
    synthetic_run_id: Optional[int] = None

class APIExecuteRequest(BaseModel):
    test_case_id: int
    synthetic_data: Optional[List[Dict[str, Any]]] = None

# ========== ENDPOINTS ==========

@router.post("/plan")
async def plan_api_test(request: APITestRequest, db: Session = Depends(get_db)):
    """Convert raw test case to structured API test plan"""
    try:
        logger.info("🎯 API Automation: Creating test plan...")
        logger.info(f"📋 Test input: {request.raw_input[:100]}...")
        
        planner = APIPlannerAgent()
        logger.info("🤖 Using API Planner Agent...")
        structured_plan = planner.plan(request.raw_input)
        
        logger.info(f"✅ API test plan created with {len(structured_plan.get('requests', []))} requests")
        
        # Save test case
        test_case = APITestCase(raw_input=request.raw_input, structured_json=structured_plan)
        db.add(test_case)
        db.commit()
        db.refresh(test_case)
        
        logger.info(f"💾 Test case saved with ID: {test_case.id}")
        
        return {
            "test_case_id": test_case.id,
            "plan": structured_plan,
            "message": "API test case planned successfully"
        }
    except Exception as e:
        logger.error(f"❌ Error in API test planning: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate")
async def generate_api_request(test_case_id: int, db: Session = Depends(get_db)):
    """Generate API request payload from structured plan"""
    try:
        logger.info(f"🔨 API Automation: Generating request for test case {test_case_id}...")
        
        test_case = db.query(APITestCase).filter(APITestCase.id == test_case_id).first()
        if not test_case:
            raise HTTPException(status_code=404, detail="Test case not found")
        
        logger.info("🤖 Using API Generator Agent...")
        generator = APIGeneratorAgent()
        request_payload = generator.generate(test_case.structured_json)
        
        logger.info(f"✅ API request generated for endpoint: {request_payload.get('url', 'N/A')}")
        
        return {
            "test_case_id": test_case_id,
            "request": request_payload,
            "message": "API request generated successfully"
        }
    except Exception as e:
        logger.error(f"❌ Error in API request generation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/execute")
async def execute_api_test(request: APIExecuteRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Execute API test"""
    try:
        logger.info(f"🚀 API Automation: Starting execution for test case {request.test_case_id}...")
        
        test_case = db.query(APITestCase).filter(APITestCase.id == request.test_case_id).first()
        if not test_case:
            raise HTTPException(status_code=404, detail="Test case not found")
        
        # Generate request
        logger.info("🔨 Generating API request...")
        generator = APIGeneratorAgent()
        api_request = generator.generate(test_case.structured_json, synthetic_data=request.synthetic_data)
        
        logger.info(f"🌐 Sending {api_request.get('method', 'GET')} request to: {api_request.get('url', 'N/A')}")
        
        # Execute
        executor = APIExecutor()
        result = executor.execute(api_request)
        
        logger.info(f"✅ Response received: Status {result.get('status_code', 'N/A')}")
        
        # Validate response
        logger.info("✔️  Validating response...")
        validator = APIValidator()
        validation = validator.validate(result.get("response"), test_case.structured_json.get("expected_schema"))
        
        logger.info(f"📊 Validation result: {validation.get('status', 'unknown')}")
        
        # Save execution run
        execution_run = APIExecutionRun(
            test_case_id=request.test_case_id,
            endpoint=api_request.get("url", ""),
            payload_json=api_request.get("payload"),
            response_json=result.get("response"),
            status=validation.get("status", "failed")
        )
        db.add(execution_run)
        db.commit()
        db.refresh(execution_run)
        
        logger.info(f"✅ API test execution completed! Run ID: {execution_run.id}, Status: {validation.get('status')}")
        
        return {
            "execution_id": execution_run.id,
            "test_case_id": request.test_case_id,
            "status": validation.get("status"),
            "response": result.get("response"),
            "validation": validation,
            "message": "API test executed"
        }
    except Exception as e:
        logger.error(f"❌ Error in API test execution: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/run")
async def run_full_api_test(request: APITestRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Full workflow: plan -> generate -> execute -> validate"""
    try:
        # Step 1: Plan
        planner = APIPlannerAgent()
        structured_plan = planner.plan(request.raw_input)
        
        test_case = APITestCase(raw_input=request.raw_input, structured_json=structured_plan)
        db.add(test_case)
        db.commit()
        db.refresh(test_case)
        
        # Step 2: Get synthetic data if needed
        synthetic_data = None
        if request.use_synthetic_data and request.synthetic_run_id:
            from models import SyntheticData
            data_rows = db.query(SyntheticData).filter(
                SyntheticData.run_id == request.synthetic_run_id
            ).all()
            synthetic_data = [d.row_json for d in data_rows]
        
        # Step 3: Generate request
        generator = APIGeneratorAgent()
        api_request = generator.generate(structured_plan, synthetic_data=synthetic_data)
        
        # Step 4: Execute
        executor = APIExecutor()
        result = executor.execute(api_request)
        
        # Step 5: Validate
        validator = APIValidator()
        validation = validator.validate(result.get("response"), structured_plan.get("expected_schema"))
        
        # Save execution
        execution_run = APIExecutionRun(
            test_case_id=test_case.id,
            endpoint=api_request.get("url", ""),
            payload_json=api_request.get("payload"),
            response_json=result.get("response"),
            status=validation.get("status", "failed")
        )
        db.add(execution_run)
        db.commit()
        db.refresh(execution_run)
        
        return {
            "execution_id": execution_run.id,
            "test_case_id": test_case.id,
            "status": validation.get("status"),
            "request": api_request,
            "response": result.get("response"),
            "validation": validation,
            "message": "API test completed"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/results/{execution_id}")
async def get_api_results(execution_id: int, db: Session = Depends(get_db)):
    """Get API test execution results"""
    execution = db.query(APIExecutionRun).filter(APIExecutionRun.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    test_case = db.query(APITestCase).filter(APITestCase.id == execution.test_case_id).first()
    
    return {
        "execution_id": execution.id,
        "test_case_id": execution.test_case_id,
        "endpoint": execution.endpoint,
        "status": execution.status,
        "payload": execution.payload_json,
        "response": execution.response_json,
        "created_at": execution.created_at,
        "test_plan": test_case.structured_json if test_case else None
    }

@router.get("/schema-cache")
async def get_schema_cache(db: Session = Depends(get_db)):
    """Get cached API schemas"""
    schemas = db.query(APISchemaCache).all()
    return {
        "schemas": [
            {
                "endpoint": s.endpoint,
                "schema": s.schema_json,
                "version": s.version
            }
            for s in schemas
        ]
    }
