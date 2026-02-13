"""
Run Status API - Phase-aware execution tracking with screenshot availability
Solves: Problem #2 (Frontend can't display screenshots until run completes)
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class ExecutionPhase(str, Enum):
    """Test execution phases"""
    JOURNEY_EXTRACTION = "journey_extraction"  # Parsing test case
    FOCUSED_CRAWLING = "focused_crawling"      # Crawling relevant pages
    CONTEXT_EXTRACTION = "context_extraction"  # Extracting page elements
    PLANNING = "planning"                      # Generating test script
    GENERATION = "generation"                  # Script validation
    EXECUTION = "execution"                    # Running test
    HEALING = "healing"                        # Self-healing failed steps
    VALIDATION = "validation"                  # Validating results
    COMPLETED = "completed"                    # Test finished
    FAILED = "failed"                          # Test failed


class PhaseStatus(str, Enum):
    """Status of individual phase"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunStatusTracker:
    """
    Tracks test execution through multiple phases.
    
    Features:
    - Phase-by-phase progress tracking
    - Screenshot availability tracking
    - Real-time status updates
    - Error capture per phase
    - Duration tracking
    
    Frontend can poll this API to:
    - Show current phase (e.g., "Crawling pages...")
    - Display screenshots as they become available
    - Show healing attempts in real-time
    - Estimate completion time
    
    Example:
        tracker = RunStatusTracker("run_12345")
        
        # Start journey extraction
        tracker.start_phase(ExecutionPhase.JOURNEY_EXTRACTION)
        # ... do work ...
        tracker.complete_phase(ExecutionPhase.JOURNEY_EXTRACTION, {
            "journey_name": "Login Flow",
            "steps": 5
        })
        
        # Execution with screenshot
        tracker.start_phase(ExecutionPhase.EXECUTION)
        tracker.add_screenshot("step_1_login.png", step_number=1)
        tracker.complete_phase(ExecutionPhase.EXECUTION, {"success": True})
        
        # Get status for frontend
        status = tracker.get_status()
        print(status['current_phase'])  # "execution"
        print(status['screenshots'])    # ["step_1_login.png"]
    """
    
    def __init__(self, run_id: str):
        """
        Initialize run status tracker.
        
        Args:
            run_id: Unique run identifier
        """
        self.run_id = run_id
        self.started_at = datetime.utcnow()
        self.current_phase = ExecutionPhase.JOURNEY_EXTRACTION
        self.completed_at: Optional[datetime] = None
        
        # Phase tracking
        self.phases: Dict[str, Dict[str, Any]] = {}
        self._initialize_phases()
        
        # Screenshots
        self.screenshots: List[Dict[str, Any]] = []
        
        # Healing attempts
        self.healing_attempts: List[Dict[str, Any]] = []
        
        # Overall status
        self.status = "running"
        self.error: Optional[str] = None
        
        logger.info(f"RunStatusTracker initialized for run_id={run_id}")
    
    def _initialize_phases(self):
        """Initialize all phases with pending status"""
        for phase in ExecutionPhase:
            self.phases[phase.value] = {
                "status": PhaseStatus.PENDING.value,
                "started_at": None,
                "completed_at": None,
                "duration_ms": None,
                "result": None,
                "error": None
            }
    
    def start_phase(self, phase: ExecutionPhase):
        """
        Mark phase as started.
        
        Args:
            phase: Phase to start
        """
        self.current_phase = phase
        self.phases[phase.value].update({
            "status": PhaseStatus.IN_PROGRESS.value,
            "started_at": datetime.utcnow().isoformat()
        })
        
        logger.info(f"[{self.run_id}] Started phase: {phase.value}")
    
    def complete_phase(
        self,
        phase: ExecutionPhase,
        result: Optional[Dict[str, Any]] = None
    ):
        """
        Mark phase as completed.
        
        Args:
            phase: Phase to complete
            result: Optional result data
        """
        phase_data = self.phases[phase.value]
        completed_at = datetime.utcnow()
        
        # Calculate duration
        if phase_data['started_at']:
            started = datetime.fromisoformat(phase_data['started_at'])
            duration_ms = int((completed_at - started).total_seconds() * 1000)
        else:
            duration_ms = 0
        
        phase_data.update({
            "status": PhaseStatus.COMPLETED.value,
            "completed_at": completed_at.isoformat(),
            "duration_ms": duration_ms,
            "result": result
        })
        
        logger.info(f"[{self.run_id}] Completed phase: {phase.value} ({duration_ms}ms)")
    
    def fail_phase(
        self,
        phase: ExecutionPhase,
        error: str
    ):
        """
        Mark phase as failed.
        
        Args:
            phase: Phase that failed
            error: Error message
        """
        phase_data = self.phases[phase.value]
        failed_at = datetime.utcnow()
        
        # Calculate duration
        if phase_data['started_at']:
            started = datetime.fromisoformat(phase_data['started_at'])
            duration_ms = int((failed_at - started).total_seconds() * 1000)
        else:
            duration_ms = 0
        
        phase_data.update({
            "status": PhaseStatus.FAILED.value,
            "completed_at": failed_at.isoformat(),
            "duration_ms": duration_ms,
            "error": error
        })
        
        self.status = "failed"
        self.error = f"{phase.value}: {error}"
        
        logger.error(f"[{self.run_id}] Failed phase: {phase.value} - {error}")
    
    def skip_phase(self, phase: ExecutionPhase, reason: str):
        """
        Mark phase as skipped.
        
        Args:
            phase: Phase to skip
            reason: Skip reason
        """
        self.phases[phase.value].update({
            "status": PhaseStatus.SKIPPED.value,
            "result": {"reason": reason}
        })
        
        logger.info(f"[{self.run_id}] Skipped phase: {phase.value} - {reason}")
    
    def add_screenshot(
        self,
        path: str,
        step_number: Optional[int] = None,
        phase: Optional[ExecutionPhase] = None,
        description: Optional[str] = None
    ):
        """
        Add screenshot to run.
        
        Args:
            path: Path to screenshot file
            step_number: Optional step number
            phase: Optional phase screenshot belongs to
            description: Optional description
        """
        screenshot = {
            "path": path,
            "step_number": step_number,
            "phase": phase.value if phase else self.current_phase.value,
            "description": description,
            "captured_at": datetime.utcnow().isoformat()
        }
        
        self.screenshots.append(screenshot)
        
        logger.info(
            f"[{self.run_id}] Screenshot added: {path} "
            f"(step={step_number}, phase={phase})"
        )
    
    def add_healing_attempt(
        self,
        step_number: int,
        original_selector: str,
        healed_selector: Optional[str],
        strategy: str,
        success: bool
    ):
        """
        Record healing attempt.
        
        Args:
            step_number: Step that needed healing
            original_selector: Original (failed) selector
            healed_selector: Healed selector (if found)
            strategy: Healing strategy used
            success: Whether healing succeeded
        """
        attempt = {
            "step_number": step_number,
            "original_selector": original_selector,
            "healed_selector": healed_selector,
            "strategy": strategy,
            "success": success,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.healing_attempts.append(attempt)
        
        logger.info(
            f"[{self.run_id}] Healing attempt: step={step_number}, "
            f"strategy={strategy}, success={success}"
        )
    
    def complete_run(self, success: bool):
        """
        Mark entire run as completed.
        
        Args:
            success: Whether run succeeded
        """
        self.completed_at = datetime.utcnow()
        self.status = "completed" if success else "failed"
        
        # Mark final phase
        if success:
            self.current_phase = ExecutionPhase.COMPLETED
        else:
            self.current_phase = ExecutionPhase.FAILED
        
        duration_s = (self.completed_at - self.started_at).total_seconds()
        
        logger.info(
            f"[{self.run_id}] Run completed: status={self.status}, "
            f"duration={duration_s:.2f}s"
        )
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current run status for frontend polling.
        
        Returns:
            {
                "run_id": str,
                "status": "running" | "completed" | "failed",
                "current_phase": str,
                "phases": {...},
                "screenshots": [...],
                "healing_attempts": [...],
                "progress_percent": int,
                "started_at": str,
                "completed_at": str | None,
                "duration_ms": int | None,
                "error": str | None
            }
        """
        # Calculate progress
        total_phases = len(ExecutionPhase)
        completed_phases = sum(
            1 for p in self.phases.values()
            if p['status'] in [PhaseStatus.COMPLETED.value, PhaseStatus.SKIPPED.value]
        )
        progress_percent = int((completed_phases / total_phases) * 100)
        
        # Calculate duration
        if self.completed_at:
            duration_ms = int((self.completed_at - self.started_at).total_seconds() * 1000)
        else:
            duration_ms = int((datetime.utcnow() - self.started_at).total_seconds() * 1000)
        
        return {
            "run_id": self.run_id,
            "status": self.status,
            "current_phase": self.current_phase.value,
            "phases": self.phases,
            "screenshots": self.screenshots,
            "healing_attempts": self.healing_attempts,
            "progress_percent": progress_percent,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": duration_ms,
            "error": self.error
        }
    
    def get_phase_summary(self) -> str:
        """
        Get human-readable phase summary for logging.
        
        Returns:
            Summary string like "5/9 phases completed (55%)"
        """
        total_phases = len(ExecutionPhase)
        completed_phases = sum(
            1 for p in self.phases.values()
            if p['status'] in [PhaseStatus.COMPLETED.value, PhaseStatus.SKIPPED.value]
        )
        progress_percent = int((completed_phases / total_phases) * 100)
        
        return f"{completed_phases}/{total_phases} phases completed ({progress_percent}%)"
    
    def to_json(self) -> str:
        """Export status as JSON string"""
        return json.dumps(self.get_status(), indent=2)


# In-memory storage (replace with database in production)
_run_trackers: Dict[str, RunStatusTracker] = {}


def get_or_create_tracker(run_id: str) -> RunStatusTracker:
    """Get existing tracker or create new one"""
    if run_id not in _run_trackers:
        _run_trackers[run_id] = RunStatusTracker(run_id)
    return _run_trackers[run_id]


def get_tracker(run_id: str) -> Optional[RunStatusTracker]:
    """Get existing tracker"""
    return _run_trackers.get(run_id)


def cleanup_old_trackers(max_age_hours: int = 24):
    """Clean up old trackers to prevent memory leak"""
    cutoff = datetime.utcnow().timestamp() - (max_age_hours * 3600)
    
    to_remove = []
    for run_id, tracker in _run_trackers.items():
        if tracker.started_at.timestamp() < cutoff:
            to_remove.append(run_id)
    
    for run_id in to_remove:
        del _run_trackers[run_id]
    
    if to_remove:
        logger.info(f"Cleaned up {len(to_remove)} old trackers")
