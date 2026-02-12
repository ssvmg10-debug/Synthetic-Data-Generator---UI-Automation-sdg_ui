"""
Enterprise E2E runner: runs UI automation test cases for LG India and Hilti India,
collects per-step screenshots, and generates a professional HTML report.

Usage (from project root):
  python run_enterprise_e2e.py                    # run all (LG + Hilti)
  python run_enterprise_e2e.py --app lg          # LG India only
  python run_enterprise_e2e.py --app hilti       # Hilti India only
  python run_enterprise_e2e.py --limit 5         # run first 5 per app (for quick check)

Requires: backend with Planner, Generator, Executor; Playwright installed in backend/.
"""
import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
# Load .env from project root so DB and Azure config are available
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    load_dotenv(BACKEND / ".env")
except ImportError:
    pass
sys.path.insert(0, str(BACKEND))
if BACKEND.exists():
    os.chdir(BACKEND)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run enterprise UI automation and generate report")
    parser.add_argument("--app", choices=["lg", "hilti", "all"], default="all")
    parser.add_argument("--limit", type=int, default=None, help="Max test cases per application")
    parser.add_argument("--out", default=None, help="Output HTML report path")
    parser.add_argument("--no-screenshots", action="store_true", help="Disable step screenshots")
    parser.add_argument("--synthetic", action="store_true", help="Also run synthetic data crawl for same test cases")
    parser.add_argument("--crawl-first", action="store_true", help="Run test-case-driven crawl before automation; use crawl data for healer")
    args = parser.parse_args()

    from db import SessionLocal, init_db
    from models import UITestCase, UIExecutionRun, HealingHistory, WorkflowExecution
    from services.ui_automation.agents.planner.agent import PlannerAgent
    from services.ui_automation.agents.generator.agent import GeneratorAgent
    from services.ui_automation.agents.healer.agent import HealerAgent
    from services.ui_automation.engine.executor import PlaywrightExecutor
    from services.ui_automation.report_generator import generate_html_report
    from services.ui_automation.crawler.test_case_crawler import crawl_and_save, get_crawl_snapshots_for_flow

    tests_dir = ROOT / "tests" / "enterprise"
    if not tests_dir.exists():
        print("tests/enterprise/ not found. Create lg_india.json and hilti_india.json first.")
        return 1

    apps = []
    if args.app in ("lg", "all"):
        lg_file = tests_dir / "lg_india.json"
        if lg_file.exists():
            apps.append(("lg", json.loads(lg_file.read_text())))
    if args.app in ("hilti", "all"):
        hilti_file = tests_dir / "hilti_india.json"
        if hilti_file.exists():
            apps.append(("hilti", json.loads(hilti_file.read_text())))

    if not apps:
        print("No test data found.")
        return 1

    all_results = []
    for app_key, data in apps:
        application = data.get("application", app_key)
        base_url = data.get("base_url", "")
        cases = data.get("test_cases", [])
        if args.limit:
            cases = cases[: args.limit]
        print(f"Running {len(cases)} tests for {application}...")
        planner = PlannerAgent()
        generator = GeneratorAgent()
        healer = HealerAgent()
        executor = PlaywrightExecutor()
        db = SessionLocal()

        for tc in cases:
            tid = tc.get("id", "unknown")
            name = tc.get("name", tid)
            steps = tc.get("steps", [])
            raw_input = "\n".join([base_url or ""] + steps) if base_url else "\n".join(steps)
            start = time.time()
            result_entry = {
                "id": tid,
                "name": name,
                "application": application,
                "status": "failed",
                "duration_sec": 0,
                "plan": None,
                "step_screenshots": [],
                "error": None,
            }
            try:
                plan = planner.plan(raw_input)
                result_entry["plan"] = plan
                flow_signature = f"{app_key}_{tid}"
                if getattr(args, "crawl_first", False):
                    try:
                        crawl_and_save(flow_signature, plan, db, run_dir=BACKEND / "test_outputs" / "crawl" / flow_signature.replace("/", "_"))
                        print(f"    Crawl saved for {flow_signature}")
                    except Exception as crawl_err:
                        print(f"    Crawl skipped: {crawl_err}")
                script = generator.generate(
                    plan,
                    language="javascript",
                    capture_screenshots=not args.no_screenshots,
                )
                # Persist test case and script
                ui_tc = UITestCase(raw_input=raw_input, structured_json=plan, script=script)
                db.add(ui_tc)
                db.commit()
                db.refresh(ui_tc)
                exec_result = executor.execute(
                    script,
                    test_case_id=ui_tc.id,
                    capture_step_screenshots=not args.no_screenshots,
                )
                result_entry["status"] = exec_result.get("status", "failed")
                result_entry["step_screenshots"] = exec_result.get("step_screenshots", [])
                result_entry["error"] = exec_result.get("error")
                # Persist execution run to DB
                run_status = exec_result.get("status", "failed")
                execution_run = UIExecutionRun(
                    test_case_id=ui_tc.id,
                    status=run_status,
                    logs_path=exec_result.get("logs_path"),
                    screenshot_path=exec_result.get("screenshot_path"),
                )
                db.add(execution_run)
                db.commit()
                db.refresh(execution_run)
                if result_entry["status"] == "failed" and exec_result.get("error"):
                    plan_steps = plan.get("steps", [])
                    failed_step_index = exec_result.get("failed_step_index")
                    if failed_step_index is None and plan_steps:
                        failed_step_index = len(plan_steps)
                    steps_before = plan_steps[: (failed_step_index - 1)] if failed_step_index else plan_steps[:-1]
                    failure_page_elements = exec_result.get("failure_page_elements")
                    if not failure_page_elements and failed_step_index is not None:
                        try:
                            crawl_snapshots = get_crawl_snapshots_for_flow(db, flow_signature)
                            for snap in crawl_snapshots:
                                if snap["step_index"] == failed_step_index:
                                    failure_page_elements = snap.get("elements", [])
                                    break
                            if not failure_page_elements and crawl_snapshots:
                                for snap in reversed(crawl_snapshots):
                                    if snap["step_index"] <= failed_step_index and snap.get("elements"):
                                        failure_page_elements = snap["elements"]
                                        break
                        except Exception:
                            pass
                    healed = healer.heal(
                        script,
                        exec_result.get("error", ""),
                        db,
                        test_case_context={"test_id": tid, "name": name, "steps": steps},
                        plan=plan,
                        failed_step_index=failed_step_index,
                        steps_before_failure=steps_before,
                        failure_url=exec_result.get("failure_url"),
                        failure_page_elements=failure_page_elements,
                    )
                    # Phase 4: up to 2 heal+retry cycles
                    current_exec_result = exec_result
                    for heal_attempt in range(2):
                        if not healed.get("healed") or not healed.get("healed_script"):
                            break
                        current_script = healed["healed_script"]
                        hh = HealingHistory(
                            execution_id=execution_run.id,
                            failed_locator=healed.get("original_selector") or "",
                            healed_locator=healed.get("healed_locator") or "",
                            strategy_used=healed.get("strategy", "alternative"),
                            success=1,
                            confidence_score=int((healed.get("confidence") or 0) * 100),
                        )
                        db.add(hh)
                        if healed.get("healed_locator"):
                            el = healer._extract_element_name(healed.get("original_selector") or "element")
                            healer.update_registry(el, healed["healed_locator"], db)
                        db.commit()
                        exec_result2 = executor.execute(
                            current_script,
                            test_case_id=ui_tc.id,
                            capture_step_screenshots=not args.no_screenshots,
                        )
                        result_entry["status"] = exec_result2.get("status", "failed")
                        result_entry["step_screenshots"] = exec_result2.get("step_screenshots", [])
                        result_entry["error"] = exec_result2.get("error")
                        current_exec_result = exec_result2
                        if exec_result2.get("status") == "passed":
                            execution_run2 = UIExecutionRun(
                                test_case_id=ui_tc.id,
                                status="healed",
                                logs_path=exec_result2.get("logs_path"),
                                screenshot_path=exec_result2.get("screenshot_path"),
                            )
                            db.add(execution_run2)
                            db.commit()
                            break
                        current_error = exec_result2.get("error", "")
                        failure_page_elements = exec_result2.get("failure_page_elements")
                        if not failure_page_elements and exec_result2.get("failed_step_index") is not None:
                            try:
                                crawl_snapshots = get_crawl_snapshots_for_flow(db, flow_signature)
                                for snap in crawl_snapshots:
                                    if snap["step_index"] == exec_result2.get("failed_step_index"):
                                        failure_page_elements = snap.get("elements", [])
                                        break
                            except Exception:
                                pass
                        healed = healer.heal(
                            current_script,
                            current_error,
                            db,
                            test_case_context={"test_id": tid, "name": name, "steps": steps},
                            plan=plan,
                            failed_step_index=exec_result2.get("failed_step_index") or failed_step_index,
                            steps_before_failure=steps_before,
                            failure_url=exec_result2.get("failure_url"),
                            failure_page_elements=failure_page_elements,
                        )
                    if current_exec_result.get("status") != "passed" and current_exec_result != exec_result:
                        execution_run2 = UIExecutionRun(
                            test_case_id=ui_tc.id,
                            status="failed",
                            logs_path=current_exec_result.get("logs_path"),
                            screenshot_path=current_exec_result.get("screenshot_path"),
                        )
                        db.add(execution_run2)
                        db.commit()
            except Exception as e:
                result_entry["error"] = str(e)
            result_entry["duration_sec"] = round(time.time() - start, 2)
            # Persist workflow execution for traceability
            try:
                wf = WorkflowExecution(
                    thread_id=f"e2e_{tid}_{int(time.time() * 1000)}",
                    workflow_type="ui_automation",
                    status="completed" if result_entry["status"] == "passed" else "failed",
                    input_data={"test_id": tid, "name": name, "application": application, "raw_input_preview": raw_input[:400]},
                    output_data={"duration_sec": result_entry["duration_sec"], "error_preview": (result_entry.get("error") or "")[:500]},
                    completed_at=datetime.now(timezone.utc),
                )
                db.add(wf)
                db.commit()
            except Exception:
                db.rollback()
            all_results.append(result_entry)
            print(f"  {tid}: {result_entry['status']} ({result_entry['duration_sec']}s)")
        db.close()

    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out or (reports_dir / f"enterprise_ui_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
    out_path = Path(out_path)
    generate_html_report(
        title="Enterprise UI Automation Report – LG India & Hilti India",
        test_results=all_results,
        output_path=out_path,
        embed_screenshots=True,
        application=", ".join(d.get("application", "") for _, d in apps),
    )
    print(f"Report written to: {out_path}")

    if args.synthetic:
        from agents.synthetic_data.graph import run_synthetic_data_workflow
        syn_results = []
        for app_key, data in apps:
            application = data.get("application", app_key)
            base_url = data.get("base_url", "")
            cases = data.get("test_cases", [])
            if args.limit:
                cases = cases[: args.limit]
            combined = base_url + "\n\n" + "\n".join(
                s for tc in cases for s in tc.get("steps", [])
            )
            db = SessionLocal()
            try:
                out = run_synthetic_data_workflow(test_case=combined, num_rows=10, db=db)
                syn_results.append({
                    "application": application,
                    "status": out.get("status", "unknown"),
                    "run_id": out.get("run_id"),
                    "schema_id": out.get("schema_id"),
                    "rows": len(out.get("generated_data", [])),
                })
            except Exception as e:
                syn_results.append({"application": application, "status": "failed", "error": str(e)})
            finally:
                db.close()
        syn_path = reports_dir / f"synthetic_crawl_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        _write_synthetic_report(syn_results, syn_path)
        print(f"Synthetic crawl report: {syn_path}")

    return 0


def _write_synthetic_report(syn_results: list, path: Path) -> None:
    body = [
        "<!DOCTYPE html><html><head><meta charset='UTF-8'><title>Synthetic Data Crawl Report</title>",
        "<style>body{font-family:system-ui;margin:24px;background:#0f172a;color:#e2e8f0;} table{border-collapse:collapse;} th,td{padding:8px 16px;border:1px solid #334155;}</style></head><body>",
        "<h1>Synthetic Data – Test-Case-Driven Crawl Report</h1>",
        "<p>Crawl is driven by test case URLs and steps (not whole application).</p>",
        "<table><tr><th>Application</th><th>Status</th><th>Run ID</th><th>Schema ID</th><th>Rows</th><th>Error</th></tr>",
    ]
    for r in syn_results:
        body.append(
            f"<tr><td>{r.get('application','')}</td><td>{r.get('status','')}</td>"
            f"<td>{r.get('run_id') or '—'}</td><td>{r.get('schema_id') or '—'}</td><td>{r.get('rows') or '—'}</td>"
            f"<td>{r.get('error') or '—'}</td></tr>"
        )
    body.append("</table></body></html>")
    path.write_text("\n".join(body), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
