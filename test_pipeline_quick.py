"""
Quick offline test: planner -> generator -> (no executor).
Verifies Phase 1-4 code paths load and run without browser.
Run from project root: python test_pipeline_quick.py
"""
import sys
import os
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    load_dotenv(BACKEND / ".env")
except ImportError:
    pass
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

def main():
    from db import SessionLocal
    from models import UITestCase, CrawlSnapshot
    from services.ui_automation.agents.planner.agent import PlannerAgent
    from services.ui_automation.agents.generator.agent import GeneratorAgent
    from services.ui_automation.agents.healer.agent import HealerAgent
    from services.ui_automation.crawler.test_case_crawler import generate_crawl_script, get_crawl_snapshots_for_flow

    raw = "https://www.lg.com/in\nGo to https://www.lg.com/in/\nWait 3 seconds\nClick Accept on cookie banner"
    print("1. Planner...")
    planner = PlannerAgent(use_llm=False)
    plan = planner.plan(raw)
    assert plan.get("steps"), "plan should have steps"
    print(f"   steps: {len(plan['steps'])}")

    print("2. Generator (with failure context capture)...")
    generator = GeneratorAgent()
    script = generator.generate(plan, language="javascript", capture_screenshots=False, capture_failure_context=True)
    assert "process.env" in script and ("FAILURE_CONTEXT_PATH" in script or "failure_context" in script)
    assert "test(" in script and "page.goto" in script
    print(f"   script length: {len(script)} chars")

    print("3. Healer (context-aware signature)...")
    healer = HealerAgent()
    import inspect
    params = list(inspect.signature(healer.heal).parameters)
    assert "test_case_context" in params
    assert "db" in params
    print(f"   heal() params: {params}")

    print("4. Crawler script generation...")
    crawl_script = generate_crawl_script(plan)
    assert "snapshots" in crawl_script and "capture" in crawl_script
    print(f"   crawl script length: {len(crawl_script)} chars")

    print("5. DB: CrawlSnapshot model and empty flow...")
    db = SessionLocal()
    try:
        snapshots = get_crawl_snapshots_for_flow(db, "lg_lg_01")
        print(f"   get_crawl_snapshots_for_flow('lg_lg_01') -> {len(snapshots)} snapshots")
    finally:
        db.close()

    print("6. Report generator (mock results)...")
    from services.ui_automation.report_generator import generate_html_report
    mock_results = [
        {"id": "lg_01", "name": "Cookie accept", "status": "passed", "duration_sec": 10.5, "plan": {"steps": [{"action": "navigate", "description": "Go to LG"}]}, "step_screenshots": []},
    ]
    report_path = ROOT / "reports" / "quick_test_report.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    out = generate_html_report("Quick test", mock_results, report_path, embed_screenshots=False)
    assert Path(out).exists()
    print(f"   report: {out}")

    print("\nAll quick checks passed. Pipeline is ready for full E2E (you run: python run_enterprise_e2e.py --limit 1).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
