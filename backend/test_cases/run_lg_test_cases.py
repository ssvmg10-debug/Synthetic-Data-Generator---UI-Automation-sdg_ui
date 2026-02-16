#!/usr/bin/env python3
"""
Run LG India test cases from lg_india_test_cases.json via POST /ui/run.
Usage (from backend):  python test_cases/run_lg_test_cases.py
Optional:  BASE_URL=http://localhost:8000  python test_cases/run_lg_test_cases.py
          RUN_FIRST=5  to run only the first 5 cases.
"""
import os
import sys
import json
import time

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
RUN_FIRST = int(os.environ.get("RUN_FIRST", "0"))  # 0 = all

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, "lg_india_test_cases.json")


def main():
    if not os.path.exists(JSON_PATH):
        print(f"Not found: {JSON_PATH}")
        sys.exit(1)
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("test_cases", [])
    if RUN_FIRST:
        cases = cases[:RUN_FIRST]
    print(f"Running {len(cases)} LG test cases against {BASE_URL}")
    results = []
    for tc in cases:
        tid = tc.get("id", "?")
        name = tc.get("name", "")[:50]
        raw = tc.get("raw_input", "")
        if not raw:
            continue
        print(f"\n[{tid}] {name}...")
        try:
            r = requests.post(
                f"{BASE_URL}/ui/run",
                json={"raw_input": raw, "visible_browser": False},
                timeout=600,
            )
            r.raise_for_status()
            body = r.json()
            status = body.get("status", body.get("message", "?"))
            exec_id = body.get("execution_id", "")
            print(f"  -> {status} (execution_id={exec_id})")
            results.append({"id": tid, "status": status, "execution_id": exec_id})
        except requests.exceptions.Timeout:
            print("  -> TIMEOUT")
            results.append({"id": tid, "status": "timeout", "execution_id": None})
        except Exception as e:
            print(f"  -> ERROR: {e}")
            results.append({"id": tid, "status": "error", "error": str(e)})
        time.sleep(2)
    passed = sum(1 for x in results if x.get("status") == "passed")
    print(f"\nDone: {passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
