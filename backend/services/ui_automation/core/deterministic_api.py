"""
🔒 DETERMINISTIC EXECUTION WRAPPER
Easy-to-use interface for the new deterministic architecture
"""
import asyncio
import logging
from playwright.async_api import async_playwright
from typing import Optional

from .deterministic_executor import DeterministicExecutor

logger = logging.getLogger(__name__)


async def execute_deterministic_test(
    test_case: str,
    start_url: str,
    visible: bool = False,
    timeout: int = 60000
) -> dict:
    """
    🔒 Execute test case with full deterministic architecture
    
    Features:
    - ✅ State machine validation
    - ✅ Intent-based execution (no text clicking)
    - ✅ Deterministic product selection
    - ✅ Post-condition validation
    - ✅ Execution checkpointing
    - ✅ Selector caching (learns from successful runs)
    - ✅ Environment reset (clean slate each run)
    - ✅ Strict failure policy (no drifting)
    
    Args:
        test_case: Natural language test case
                   Example: "Navigate to lg.com/in, click Air Solutions, 
                            click Split AC, select LG 4 Star Split AC, 
                            add to cart, enter pincode 560001, continue as guest"
        start_url: Starting URL (e.g., "https://www.lg.com/in")
        visible: Whether to run browser in visible mode
        timeout: Overall timeout in milliseconds
    
    Returns:
        {
            "success": bool,
            "steps_completed": int,
            "total_steps": int,
            "checkpoints": int,
            "final_state": str,
            "error": Optional[str]
        }
    
    Example:
        >>> result = await execute_deterministic_test(
        ...     test_case="Navigate to lg.com/in, click Air Solutions, select LG AC",
        ...     start_url="https://www.lg.com/in",
        ...     visible=False
        ... )
        >>> print(f"Success: {result['success']}")
        >>> print(f"Steps: {result['steps_completed']}/{result['total_steps']}")
    """
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=not visible,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=site-per-process',
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        
        page = await context.new_page()
        page.set_default_timeout(timeout)
        
        try:
            executor = DeterministicExecutor()
            result = await executor.execute_test_case(
                test_case=test_case,
                start_url=start_url,
                page=page,
                context=context,
                visible=visible
            )
            
            return result
            
        finally:
            await browser.close()


def execute_deterministic_test_sync(
    test_case: str,
    start_url: str,
    visible: bool = False,
    timeout: int = 60000
) -> dict:
    """
    Synchronous wrapper for execute_deterministic_test
    
    Same as execute_deterministic_test but can be called from sync code.
    
    Example:
        >>> result = execute_deterministic_test_sync(
        ...     test_case="Navigate to lg.com/in, click Air Solutions",
        ...     start_url="https://www.lg.com/in"
        ... )
    """
    return asyncio.run(execute_deterministic_test(test_case, start_url, visible, timeout))


# Export for easy imports
__all__ = [
    'execute_deterministic_test',
    'execute_deterministic_test_sync',
    'DeterministicExecutor'
]
