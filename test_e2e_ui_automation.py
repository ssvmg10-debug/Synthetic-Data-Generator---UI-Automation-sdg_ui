"""
End-to-End UI Automation Tests
Testing 3 real-world scenarios
"""
import requests
import json
import time

BACKEND_URL = "http://localhost:8000"

def test_ui_automation(test_name, description, page_url):
    """Test UI automation end-to-end"""
    print(f"\n{'='*80}")
    print(f"🧪 TEST: {test_name}")
    print(f"{'='*80}")
    print(f"Description: {description}")
    print(f"URL: {page_url}")
    print()
    
    # Step 1: Plan
    print("📋 Step 1: Creating test plan...")
    plan_response = requests.post(
        f"{BACKEND_URL}/ui/plan",
        json={
            "feature_description": description,
            "page_url": page_url
        }
    )
    
    if plan_response.status_code != 200:
        print(f"❌ Planning failed: {plan_response.text}")
        return False
    
    plan_data = plan_response.json()
    print(f"✅ Test plan created!")
    print(json.dumps(plan_data.get('plan', {}), indent=2))
    
    # Step 2: Generate
    print("\n🔨 Step 2: Generating Playwright script...")
    generate_response = requests.post(
        f"{BACKEND_URL}/ui/generate",
        json={
            "test_plan": plan_data['plan'],
            "page_url": page_url
        }
    )
    
    if generate_response.status_code != 200:
        print(f"❌ Generation failed: {generate_response.text}")
        return False
    
    generate_data = generate_response.json()
    test_case_id = generate_data.get('test_case_id')
    print(f"✅ Test script generated! (ID: {test_case_id})")
    print("\n📝 Generated Script Preview:")
    print("-" * 80)
    script = generate_data.get('script', '')
    print(script[:500] + "..." if len(script) > 500 else script)
    print("-" * 80)
    
    # Step 3: Validate
    print("\n🔍 Step 3: Validating test script...")
    validate_response = requests.post(
        f"{BACKEND_URL}/ui/validate",
        json={"test_case_id": test_case_id}
    )
    
    if validate_response.status_code == 200:
        validate_data = validate_response.json()
        print(f"✅ Validation: {validate_data.get('validation_result', 'OK')}")
    
    # Step 4: Execute
    print("\n🚀 Step 4: Executing test...")
    execute_response = requests.post(
        f"{BACKEND_URL}/ui/execute",
        json={"test_case_id": test_case_id}
    )
    
    if execute_response.status_code != 200:
        print(f"❌ Execution failed: {execute_response.text}")
        return False
    
    execute_data = execute_response.json()
    run_id = execute_data.get('run_id')
    status = execute_data.get('status', 'unknown')
    
    print(f"\n📊 Execution Status: {status.upper()}")
    
    # Step 5: Get Results
    print("\n📈 Step 5: Fetching test results...")
    time.sleep(2)  # Wait for execution to complete
    
    results_response = requests.get(f"{BACKEND_URL}/ui/results/{run_id}")
    
    if results_response.status_code == 200:
        results_data = results_response.json()
        result = results_data.get('result', {})
        
        print(f"\n{'='*80}")
        print(f"📋 FINAL RESULTS")
        print(f"{'='*80}")
        print(f"Status: {result.get('status', 'N/A')}")
        print(f"Duration: {result.get('duration', 'N/A')}s")
        print(f"Started: {result.get('started_at', 'N/A')}")
        print(f"Completed: {result.get('completed_at', 'N/A')}")
        
        if result.get('logs'):
            print(f"\n📝 Logs:")
            print(result['logs'])
        
        if status == 'passed':
            print(f"\n✅ TEST PASSED!")
            return True
        else:
            print(f"\n❌ TEST FAILED!")
            return False
    else:
        print(f"❌ Could not fetch results: {results_response.text}")
        return False


def main():
    """Run all three test scenarios"""
    print("🚀 Starting End-to-End UI Automation Tests")
    print("=" * 80)
    
    # Test 1: LG Website
    test1_result = test_ui_automation(
        test_name="LG TV Purchase Flow",
        description="""
        Navigate to https://www.lg.com/in
        Click on search option and search for 'lg 108cm tv'
        Click on Buy Now for any product under 30000
        Fill the pincode as 500032
        Click on check
        Click on checkout
        Click on continue with condition 'complete purchase as guest'
        Fill billing/shipping details
        """,
        page_url="https://www.lg.com/in"
    )
    
    # Test 2: Sauce Demo Shopify
    test2_result = test_ui_automation(
        test_name="Sauce Demo Shopping Cart",
        description="""
        Open https://sauce-demo.myshopify.com/
        Click on grey shirt
        Click on add to cart (don't click on mycart)
        Click on checkout
        Click on checkout again
        Click on sign and continue as guest
        In checkout page fill all the required fields
        Click on paynow
        """,
        page_url="https://sauce-demo.myshopify.com/"
    )
    
    # Test 3: Hilti Website
    test3_result = test_ui_automation(
        test_name="Hilti Power Tools Purchase",
        description="""
        Open https://www.hilti.in/
        Navigate to power tools
        Navigate to rotary hammers
        Click on any item
        Add to cart
        Checkout
        """,
        page_url="https://www.hilti.in/"
    )
    
    # Summary
    print("\n\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print(f"Test 1 (LG): {'✅ PASSED' if test1_result else '❌ FAILED'}")
    print(f"Test 2 (Sauce Demo): {'✅ PASSED' if test2_result else '❌ FAILED'}")
    print(f"Test 3 (Hilti): {'✅ PASSED' if test3_result else '❌ FAILED'}")
    print("=" * 80)
    
    total = 3
    passed = sum([test1_result, test2_result, test3_result])
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")


if __name__ == "__main__":
    # Check backend health first
    try:
        health = requests.get(f"{BACKEND_URL}/health")
        if health.status_code == 200:
            print("✅ Backend is healthy and ready")
            main()
        else:
            print("❌ Backend is not healthy")
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        print("Please ensure backend is running on http://localhost:8000")
