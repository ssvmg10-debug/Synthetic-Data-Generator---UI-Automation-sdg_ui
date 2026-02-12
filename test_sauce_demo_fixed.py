"""
Test script to verify improved Sauce Demo test case handling
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_sauce_demo_improved():
    """Test the improved Sauce Demo workflow"""
    
    print("=" * 80)
    print("🧪 Testing Improved Sauce Demo Workflow")
    print("=" * 80)
    
    # Check backend health
    print("\n1️⃣ Checking backend health...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Backend is healthy!")
        else:
            print(f"⚠️ Backend returned: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Backend not reachable: {e}")
        return
    
    # Test case exactly as provided
    test_case = """1. open this application https://sauce-demo.myshopify.com/
2. Click on grey shirt and then click on add to cart , don't click on mycart
3. then click on checkout and then click on checkout
4. click on sign and continue as guest and them in checkout page fill all the required fields and click on paynow"""
    
    print("\n2️⃣ Submitting test case to UI Automation...")
    print(f"📝 Test case:\n{test_case}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/ui/run",
            json={"raw_input": test_case, "use_synthetic_data": True},
            timeout=120
        )
        
        print(f"\n✅ Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n📊 Test Results:")
            print(f"   Test Case ID: {data.get('testcase_id')}")
            print(f"   Execution ID: {data.get('execution_id')}")
            print(f"   Status: {data.get('status')}")
            print(f"   Script Length: {len(data.get('script', ''))} characters")
            
            # Print test plan
            if 'structured_plan' in data:
                plan = data['structured_plan']
                print(f"\n📋 Test Plan:")
                print(f"   Test Name: {plan.get('test_name')}")
                print(f"   URL: {plan.get('url')}")
                print(f"   Steps: {plan.get('total_steps')}")
                
                print("\n   Step Details:")
                for i, step in enumerate(plan.get('steps', [])[:10], 1):  # Show first 10 steps
                    action = step.get('action')
                    element = step.get('element', '')
                    selector = step.get('selector', '')
                    print(f"   {i}. {action.upper()}: {element}")
                    if selector and action != 'navigate' and action != 'comment':
                        print(f"      Selector: {selector[:80]}...")
            
            # Print partial script
            if 'script' in data:
                script = data['script']
                print(f"\n📄 Generated Script (first 500 chars):")
                print(f"   {script[:500]}...")
            
            # Print error if any
            if data.get('status') == 'failed' and 'error' in data:
                print(f"\n⚠️ Error: {data['error'][:200]}...")
            else:
                print("\n✅ Test execution completed!")
            
            return data
            
        else:
            print(f"❌ Request failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            
    except requests.Timeout:
        print("⏰ Request timed out (test may still be running)")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("\n🚀 Starting Sauce Demo Test with Improved Agents\n")
    time.sleep(2)  # Give backend time to start
    
    result = test_sauce_demo_improved()
    
    print("\n" + "=" * 80)
    print("✅ Test execution complete!")
    print("=" * 80)
    print("\n💡 Check the Streamlit UI to see the test execution!")
    print("   URL: http://localhost:8501")
    print("\n📂 Generated test file location:")
    print("   backend/test_outputs/test_XX.spec.js")
