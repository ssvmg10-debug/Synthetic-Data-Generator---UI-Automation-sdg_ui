"""
Intent-Based Executor
Production-grade intent-driven UI automation executor
"""
import logging
import time
from playwright.async_api import Page, Browser
from typing import List, Dict, Any
from services.ui_automation.core.intent_models import Intent, IntentResult
from services.ui_automation.core.intent_planner import IntentPlanner
from services.ui_automation.core.flow_router import FlowRouter

logger = logging.getLogger(__name__)


class IntentExecutor:
    """
    Intent-based automation executor.
    
    Architecture:
    User Test Case → IntentPlanner → List[Intent] → FlowRouter → Results
    
    Key improvements:
    1. Semantic intents instead of text steps
    2. State validation after each intent
    3. Specialized flow executors
    4. Deterministic retry (max 1)
    5. Controlled resolver with limits
    """
    
    def __init__(self):
        self.planner = IntentPlanner()
        self.router = FlowRouter()
    
    async def execute_test_case(
        self,
        page: Page,
        test_case: str,
        url: str
    ) -> Dict[str, Any]:
        """
        Execute test case using intent-based automation.
        
        Args:
            page: Playwright page
            test_case: Natural language test case
            url: Starting URL
        
        Returns:
            Execution report with metrics
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 INTENT-BASED EXECUTOR")
        logger.info(f"Test Case: {test_case}")
        logger.info(f"URL: {url}")
        logger.info(f"{'='*80}\n")
        
        start_time = time.time()
        
        # Phase 1: Plan intents
        logger.info("📋 Phase 1: Planning intents...")
        intents = await self.planner.plan(test_case, url)
        
        if not intents:
            logger.error("❌ Planning failed - no intents generated")
            return {
                "success": False,
                "error": "Planning failed",
                "total_time": time.time() - start_time
            }
        
        logger.info(f"✅ Generated {len(intents)} intents")
        for i, intent in enumerate(intents, 1):
            logger.info(f"  {i}. {intent}")
        
        # Phase 2: Execute intents
        logger.info(f"\n{'='*80}")
        logger.info("🎬 Phase 2: Executing intents...")
        logger.info(f"{'='*80}\n")
        
        results: List[IntentResult] = []
        success_count = 0
        failure_count = 0
        
        for i, intent in enumerate(intents, 1):
            logger.info(f"\n[Intent {i}/{len(intents)}]")
            
            result = await self.router.execute_intent(page, intent, retry_on_failure=True)
            results.append(result)
            
            if result.success:
                success_count += 1
            else:
                failure_count += 1
                
                # Decide whether to continue or stop
                if self._should_stop_on_failure(intent, result):
                    logger.error("🛑 Critical failure - stopping execution")
                    break
        
        total_time = time.time() - start_time
        
        # Phase 3: Generate report
        logger.info(f"\n{'='*80}")
        logger.info("📊 Execution Summary")
        logger.info(f"{'='*80}")
        logger.info(f"Total Intents: {len(intents)}")
        logger.info(f"Success: {success_count}")
        logger.info(f"Failed: {failure_count}")
        logger.info(f"Total Time: {total_time:.2f}s")
        logger.info(f"{'='*80}\n")
        
        report = self._generate_report(intents, results, total_time)
        
        return report
    
    def _should_stop_on_failure(self, intent: Intent, result: IntentResult) -> bool:
        """
        Decide whether to stop execution on failure.
        
        Critical intents (stop on failure):
        - NAVIGATE
        - SEARCH_PRODUCT
        - SELECT_PRODUCT
        
        Non-critical (continue):
        - VIEW_CART
        - VERIFY_TEXT
        """
        critical_intents = [
            "NAVIGATE",
            "SEARCH_PRODUCT",
            "SELECT_PRODUCT",
        ]
        
        intent_str = str(intent.intent)
        return intent_str in critical_intents
    
    def _generate_report(
        self,
        intents: List[Intent],
        results: List[IntentResult],
        total_time: float
    ) -> Dict[str, Any]:
        """Generate execution report"""
        
        success_count = sum(1 for r in results if r.success)
        failure_count = len(results) - success_count
        
        # Per-intent breakdown
        intent_breakdown = []
        for intent, result in zip(intents[:len(results)], results):
            intent_breakdown.append({
                "intent": str(intent.intent),
                "success": result.success,
                "execution_time": result.execution_time,
                "state_validated": result.state_validated,
                "retry_attempted": result.retry_attempted,
                "error": result.error
            })
        
        # Phase usage stats
        phase_stats = {
            "flow_executors": sum(1 for r in results if r.phase_used and "flow" in r.phase_used),
            "resolver": sum(1 for r in results if r.phase_used and "resolver" in r.phase_used),
            "retry": sum(1 for r in results if r.retry_attempted)
        }
        
        return {
            "success": failure_count == 0,
            "total_intents": len(intents),
            "executed_intents": len(results),
            "success_count": success_count,
            "failure_count": failure_count,
            "total_time": total_time,
            "avg_time_per_intent": total_time / len(results) if results else 0,
            "phase_stats": phase_stats,
            "intent_breakdown": intent_breakdown
        }


async def execute_test_case_with_intents(
    page: Page,
    test_case: str,
    url: str
) -> Dict[str, Any]:
    """
    Convenience function for intent-based execution.
    
    Args:
        page: Playwright page
        test_case: Natural language test case
        url: Starting URL
    
    Returns:
        Execution report
    """
    executor = IntentExecutor()
    return await executor.execute_test_case(page, test_case, url)
