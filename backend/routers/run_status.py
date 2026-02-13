"""
API Router for Run Status - Frontend polling endpoint
Solves: Problem #2 (Frontend can't display screenshots until run completes)
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

from services.ui_automation.run_status import get_tracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ui-automation/runs", tags=["run-status"])


@router.get("/{run_id}/status")
async def get_run_status(run_id: str) -> Dict[str, Any]:
    """
    Get current status of test run.
    
    Frontend can poll this endpoint every 2-5 seconds to:
    - Show current phase (e.g., "Crawling pages...")
    - Display progress percentage
    - Show screenshots as they become available
    - Display healing attempts in real-time
    - Show error messages if run fails
    
    Args:
        run_id: Unique run identifier
    
    Returns:
        {
            "run_id": str,
            "status": "running" | "completed" | "failed",
            "current_phase": str,
            "progress_percent": int,
            "phases": {...},
            "screenshots": [...],
            "healing_attempts": [...],
            "started_at": str,
            "completed_at": str | None,
            "duration_ms": int,
            "error": str | None
        }
    
    Example:
        GET /api/ui-automation/runs/run_12345/status
        
        Response:
        {
            "run_id": "run_12345",
            "status": "running",
            "current_phase": "execution",
            "progress_percent": 67,
            "screenshots": [
                {
                    "path": "screenshots/run_12345/step_1_click_20240211_120000.png",
                    "step_number": 1,
                    "phase": "execution",
                    "captured_at": "2024-02-11T12:00:00"
                }
            ],
            "healing_attempts": [
                {
                    "step_number": 2,
                    "original_selector": "button.login",
                    "healed_selector": "button:has-text('Login')",
                    "strategy": "fuzzy_match",
                    "success": true
                }
            ]
        }
    """
    logger.info(f"Status request for run_id={run_id}")
    
    tracker = get_tracker(run_id)
    
    if not tracker:
        logger.warning(f"Run not found: {run_id}")
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    status = tracker.get_status()
    
    logger.debug(
        f"Status for {run_id}: phase={status['current_phase']}, "
        f"progress={status['progress_percent']}%"
    )
    
    return status


@router.get("/{run_id}/screenshots")
async def get_run_screenshots(run_id: str) -> Dict[str, Any]:
    """
    Get all screenshots for a run.
    
    Args:
        run_id: Unique run identifier
    
    Returns:
        {
            "run_id": str,
            "screenshots": [...]
        }
    """
    logger.info(f"Screenshots request for run_id={run_id}")
    
    tracker = get_tracker(run_id)
    
    if not tracker:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    return {
        "run_id": run_id,
        "screenshots": tracker.screenshots
    }


@router.get("/{run_id}/healing")
async def get_run_healing_attempts(run_id: str) -> Dict[str, Any]:
    """
    Get all healing attempts for a run.
    
    Args:
        run_id: Unique run identifier
    
    Returns:
        {
            "run_id": str,
            "healing_attempts": [...]
        }
    """
    logger.info(f"Healing attempts request for run_id={run_id}")
    
    tracker = get_tracker(run_id)
    
    if not tracker:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    return {
        "run_id": run_id,
        "healing_attempts": tracker.healing_attempts
    }


@router.get("/{run_id}/phases")
async def get_run_phases(run_id: str) -> Dict[str, Any]:
    """
    Get detailed phase information for a run.
    
    Args:
        run_id: Unique run identifier
    
    Returns:
        {
            "run_id": str,
            "phases": {...}
        }
    """
    logger.info(f"Phases request for run_id={run_id}")
    
    tracker = get_tracker(run_id)
    
    if not tracker:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    
    return {
        "run_id": run_id,
        "phases": tracker.phases
    }
