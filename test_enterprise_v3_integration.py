"""
Quick test to verify Enterprise v3 API integration

This script tests that the Enterprise v3 architecture is properly
integrated with the API endpoints.
"""
import requests
import json
import sys

BASE_URL = "http://localhost:8004"

def test_enterprise_v3_endpoint():
    """Test the dedicated Enterprise v3 endpoint"""
    print("="*80)
    print("TEST 1: Dedicated Enterprise v3 Endpoint")
    print("="*80)
    
    endpoint = f"{BASE_URL}/api/ui-automation/run-enterprise-v3"
    payload = {
        "raw_input": "Navigate to https://sauce-demo.myshopify.com/ and click the first product",
        "visible_browser": False  # Headless for quick test
    }
    
    print(f"\nEndpoint: {endpoint}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("\nSending request...")
    
    try:
        response = requests.post(endpoint, json=payload, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ SUCCESS - Enterprise v3 endpoint working!")
            print(f"\nExecution ID: {result.get('execution_id')}")
            print(f"Status: {result.get('status')}")
            print(f"Architecture: {result.get('architecture')}")
            print(f"Health Score: {result.get('health_score')}")
            print(f"Healing Attempts: {result.get('healing_attempts')}")
            print(f"Exploration Count: {result.get('exploration_count')}")
            print(f"Steps Executed: {result.get('steps_executed')}")
            print(f"\nFeatures: {', '.join(result.get('features', []))}")
            return True
        else:
            print(f"\n❌ FAILED - Status code: {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("\n❌ FAILED - Cannot connect to backend")
        print("Make sure backend is running: python backend/run_uvicorn.py")
        return False
    except Exception as e:
        print(f"\n❌ FAILED - Error: {str(e)}")
        return False


def test_enterprise_v3_flag():
    """Test the existing endpoint with use_enterprise_v3 flag"""
    print("\n" + "="*80)
    print("TEST 2: Existing Endpoint with use_enterprise_v3 Flag")
    print("="*80)
    
    endpoint = f"{BASE_URL}/api/ui-automation/run"
    payload = {
        "raw_input": "Navigate to https://sauce-demo.myshopify.com/",
        "use_enterprise_v3": True,  # Enable Enterprise v3
        "visible_browser": False
    }
    
    print(f"\nEndpoint: {endpoint}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("\nSending request...")
    
    try:
        response = requests.post(endpoint, json=payload, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            
            # Check if Enterprise v3 features are present
            has_health_score = 'health_score' in result
            has_confidence = 'confidence_scores' in result
            has_exploration = 'exploration_count' in result
            is_enterprise = result.get('enterprise_v3', False)
            
            if has_health_score and has_confidence and has_exploration:
                print("\n✅ SUCCESS - Enterprise v3 flag working!")
                print(f"\nExecution ID: {result.get('execution_id')}")
                print(f"Status: {result.get('status')}")
                print(f"Enterprise v3: {is_enterprise}")
                print(f"Health Score: {result.get('health_score')}")
                print(f"Healing Attempts: {result.get('steps_healed')}")
                print(f"Exploration Count: {result.get('exploration_count')}")
                return True
            else:
                print("\n⚠️  WARNING - Endpoint responded but missing Enterprise v3 features")
                print(f"Has health_score: {has_health_score}")
                print(f"Has confidence_scores: {has_confidence}")
                print(f"Has exploration_count: {has_exploration}")
                return False
        else:
            print(f"\n❌ FAILED - Status code: {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("\n❌ FAILED - Cannot connect to backend")
        print("Make sure backend is running: python backend/run_uvicorn.py")
        return False
    except Exception as e:
        print(f"\n❌ FAILED - Error: {str(e)}")
        return False


def check_api_docs():
    """Check if API docs include the new Enterprise v3 endpoints"""
    print("\n" + "="*80)
    print("TEST 3: API Documentation Check")
    print("="*80)
    
    try:
        # Check OpenAPI schema
        response = requests.get(f"{BASE_URL}/openapi.json", timeout=10)
        
        if response.status_code == 200:
            schema = response.json()
            paths = schema.get('paths', {})
            
            has_v3_endpoint = '/api/ui-automation/run-enterprise-v3' in paths
            has_metrics_endpoint = any('enterprise-v3/metrics' in path for path in paths.keys())
            
            print(f"\n✅ API docs accessible at {BASE_URL}/docs")
            print(f"\n/api/ui-automation/run-enterprise-v3 endpoint: {'✅ Found' if has_v3_endpoint else '❌ Not found'}")
            print(f"/api/ui-automation/enterprise-v3/metrics endpoint: {'✅ Found' if has_metrics_endpoint else '❌ Not found'}")
            
            return has_v3_endpoint
        else:
            print(f"\n⚠️  WARNING - Could not fetch API docs")
            return None
            
    except Exception as e:
        print(f"\n⚠️  WARNING - Could not check API docs: {str(e)}")
        return None


def main():
    """Run all integration tests"""
    print("\n🚀 ENTERPRISE V3 INTEGRATION TEST SUITE")
    print("="*80)
    print("\nThis test suite verifies that Enterprise v3 architecture")
    print("is properly integrated with the API endpoints.")
    print()
    
    results = []
    
    # Test 1: Check API docs
    api_docs_ok = check_api_docs()
    results.append(("API Documentation", api_docs_ok))
    
    # Test 2: Test dedicated endpoint
    test1_ok = test_enterprise_v3_endpoint()
    results.append(("Dedicated Enterprise v3 Endpoint", test1_ok))
    
    # Test 3: Test flag on existing endpoint
    test2_ok = test_enterprise_v3_flag()
    results.append(("Enterprise v3 Flag", test2_ok))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, result in results:
        if result is True:
            status = "✅ PASSED"
        elif result is False:
            status = "❌ FAILED"
        else:
            status = "⚠️  SKIPPED"
        print(f"{test_name}: {status}")
    
    passed = sum(1 for _, r in results if r is True)
    total = len([r for r in results if r is not None])
    
    print(f"\nResult: {passed}/{total} tests passed")
    print("="*80)
    
    if passed == total and total > 0:
        print("\n✅ ALL TESTS PASSED - Enterprise v3 integration successful!")
        return 0
    elif passed > 0:
        print("\n⚠️  PARTIAL SUCCESS - Some tests failed")
        return 1
    else:
        print("\n❌ ALL TESTS FAILED - Integration needs fixing")
        return 2


if __name__ == "__main__":
    sys.exit(main())
