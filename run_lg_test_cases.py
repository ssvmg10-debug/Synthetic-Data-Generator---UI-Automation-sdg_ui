"""
Run LG India test cases end-to-end. Target: 100% pass rate.

Usage:
  python run_lg_test_cases.py --list              # list all case ids and names
  python run_lg_test_cases.py                     # run first case only
  python run_lg_test_cases.py --all               # run ALL cases E2E (full suite)
  python run_lg_test_cases.py --all --report out # run all + write report
  python run_lg_test_cases.py --id lg_01_buy_tv_under_30k
  python run_lg_test_cases.py --all --fail-fast  # stop on first failure

Exit code: 0 only when all run tests passed (100%); else 1.
Requires backend running (e.g. uvicorn main:app --port 8000).
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

# Add backend to path so lg_test_cases can be imported from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
from lg_test_cases import LG_TEST_CASES, get_test_case_by_id

BASE = os.environ.get("VITE_API_URL") or os.environ.get("BACKEND_PORT") or "8000"
if not BASE.startswith("http"):
    BASE = f"http://localhost:{BASE}"


def post(path: str, body: dict, timeout: int = 500) -> Tuple[int | None, dict]:
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.status, json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        body_str = e.read().decode("utf-8", "replace")
        try:
            data = json.loads(body_str)
        except Exception:
            data = {"detail": body_str[:500]}
        return e.code, data
    except Exception as e:
        return None, {"error": str(e)}


def run_one(tc: dict, visible_browser: bool = True, timeout: int = 500) -> dict:
    """Run a single test case. Returns result dict with id, name, passed, status, error, etc."""
    body = {
        "raw_input": tc["text"],
        "use_synthetic_data": False,
        "script_language": "javascript",
        "visible_browser": visible_browser,
    }
    status, data = post("/ui/run", body, timeout=timeout)
    execution_status = data.get("status") if status == 200 else None
    passed = status == 200 and execution_status == "passed"
    error = data.get("error") or data.get("detail")
    if isinstance(error, dict):
        error = error.get("detail", str(error))[:500]
    elif error is not None:
        error = str(error)[:500]
    return {
        "id": tc["id"],
        "name": tc["name"],
        "http_status": status,
        "execution_status": execution_status,
        "passed": passed,
        "error": error,
        "execution_id": data.get("execution_id"),
        "test_case_id": data.get("test_case_id"),
        "healed": data.get("healed"),
        "step_screenshots": len(data.get("step_screenshots") or []),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Run LG India UI automation test cases end-to-end (target: 100% pass rate)"
    )
    parser.add_argument("--list", action="store_true", help="List all test case ids and names")
    parser.add_argument("--all", action="store_true", help="Run ALL test cases (full E2E suite)")
    parser.add_argument("--id", type=str, help="Run single test case by id")
    parser.add_argument("--index", type=int, default=0, help="Run test case by index 0..N-1 (default 0)")
    parser.add_argument("--report", type=str, metavar="PATH", help="Write JSON + Markdown report to PATH (e.g. reports/lg_e2e)")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure (only with --all)")
    parser.add_argument("--no-browser", action="store_true", help="Run Playwright headless (no visible browser)")
    parser.add_argument("--timeout", type=int, default=500, help="Request timeout per test in seconds (default 500)")
    args = parser.parse_args()

    if args.list:
        print(f"LG India test cases ({len(LG_TEST_CASES)} total):\n")
        for i, tc in enumerate(LG_TEST_CASES):
            print(f"  {i}: {tc['id']}")
            print(f"      {tc['name']}")
        return 0

    if args.id:
        tc = get_test_case_by_id(args.id)
        if not tc:
            print(f"Unknown test case id: {args.id}", file=sys.stderr)
            return 1
        cases = [tc]
    elif args.all:
        cases = LG_TEST_CASES
    else:
        idx = max(0, min(args.index, len(LG_TEST_CASES) - 1))
        cases = [LG_TEST_CASES[idx]]

    visible_browser = not args.no_browser
    results: List[dict] = []
    total = len(cases)
    def safe_print(s: str) -> None:
        """Print without Unicode errors on Windows console (cp1252)."""
        out = s.encode("ascii", errors="replace").decode("ascii")
        print(out)

    for i, tc in enumerate(cases):
        print("=" * 70)
        safe_print(f"[{i + 1}/{total}] {tc['id']}")
        safe_print(f"     {tc['name']}")
        print("=" * 70)
        start = time.time()
        result = run_one(tc, visible_browser=visible_browser, timeout=args.timeout)
        elapsed = time.time() - start
        result["elapsed_seconds"] = round(elapsed, 1)
        results.append(result)
        if result["passed"]:
            print(f"  PASSED  (execution_id={result.get('execution_id')}, {result['elapsed_seconds']}s)")
        else:
            print(f"  FAILED  (status={result.get('execution_status')}, {result['elapsed_seconds']}s)")
            err = result.get("error") or "unknown"
            safe_print(f"  Error: {err[:300]}{'...' if len(err) > 300 else ''}")
        print()
        if args.all and args.fail_fast and not result["passed"]:
            print("Stopping on first failure (--fail-fast).")
            break

    # Summary
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = len(results) - passed_count
    pass_rate = (100.0 * passed_count / len(results)) if results else 0

    print("=" * 70)
    print("LG INDIA E2E SUITE – SUMMARY")
    print("=" * 70)
    print(f"  Total:   {len(results)}")
    print(f"  Passed:  {passed_count}")
    print(f"  Failed:  {failed_count}")
    print(f"  Pass rate: {pass_rate:.1f}%  (Target: 100%)")
    print("=" * 70)

    if failed_count > 0:
        print("\nFailed cases:")
        for r in results:
            if not r["passed"]:
                safe_print(f"  - {r['id']}: {r.get('error') or r.get('execution_status')}")

    # Report files
    if args.report and results:
        base_path = args.report.rstrip(".json").rstrip(".md")
        os.makedirs(os.path.dirname(base_path) or ".", exist_ok=True)
        report_data = {
            "suite": "lg_india_e2e",
            "target": "100%",
            "run_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "total": len(results),
            "passed": passed_count,
            "failed": failed_count,
            "pass_rate_percent": round(pass_rate, 1),
            "results": results,
        }
        with open(base_path + ".json", "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        with open(base_path + ".md", "w", encoding="utf-8") as f:
            f.write("# LG India E2E – Run Report\n\n")
            f.write(f"**Run:** {report_data['run_at']}\n\n")
            f.write(f"| Total | Passed | Failed | Pass rate |\n")
            f.write(f"|-------|--------|--------|----------|\n")
            f.write(f"| {len(results)} | {passed_count} | {failed_count} | {pass_rate:.1f}% |\n\n")
            f.write("## Target: 100%\n\n")
            f.write("## Results\n\n")
            for r in results:
                status = "PASS" if r["passed"] else "FAIL"
                f.write(f"- **{r['id']}** – {status}  \n  {r['name']}\n")
                if not r["passed"] and r.get("error"):
                    f.write(f"  - Error: {r['error'][:200]}\n")
            f.write("\n")
        print(f"\nReport written: {base_path}.json, {base_path}.md")

    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
