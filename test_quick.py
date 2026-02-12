"""
Quick UI Automation Test - Direct API Testing
"""
import requests
import json

BACKEND_URL = "http://localhost:8000"

def test_simple():
    """Test the complete flow"""
    
    # Test 1: LG Website
    print("\n" + "="*80)
    print("TEST 1: LG TV Purchase")
    print("="*80)
    
    test_input = """
    Navigate to https://www.lg.com/in
    Click on search and search for 'lg 108cm tv'
    Click Buy Now for any product under 30000
    Fill pincode 500032 and click check
    Click checkout
    Continue as guest
    Fill billing details
    """
    
    # Plan
    print("📋 Creating test plan...")
    plan_resp = requests.post(f"{BACKEND_URL}/ui/plan", json={
        "raw_input": test_input
    })
    
    print(f"Status: {plan_resp.status_code}")
    if plan_resp.status_code == 200:
        data = plan_resp.json()
        print(f"✅ Plan created! Test case ID: {data.get('test_case_id')}")
        print(f"Plan: {json.dumps(data.get('plan', {}), indent=2)[:500]}...")
        
        test_case_id = data.get('test_case_id')
        
        # Generate
        print("\n🔨 Generating script...")
        gen_resp = requests.post(f"{BACKEND_URL}/ui/generate", json={
            "test_case_id": test_case_id
        })
        
        if gen_resp.status_code == 200:
            gen_data = gen_resp.json()
            print(f"✅ Script generated!")
            print(f"Script preview: {gen_data.get('script', '')[:300]}...")
            
            # Execute
            print("\n🚀 Executing test...")
            exec_resp = requests.post(f"{BACKEND_URL}/ui/execute", json={
                "test_case_id": test_case_id
            })
            
            if exec_resp.status_code == 200:
                exec_data = exec_resp.json()
                print(f"✅ Execution completed!")
                print(f"Status: {exec_data.get('status')}")
                print(f"Run ID: {exec_data.get('run_id')}")
            else:
                print(f"❌ Execution failed: {exec_resp.text}")
        else:
            print(f"❌ Generation failed: {gen_resp.text}")
    else:
        print(f"❌ Planning failed: {plan_resp.text}")


if __name__ == "__main__":
    # Check backend
    try:
        health = requests.get(f"{BACKEND_URL}/health", timeout=5)
        if health.status_code == 200:
            print("✅ Backend is running")
            test_simple()
        else:
            print("❌ Backend not healthy")
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
