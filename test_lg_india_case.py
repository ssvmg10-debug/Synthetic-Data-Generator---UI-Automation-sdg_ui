"""
Run the LG India test case against Synthetic Data and UI Automation endpoints.
Usage: from project root, with backend running: python test_lg_india_case.py
"""
import json
import os
import sys
import urllib.request
import urllib.error

BASE = os.environ.get("VITE_API_URL") or os.environ.get("BACKEND_PORT") or "8001"
if not BASE.startswith("http"):
    BASE = f"http://localhost:{BASE}"

TEST_CASE = """navigate to this application https://www.lg.com/in
click on search option and search for lg 108cm tv and then click on buynow for any product under 30000
then fill the pincode as 500032, then click on check, then click on checkout
then click on continue with this condition (complete purchase as guest),
then fill billing/shipping details"""


def post(path, body):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=300)
        return resp.status, json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            data = json.loads(body)
        except Exception:
            data = {"detail": body[:500]}
        return e.code, data
    except Exception as e:
        return None, {"error": str(e)}


def main():
    print("=" * 60)
    print("LG India test case")
    print("=" * 60)
    print(TEST_CASE[:200] + "...")
    print()

    # 1) Synthetic Data
    print("[1] Synthetic Data Agent: POST /synthetic/generate-from-text")
    status, data = post("/synthetic/generate-from-text", {"user_input": TEST_CASE, "model": "GaussianCopula"})
    print(f"    Status: {status}")
    if status == 200:
        print(f"    Run ID: {data.get('run_id')}, Rows: {data.get('rows_generated', 0)}")
        if data.get("data"):
            print(f"    Sample row keys: {list(data['data'][0].keys()) if data['data'] else []}")
    else:
        print(f"    Error: {data.get('error') or data.get('detail', data)}")
    print()

    # 2) UI Automation
    print("[2] UI Automation Agent: POST /ui/run")
    status2, data2 = post(
        "/ui/run",
        {
            "raw_input": TEST_CASE,
            "use_synthetic_data": False,
            "script_language": "javascript",
        },
    )
    print(f"    Status: {status2}")
    if status2 == 200:
        print(f"    Execution ID: {data2.get('execution_id')}, Status: {data2.get('status')}, Healed: {data2.get('healed')}")
        if data2.get("plan", {}).get("steps"):
            print(f"    Plan steps: {len(data2['plan']['steps'])}")
    else:
        print(f"    Error: {data2.get('error') or data2.get('detail', data2)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
    sys.exit(0)
