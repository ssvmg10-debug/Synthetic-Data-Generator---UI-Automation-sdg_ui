"""
Quick E2E Test for Chat-based UI
Tests both Synthetic Data and UI Automation flows
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_health():
    """Test if backend is running"""
    print("\n" + "="*80)
    print("🏥 Testing Backend Health...")
    print("="*80)
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Backend is healthy!")
            print(f"Response: {response.json()}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to backend: {str(e)}")
        print("\n💡 Make sure backend is running with: .\\start_backend.ps1")
        return False

def test_synthetic_data_natural_language():
    """Test natural language data generation"""
    print("\n" + "="*80)
    print("🧬 Testing Synthetic Data Generation (Natural Language)...")
    print("="*80)
    
    try:
        # Test request
        payload = {
            "user_input": "Generate 5 user profiles with email, name, and age",
            "model": "GaussianCopula"
        }
        
        print(f"\n📤 Request: {json.dumps(payload, indent=2)}")
        print("\n⏳ Sending request to backend...")
        
        response = requests.post(
            f"{BASE_URL}/synthetic/generate-from-text",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ Data Generated Successfully!")
            print(f"Run ID: {result.get('run_id')}")
            print(f"Schema ID: {result.get('schema_id')}")
            print(f"Rows Generated: {result.get('count')}")
            print(f"\n📊 Sample Data (first 2 rows):")
            print(json.dumps(result.get('data', [])[:2], indent=2))
            return True
        else:
            print(f"\n❌ Request failed: {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False

def test_ui_automation():
    """Test UI automation flow"""
    print("\n" + "="*80)
    print("🎭 Testing UI Automation (Natural Language)...")
    print("="*80)
    
    try:
        # Test request
        payload = {
            "raw_input": """Simple Google Search Test
1. Navigate to https://www.google.com
2. Type "Playwright automation" in search box
3. Press Enter
4. Wait for 3 seconds
5. Verify that search results are displayed"""
        }
        
        print(f"\n📤 Request: {payload['raw_input'][:100]}...")
        print("\n⏳ Sending request to backend...")
        print("⚠️  This will open a browser window...")
        
        response = requests.post(
            f"{BASE_URL}/ui/run",
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ Test Executed Successfully!")
            print(f"Execution ID: {result.get('execution_id')}")
            print(f"Test Case ID: {result.get('test_case_id')}")
            print(f"Status: {result.get('status')}")
            print(f"Self-Healed: {result.get('healed', False)}")
            
            if result.get('validation'):
                print(f"\n🔍 Validation: {result['validation']}")
            
            return True
        else:
            print(f"\n❌ Request failed: {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        return False

def main():
    print("\n" + "="*80)
    print("🧪 E2E Integration Test - Chat-based UI")
    print("="*80)
    print("\nThis test will verify:")
    print("  ✓ Backend server is running")
    print("  ✓ Synthetic data generation works")
    print("  ✓ UI automation works")
    print("\n" + "="*80)
    
    # Test 1: Health check
    if not test_health():
        print("\n❌ Cannot proceed without backend. Please start backend first.")
        return
    
    time.sleep(1)
    
    # Test 2: Synthetic Data
    print("\n⏳ Waiting 2 seconds before next test...")
    time.sleep(2)
    
    synthetic_success = test_synthetic_data_natural_language()
    
    time.sleep(1)
    
    # Test 3: UI Automation
    print("\n⏳ Waiting 2 seconds before next test...")
    time.sleep(2)
    
    ui_success = test_ui_automation()
    
    # Summary
    print("\n" + "="*80)
    print("📊 Test Summary")
    print("="*80)
    print(f"Backend Health: {'✅ PASS' if test_health() else '❌ FAIL'}")
    print(f"Synthetic Data: {'✅ PASS' if synthetic_success else '❌ FAIL'}")
    print(f"UI Automation: {'✅ PASS' if ui_success else '❌ FAIL'}")
    print("="*80)
    
    if synthetic_success and ui_success:
        print("\n🎉 All tests passed! System is working correctly.")
        print("\n💡 Next steps:")
        print("  1. Open http://localhost:8501 in your browser")
        print("  2. Try the Synthetic Data Generator chat interface")
        print("  3. Try the UI Automation chat interface")
        print("  4. Check logs in the backend terminal window")
    else:
        print("\n⚠️  Some tests failed. Check logs above for details.")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()
