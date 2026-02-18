#!/usr/bin/env python3
"""
Run the 3 UI automation test cases via the V2 API.
Usage (from repo root): python backend/run_ui_automation_testcases.py
Or from backend: python run_ui_automation_testcases.py

Ensure backend is running (e.g. .\start_backend.ps1) and set BACKEND_URL if needed.
"""
import os
import sys
import time

try:
    import httpx
except ImportError:
    print("Install httpx: pip install httpx")
    sys.exit(1)

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
V2_RUN = f"{BACKEND_URL}/ui-automation-v2/run"

TEST_CASES = [
    {
        "name": "LG flow: Air Solutions → Split AC → Product → Buy → Pincode → Delivery → Checkout → Guest → Billing → QR → Place order",
        "natural_language": """navigate to this application https://www.lg.com/in
then click on air solutions
then click on split air conditioners
then click on any one product
Then click on buynow
then fill the pincode as 500032,
then click on check beside pincode after that wait for 5 seconds
then select free delivery option in delivery method
then click on checkout
then click on continue with this condition (complete purchase as guest),
then fill billing/shipping details
then in payment click on QR code
then click on all checkboxes
then click on place order""",
    },
    {
        "name": "LG flow: Search → LG TV 108cm → Product → Buy → Pincode → Delivery → Checkout → Guest → Billing",
        "natural_language": """navigate to this application https://www.lg.com/in
then click on search option
then search for lg tv 108cm
then click on any product
then click on buynow
then fill the pincode as 500032,
then click on check beside pincode
then select free delivery option
then click on checkout
then click on continue with this condition (complete purchase as guest),
then fill billing/shipping details""",
    },
    {
        "name": "LG flow: Banner Buy Electronics → Audio → Party speakers → Product → Buy → … → Place order",
        "natural_language": """navigate to this application https://www.lg.com/in
On India ka passion LG ka celebration banner click on buy electronics & IT
click on Audio
Under filters, under category click on party speakers checkbox
then click on this product LG XBOOM RNC5, Deep Bass, Powerful Sound, Karaoke Bluetooth Party Speaker
Then click on buynow
then fill the pincode as 500032,
then click on check beside pincode after that wait for 5 seconds
then select free delivery option in delivery method
then click on checkout
then click on continue with this condition (complete purchase as guest),
then fill billing/shipping details
then in payment click on QR code
then click on all checkboxes
then click on place order""",
    },
]


def run_one(idx: int, tc: dict, visible: bool = True) -> bool:
    name = tc["name"]
    nl = tc["natural_language"]
    print(f"\n{'='*70}")
    print(f"Test case {idx + 1}/{len(TEST_CASES)}: {name[:70]}...")
    print(f"{'='*70}")
    try:
        with httpx.Client(timeout=300.0) as client:
            r = client.post(
                V2_RUN,
                json={
                    "natural_language": nl,
                    "visible_browser": visible,
                    "start_url": None,
                },
            )
        r.raise_for_status()
        data = r.json()
        passed = data.get("passed", False)
        steps = data.get("executed_steps", 0), data.get("total_steps", 0)
        duration = data.get("duration_ms", 0)
        error = data.get("error")
        print(f"  Result: {'PASS' if passed else 'FAIL'}")
        print(f"  Steps:  {steps[0]}/{steps[1]}")
        print(f"  Time:   {duration} ms")
        if error:
            print(f"  Error:  {error}")
        return passed
    except httpx.ConnectError as e:
        print(f"  ERROR: Cannot connect to backend at {BACKEND_URL}. Start it with .\\start_backend.ps1")
        print(f"  {e}")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    visible = "--headless" not in sys.argv
    if visible:
        print("Browser: visible (use --headless for headless)")
    else:
        print("Browser: headless")
    print(f"Backend: {BACKEND_URL}")
    results = []
    for i, tc in enumerate(TEST_CASES):
        ok = run_one(i, tc, visible=visible)
        results.append((tc["name"], ok))
        time.sleep(2)
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    for name, ok in results:
        print(f"  {'PASS' if ok else 'FAIL'}: {name[:60]}...")
    passed = sum(1 for _, ok in results if ok)
    print(f"\nTotal: {passed}/{len(results)} passed")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
