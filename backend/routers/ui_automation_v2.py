"""
🚀 NEW API ENDPOINT - Enhanced Deterministic System V2 Integration
Integrates the new semantic parser + assertion engine + enhanced executor
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
from pathlib import Path

from services.ui_automation.core.enhanced_deterministic_executor import DeterministicExecutorV2, ExecutionResult
from services.ui_automation.core.semantic_parser import SemanticTestParser

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
async def run_test_v2(request: TestRequestV2):
    """
    Execute test using Enhanced Deterministic System V2
    
    Features:
    - Semantic parsing (English → JSON DSL)
    - Assertions never click (only inspect)
    - Deterministic execution (no randomness)
    - State validation (before/after each step)
    - Smart waits (network idle, state changes)
    
    Example (Natural Language):
    ```json
    {
        "natural_language": "Navigate to https://www.lg.com/in, Click Air Solutions, Verify page loaded, Select LG AC",
        "visible_browser": true
    }
    ```
    
    Example (Enterprise Format):
    ```json
    {
        "enterprise_spec": {
            "Test Case ID": "TC_LG_001",
            "Objective": "Verify product selection",
            "Steps": [
                {"Step": "Navigate to homepage", "Expected Result": "Homepage loaded"},
                {"Step": "Click Air Solutions", "Expected Result": "Category displayed"}
            ]
        },
        "visible_browser": false
    }
    ```
    """
    logger.info("="*80)
    logger.info("ENHANCED DETERMINISTIC SYSTEM V2 - REQUEST RECEIVED")
    logger.info("="*80)
    
    try:
        # Import Playwright
        from playwright.async_api import async_playwright
        
        # Validate input
        if not request.natural_language and not request.enterprise_spec:
            raise HTTPException(
                status_code=400,
                detail="Either 'natural_language' or 'enterprise_spec' is required"
            )
        
        # Launch browser
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=not request.visible_browser)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()
            
            # Create executor
            executor = DeterministicExecutorV2(page, context)
            
            # Execute based on input format
            if request.natural_language:
                logger.info("Input: Natural Language")
                logger.info("Text: %s", request.natural_language[:100] + "..." if len(request.natural_language) > 100 else request.natural_language)
                
                result: ExecutionResult = await executor.execute_natural_language(
                    request.natural_language,
                    start_url=request.start_url
                )
            
            elif request.enterprise_spec:
                logger.info("Input: Enterprise Format")
                logger.info("Test Case ID: %s", request.enterprise_spec.get("Test Case ID", "N/A"))
                
                result: ExecutionResult = await executor.execute_enterprise_format(
                    request.enterprise_spec
                )
            
            # Close browser
            await browser.close()
        
        # Count assertion vs action steps
        from services.ui_automation.core.test_model import StepType
        
        # Parse test case to count step types
        if request.natural_language:
            test_case = SemanticTestParser.parse_natural_language(request.natural_language)
        else:
            test_case = SemanticTestParser.parse_enterprise_format(request.enterprise_spec)
        
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
        "system": "Enhanced Deterministic System V2",
        "features": [
            "Semantic parsing (English → JSON DSL)",
            "Assertion engine (never clicks)",
            "Deterministic execution",
            "State validation",
            "Smart waits"
        ]
    }
