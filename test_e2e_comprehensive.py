"""
Comprehensive End-to-End Testing Report
Tests both Synthetic Data Generator and UI Automation
"""
import requests
import json
import time
from datetime import datetime

BACKEND_URL = "http://localhost:8000"

class TestReport:
    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "synthetic_data_tests": [],
            "ui_automation_tests": [],
            "summary": {}
        }
    
    def add_synthetic_test(self, test_name, result):
        self.results["synthetic_data_tests"].append({
            "test_name": test_name,
            "result": result
        })
    
    def add_ui_test(self, test_name, result):
        self.results["ui_automation_tests"].append({
            "test_name": test_name,
            "result": result
        })
    
    def generate_report(self):
        synthetic_passed = sum(1 for t in self.results["synthetic_data_tests"] if t["result"]["status"] == "PASSED")
        synthetic_total = len(self.results["synthetic_data_tests"])
        
        ui_passed = sum(1 for t in self.results["ui_automation_tests"] if t["result"]["status"] == "PASSED")
        ui_total = len(self.results["ui_automation_tests"])
        
        self.results["summary"] = {
            "synthetic_data": {
                "total": synthetic_total,
                "passed": synthetic_passed,
                "failed": synthetic_total - synthetic_passed,
                "success_rate": f"{(synthetic_passed/synthetic_total*100) if synthetic_total > 0 else 0:.1f}%"
            },
            "ui_automation": {
                "total": ui_total,
                "passed": ui_passed,
                "failed": ui_total - ui_passed,
                "success_rate": f"{(ui_passed/ui_total*100) if ui_total > 0 else 0:.1f}%"
            },
            "overall": {
                "total": synthetic_total + ui_total,
                "passed": synthetic_passed + ui_passed,
                "failed": (synthetic_total - synthetic_passed) + (ui_total - ui_passed),
                "success_rate": f"{((synthetic_passed + ui_passed)/(synthetic_total + ui_total)*100) if (synthetic_total + ui_total) > 0 else 0:.1f}%"
            }
        }
        
        return self.results
    
    def print_report(self):
        print("\n" + "="*100)
        print("📊 END-TO-END TESTING REPORT")
        print("="*100)
        print(f"Test Run: {self.results['timestamp']}")
        print()
        
        # Synthetic Data Tests
        print("🧬 SYNTHETIC DATA GENERATOR TESTS")
        print("-"*100)
        for test in self.results["synthetic_data_tests"]:
            status_icon = "✅" if test["result"]["status"] == "PASSED" else "❌"
            print(f"{status_icon} {test['test_name']}")
            print(f"   Status: {test['result']['status']}")
            print(f"   Details: {test['result']['details']}")
            if test['result'].get('rows_generated'):
                print(f"   Rows Generated: {test['result']['rows_generated']}")
            print()
        
        # UI Automation Tests
        print("🎭 UI AUTOMATION TESTS")
        print("-"*100)
        for test in self.results["ui_automation_tests"]:
            status_icon = "✅" if test["result"]["status"] == "PASSED" else "❌"
            print(f"{status_icon} {test['test_name']}")
            print(f"   Status: {test['result']['status']}")
            print(f"   Details: {test['result']['details']}")
            if test['result'].get('test_case_id'):
                print(f"   Test Case ID: {test['result']['test_case_id']}")
            if test['result'].get('execution_time'):
                print(f"   Execution Time: {test['result']['execution_time']}s")
            print()
        
        # Summary
        print("="*100)
        print("📈 SUMMARY")
        print("="*100)
        summary = self.results["summary"]
        
        print(f"\n🧬 Synthetic Data Generator:")
        print(f"   Total Tests: {summary['synthetic_data']['total']}")
        print(f"   Passed: {summary['synthetic_data']['passed']}")
        print(f"   Failed: {summary['synthetic_data']['failed']}")
        print(f"   Success Rate: {summary['synthetic_data']['success_rate']}")
        
        print(f"\n🎭 UI Automation:")
        print(f"   Total Tests: {summary['ui_automation']['total']}")
        print(f"   Passed: {summary['ui_automation']['passed']}")
        print(f"   Failed: {summary['ui_automation']['failed']}")
        print(f"   Success Rate: {summary['ui_automation']['success_rate']}")
        
        print(f"\n🎯 Overall:")
        print(f"   Total Tests: {summary['overall']['total']}")
        print(f"   Passed: {summary['overall']['passed']}")
        print(f"   Failed: {summary['overall']['failed']}")
        print(f"   Success Rate: {summary['overall']['success_rate']}")
        
        print("\n" + "="*100)
        
        # Save to file
        with open("test_report.json", "w") as f:
            json.dump(self.results, f, indent=2)
        print("📁 Detailed report saved to: test_report.json")
        print("="*100)


def test_synthetic_data_ui_schema(report):
    """Test Synthetic Data Generator with UI Schema"""
    test_name = "Generate Data from UI Form Schema"
    print(f"\n🧪 Testing: {test_name}")
    
    html_form = """
    <form>
        <input type="text" name="username" placeholder="Username" required />
        <input type="email" name="email" placeholder="Email" required />
        <input type="password" name="password" required />
        <input type="tel" name="phone" placeholder="Phone Number" />
        <input type="date" name="dob" />
        <select name="country">
            <option>USA</option>
            <option>India</option>
            <option>UK</option>
        </select>
    </form>
    """
    
    try:
        # Extract UI schema
        print("   📋 Step 1: Extracting UI schema...")
        schema_resp = requests.post(f"{BACKEND_URL}/synthetic/ui-schema", 
                                    json={"html_content": html_form}, 
                                    timeout=30)
        
        if schema_resp.status_code != 200:
            report.add_synthetic_test(test_name, {
                "status": "FAILED",
                "details": f"Schema extraction failed: {schema_resp.text}"
            })
            return
        
        schema_data = schema_resp.json()
        schema_id = schema_data.get('schema_id')
        print(f"   ✅ Schema extracted! ID: {schema_id}")
        
        # Generate data
        print("   🔨 Step 2: Generating synthetic data...")
        generate_resp = requests.post(f"{BACKEND_URL}/synthetic/generate",
                                     json={"schema_id": schema_id, "num_rows": 10},
                                     timeout=60)
        
        if generate_resp.status_code != 200:
            report.add_synthetic_test(test_name, {
                "status": "FAILED",
                "details": f"Data generation failed: {generate_resp.text}"
            })
            return
        
        generate_data = generate_resp.json()
        rows = generate_data.get('count', 0)
        
        if rows > 0:
            print(f"   ✅ Generated {rows} rows of data!")
            report.add_synthetic_test(test_name, {
                "status": "PASSED",
                "details": "Successfully extracted schema and generated synthetic data",
                "schema_id": schema_id,
                "rows_generated": rows
            })
        else:
            report.add_synthetic_test(test_name, {
                "status": "FAILED",
                "details": "No data generated"
            })
    
    except Exception as e:
        report.add_synthetic_test(test_name, {
            "status": "FAILED",
            "details": f"Exception: {str(e)}"
        })


def test_synthetic_data_api_schema(report):
    """Test Synthetic Data Generator with API Schema"""
    test_name = "Generate Data from API Schema"
    print(f"\n🧪 Testing: {test_name}")
    
    api_spec = {
        "openapi": "3.0.0",
        "info": {"title": "User API", "version": "1.0.0"},
        "paths": {
            "/users": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "email": {"type": "string", "format": "email"},
                                        "age": {"type": "integer"},
                                        "active": {"type": "boolean"}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    try:
        # Extract API schema
        print("   📋 Step 1: Extracting API schema...")
        schema_resp = requests.post(f"{BACKEND_URL}/synthetic/api-schema",
                                    json={
                                        "openapi_spec": api_spec,
                                        "endpoint": "/users"
                                    },
                                    timeout=30)
        
        if schema_resp.status_code != 200:
            report.add_synthetic_test(test_name, {
                "status": "FAILED",
                "details": f"Schema extraction failed: {schema_resp.text}"
            })
            return
        
        schema_data = schema_resp.json()
        schema_id = schema_data.get('schema_id')
        print(f"   ✅ Schema extracted! ID: {schema_id}")
        
        # Generate data
        print("   🔨 Step 2: Generating synthetic data...")
        generate_resp = requests.post(f"{BACKEND_URL}/synthetic/generate",
                                     json={"schema_id": schema_id, "num_rows": 10},
                                     timeout=60)
        
        if generate_resp.status_code != 200:
            report.add_synthetic_test(test_name, {
                "status": "FAILED",
                "details": f"Data generation failed: {generate_resp.text}"
            })
            return
        
        generate_data = generate_resp.json()
        rows = generate_data.get('count', 0)
        
        if rows > 0:
            print(f"   ✅ Generated {rows} rows of data!")
            report.add_synthetic_test(test_name, {
                "status": "PASSED",
                "details": "Successfully extracted API schema and generated synthetic data",
                "schema_id": schema_id,
                "rows_generated": rows
            })
        else:
            report.add_synthetic_test(test_name, {
                "status": "FAILED",
                "details": "No data generated"
            })
    
    except Exception as e:
        report.add_synthetic_test(test_name, {
            "status": "FAILED",
            "details": f"Exception: {str(e)}"
        })


def test_ui_automation(test_name, description, page_url, report):
    """Test UI Automation end-to-end"""
    print(f"\n🧪 Testing: {test_name}")
    
    start_time = time.time()
    
    try:
        # Step 1: Plan
        print("   📋 Step 1: Creating test plan...")
        plan_resp = requests.post(f"{BACKEND_URL}/ui/plan",
                                 json={"raw_input": f"URL: {page_url}\n\nTest: {description}"},
                                 timeout=60)
        
        if plan_resp.status_code != 200:
            report.add_ui_test(test_name, {
                "status": "FAILED",
                "details": f"Planning failed: {plan_resp.text[:200]}"
            })
            return
        
        plan_data = plan_resp.json()
        test_case_id = plan_data.get('test_case_id')
        print(f"   ✅ Test plan created! ID: {test_case_id}")
        
        # Step 2: Generate
        print("   🔨 Step 2: Generating Playwright script...")
        gen_resp = requests.post(f"{BACKEND_URL}/ui/generate",
                                json={"test_case_id": test_case_id},
                                timeout=60)
        
        if gen_resp.status_code != 200:
            report.add_ui_test(test_name, {
                "status": "FAILED",
                "details": f"Script generation failed: {gen_resp.text[:200]}",
                "test_case_id": test_case_id
            })
            return
        
        gen_data = gen_resp.json()
        print(f"   ✅ Script generated!")
        
        # Step 3: Execute
        print("   🚀 Step 3: Executing test...")
        exec_resp = requests.post(f"{BACKEND_URL}/ui/execute",
                                 json={"test_case_id": test_case_id},
                                 timeout=120)
        
        if exec_resp.status_code != 200:
            report.add_ui_test(test_name, {
                "status": "FAILED",
                "details": f"Execution failed: {exec_resp.text[:200]}",
                "test_case_id": test_case_id
            })
            return
        
        exec_data = exec_resp.json()
        execution_time = time.time() - start_time
        
        if exec_data.get('success'):
            print(f"   ✅ Test execution completed!")
            report.add_ui_test(test_name, {
                "status": "PASSED",
                "details": f"Test completed successfully. Status: {exec_data.get('status')}",
                "test_case_id": test_case_id,
                "run_id": exec_data.get('run_id'),
                "execution_time": round(execution_time, 2)
            })
        else:
            report.add_ui_test(test_name, {
                "status": "FAILED",
                "details": f"Execution completed but failed: {exec_data.get('status')}",
                "test_case_id": test_case_id,
                "execution_time": round(execution_time, 2)
            })
    
    except Exception as e:
        report.add_ui_test(test_name, {
            "status": "FAILED",
            "details": f"Exception: {str(e)}"
        })


def main():
    """Run all end-to-end tests"""
    
    # Check backend health
    try:
        health = requests.get(f"{BACKEND_URL}/health", timeout=5)
        if health.status_code != 200:
            print("❌ Backend is not healthy. Please ensure it's running on http://localhost:8000")
            return
    except Exception as e:
        print(f"❌ Cannot connect to backend: {e}")
        print("Please start backend: cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000")
        return
    
    print("✅ Backend is healthy and ready")
    print("\n" + "="*100)
    print("🚀 STARTING END-TO-END TESTS")
    print("="*100)
    
    report = TestReport()
    
    # =========================================
    # SYNTHETIC DATA GENERATOR TESTS
    # =========================================
    print("\n" + "="*100)
    print("🧬 TESTING SYNTHETIC DATA GENERATOR")
    print("="*100)
    
    test_synthetic_data_ui_schema(report)
    test_synthetic_data_api_schema(report)
    
    # =========================================
    # UI AUTOMATION TESTS
    # =========================================
    print("\n" + "="*100)
    print("🎭 TESTING UI AUTOMATION")
    print("="*100)
    
    # Test 1: LG Website
    test_ui_automation(
        test_name="LG TV Purchase Flow",
        description="""Navigate to https://www.lg.com/in
Click on search option and search for 'lg 108cm tv'
Click on Buy Now for any product under 30000
Fill the pincode as 500032
Click on check
Click on checkout
Click on continue with condition 'complete purchase as guest'
Fill billing/shipping details""",
        page_url="https://www.lg.com/in",
        report=report
    )
    
    # Test 2: Sauce Demo
    test_ui_automation(
        test_name="Sauce Demo Shopping Cart",
        description="""Open https://sauce-demo.myshopify.com/
Click on grey shirt
Click on add to cart (don't click on mycart)
Click on checkout
Click on checkout again
Click on sign and continue as guest
In checkout page fill all the required fields
Click on paynow""",
        page_url="https://sauce-demo.myshopify.com/",
        report=report
    )
    
    # Test 3: Hilti
    test_ui_automation(
        test_name="Hilti Power Tools Purchase",
        description="""Open https://www.hilti.in/
Navigate to power tools
Navigate to rotary hammers
Click on any item
Add to cart
Checkout""",
        page_url="https://www.hilti.in/",
        report=report
    )
    
    # Generate and print report
    report.generate_report()
    report.print_report()


if __name__ == "__main__":
    main()
