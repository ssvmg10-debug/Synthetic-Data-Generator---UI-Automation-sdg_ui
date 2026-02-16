"""
Observability & Telemetry – placeholder for Prometheus/Grafana metrics.
Metrics: per-test pass %, per-step flakiness, healing success rates, average runtime, auto-fixed selectors.
Structured logs (step_id, attempt, selector_used, healed_flag) are emitted from EnhancedExecutor.
"""
from typing import Dict, Any

# In-memory counters (replace with Prometheus client in production)
_counters: Dict[str, int] = {
    "runs_total": 0,
    "runs_passed": 0,
    "runs_failed": 0,
    "steps_total": 0,
    "steps_healed": 0,
    "steps_failed": 0,
}


def increment(name: str, value: int = 1) -> None:
    _counters[name] = _counters.get(name, 0) + value


def get_counters() -> Dict[str, int]:
    return dict(_counters)


def reset_counters() -> None:
    _counters.clear()
    for k in ["runs_total", "runs_passed", "runs_failed", "steps_total", "steps_healed", "steps_failed"]:
        _counters[k] = 0


def record_run(success: bool, steps_executed: int, steps_healed: int, steps_failed: int) -> None:
    """Call after each run completes. Updates all run/step counters and KPIs."""
    increment("runs_total")
    if success:
        increment("runs_passed")
    else:
        increment("runs_failed")
    increment("steps_total", steps_executed)
    increment("steps_healed", steps_healed)
    increment("steps_failed", steps_failed)


def get_kpis() -> Dict[str, Any]:
    """Return counters plus derived KPIs for POC dashboard (no Grafana)."""
    c = get_counters()
    total = c.get("runs_total", 0)
    passed = c.get("runs_passed", 0)
    return {
        **c,
        "pass_rate_pct": round(100.0 * passed / total, 1) if total else 0,
        "heal_rate": c.get("steps_healed", 0),
    }
