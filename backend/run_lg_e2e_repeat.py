#!/usr/bin/env python3
"""
Run the LG E2E test case multiple times via the V2 API.
Usage (backend must be running on port 8001):
  cd backend && python run_lg_e2e_repeat.py
  python -m backend.run_lg_e2e_repeat --runs 5 --port 8001
"""
import argparse
import sys
from pathlib import Path

_backend = Path(__file__).resolve().parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

import requests

LG_E2E_TEST = """
navigate to this application https://www.lg.com/in
then click on search option
then search for lg tv 108cm
then click on any product
then click on buynow
then fill the pincode as 500032
then click on check beside pincode
then select free delivery option
then click on checkout
then click on continue with this condition (complete purchase as guest)
then fill billing/shipping details
"""


def run_once(base_url: str, visible: bool = False) -> tuple[bool, str, int]:
    try:
        resp = requests.post(
            f"{base_url}/ui-automation-v2/run",
            json={"natural_language": LG_E2E_TEST.strip(), "visible_browser": visible},
            timeout=600,
        )
    except requests.exceptions.ConnectionError as e:
        return False, f"Backend not reachable at {base_url}. Start backend first (e.g. .\\start_backend.ps1)", 0
    if resp.status_code != 200:
        return False, resp.text or f"HTTP {resp.status_code}", 0
    data = resp.json()
    passed = data.get("passed", False)
    executed = data.get("executed_steps", 0)
    total = data.get("total_steps", 0)
    err = data.get("error") or ("OK" if passed else f"Steps {executed}/{total}")
    return passed, err, executed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3, help="Number of runs")
    ap.add_argument("--port", type=int, default=8001, help="Backend port")
    ap.add_argument("--visible", action="store_true", help="Show browser")
    args = ap.parse_args()
    base_url = f"http://127.0.0.1:{args.port}"
    results = []
    for i in range(args.runs):
        print(f"\n--- Run {i + 1}/{args.runs} ---")
        ok, msg, steps = run_once(base_url, visible=args.visible)
        results.append(ok)
        print(f"  Passed: {ok}, Steps: {steps}, Msg: {msg}")
    passed = sum(results)
    total = len(results)
    print(f"\n=== Result: {passed}/{total} runs passed ({100 * passed / total if total else 0:.0f}%)")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
