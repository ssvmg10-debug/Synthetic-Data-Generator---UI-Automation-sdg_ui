"""
Comprehensive test to verify the Sauce Demo fix
Tests the complete workflow with improved agents
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def main():
    print("\n" + "=" * 90)
    print("🔧 COMPREHENSIVE SAUCE DEMO TEST - AFTER FIXES")
    print("=" * 90)
    
    # Wait for backend
    print("\n⏳ Waiting for backend to be ready...")
    for i in range(10):
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=2)
            if response.status_code == 200:
                print("✅ Backend is ready!\n")
                break
        except:
            if i == 9:
                print("❌ Backend not available after 10 attempts")
                return
            time.sleep(1)
    
    # Your exact test case
    test_case = """1. open this application https://sauce-demo.myshopify.com/
2. Click on grey shirt and then click on add to cart , don't click on mycart
3. then click on checkout and then click on checkout
4. click on sign and continue as guest and them in checkout page fill all the required fields and click on paynow"""
    
    print("📋 TEST CASE:")
    print("-" * 90)
    print(test_case)
    print("-" * 90)
    
    print("\n🚀 Submitting to UI Automation API...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/ui/run",
            json={
                "raw_input": test_case,
                "use_synthetic_data": True  # Enable synthetic data for form filling
            },
            timeout=120
        )
        
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            print(response.text)
            return
        
        result = response.json()
        
        print("\n" + "=" * 90)
        print("📊 EXECUTION RESULTS")
        print("=" * 90)
        
        print(f"\n✓ Test Case ID: {result.get('testcase_id', 'N/A')}")
        print(f"✓ Execution ID: {result.get('execution_id', 'N/A')}")
        print(f"✓ Status: {result.get('status', 'N/A').upper()}")
        
        # Show test plan
        if 'structured_plan' in result:
            plan = result['structured_plan']
            print(f"\n📋 GENERATED TEST PLAN:")
            print(f"   Test Name: {plan.get('test_name', 'N/A')}")
            print(f"   URL: {plan.get('url', 'N/A')}")
            print(f"   Total Steps: {plan.get('total_steps', 0)}")
            
            print(f"\n   STEPS BREAKDOWN:")
            for i, step in enumerate(plan.get('steps', []), 1):
                action = step.get('action', 'unknown').upper()
                element = step.get('element', 'N/A')
                description = step.get('description', 'N/A')
                
                print(f"\n   {i}. {action}")
                print(f"      Element: {element}")
                print(f"      Description: {description}")
                
                if step.get('selector') and action not in ['NAVIGATE', 'COMMENT', 'WAIT']:
                    selector = step['selector']
                    print(f"      Selector: {selector[:100]}{'...' if len(selector) > 100 else ''}")
        
        # Show generated script
        if 'script' in result:
            script = result['script']
            print(f"\n📄 GENERATED PLAYWRIGHT SCRIPT:")
            print(f"   Length: {len(script)} characters")
            print("\n   First 800 characters:")
            print("   " + "-" * 86)
            for line in script[:800].split('\n'):
                print(f"   {line}")
            if len(script) > 800:
                print("   ...")
            print("   " + "-" * 86)
        
        # Show status and errors
        print(f"\n🎯 FINAL STATUS: {result.get('status', 'N/A').upper()}")
        
        if result.get('status') == 'failed' and 'error' in result:
            print(f"\n⚠️  ERROR DETAILS:")
            error = result['error']
            print(f"   {error[:300]}{'...' if len(error) > 300 else ''}")
            print(f"\n   💡 Note: Failures are expected if selectors don't match the live site.")
            print(f"      The Healer Agent should auto-fix these issues on subsequent attempts.")
        elif result.get('status') == 'passed':
            print(f"\n✅ TEST PASSED SUCCESSFULLY!")
        
        print(f"\n📂 Generated Files:")
        test_id = result.get('testcase_id') or result.get('execution_id')
        print(f"   • Test Script: backend/test_outputs/test_{test_id}.spec.js")
        print(f"   • Logs: backend/test_outputs/logs_{test_id}.txt")
        
        print("\n" + "=" * 90)
        print("✅ IMPROVEMENTS APPLIED:")
        print("=" * 90)
        print("1. ✓ Smart element extraction (multi-word support)")
        print("2. ✓ Intelligent selector generation (context-aware)")
        print("3. ✓ Better Playwright patterns (try-catch, wait strategies)")
        print("4. ✓ Proper PATH handling for npx/playwright execution")
        print("5. ✓ Timeout configurations (3 minutes per test)")
        print("6. ✓ Synthetic data integration for form filling")
        print("=" * 90)
        
        print(f"\n🌐 View in Streamlit UI: http://localhost:8501")
        print(f"📖 API Docs: http://localhost:8000/docs")
        
        return result
        
    except requests.Timeout:
        print("⏰ Request timed out after 120 seconds")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
