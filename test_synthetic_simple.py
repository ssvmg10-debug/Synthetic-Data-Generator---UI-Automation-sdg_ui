"""
Simple test to debug synthetic data generation
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_ui_schema():
    print("\n🧪 Testing UI Schema Extraction and Data Generation")
    print("=" * 60)
    
    # 1. Extract UI Schema
    html_content = """
    <form>
        <input type="text" name="firstName" placeholder="First Name" required>
        <input type="text" name="lastName" placeholder="Last Name" required>
        <input type="email" name="email" placeholder="Email" required>
        <input type="tel" name="phone" placeholder="Phone" required>
        <select name="country">
            <option>USA</option>
            <option>Canada</option>
            <option>UK</option>
        </select>
        <input type="submit">
    </form>
    """
    
    print("\n1. Extracting schema from HTML form...")
    response = requests.post(
        f"{BASE_URL}/synthetic/ui-schema",
        json={"html_content": html_content}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        schema_data = response.json()
        schema_id = schema_data.get('schema_id')
        schema = schema_data.get('schema')
        
        print(f"\n✅ Schema extracted! ID: {schema_id}")
        print(f"Schema fields: {len(schema.get('fields', []))}")
        print(f"Fields: {[f['name'] for f in schema.get('fields', [])]}")
        
        # 2. Generate synthetic data
        print("\n2. Generating synthetic data...")
        response = requests.post(
            f"{BASE_URL}/synthetic/generate",
            json={"schema_id": schema_id, "num_rows": 5}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            generated_data = data.get('data', [])
            print(f"\n✅ Generated {len(generated_data)} rows of data")
            if generated_data:
                print(f"Sample row: {json.dumps(generated_data[0], indent=2)}")
            else:
                print("⚠️ No data was generated!")
        else:
            print(f"❌ Data generation failed: {response.text}")
    else:
        print(f"❌ Schema extraction failed: {response.text}")

def test_api_schema():
    print("\n\n🧪 Testing API Schema Extraction and Data Generation")
    print("=" * 60)
    
    # OpenAPI spec sample
    api_spec = {
        "openapi": "3.0.0",
        "info": {"title": "Users API", "version": "1.0.0"},
        "paths": {
            "/users": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                            "username": {"type": "string"},
                                            "email": {"type": "string", "format": "email"},
                                            "age": {"type": "integer", "minimum": 18, "maximum": 100}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    print("\n1. Extracting schema from OpenAPI spec...")
    response = requests.post(
        f"{BASE_URL}/synthetic/api-schema",
        json={"openapi_spec": api_spec, "endpoint": "/users"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        schema_data = response.json()
        schema_id = schema_data.get('schema_id')
        schema = schema_data.get('schema')
        
        print(f"\n✅ Schema extracted! ID: {schema_id}")
        print(f"Schema fields: {len(schema.get('fields', []))}")
        print(f"Fields: {[f['name'] for f in schema.get('fields', [])]}")
        
        # 2. Generate synthetic data
        print("\n2. Generating synthetic data...")
        response = requests.post(
            f"{BASE_URL}/synthetic/generate",
            json={"schema_id": schema_id, "num_rows": 5}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            data = response.json()
            generated_data = data.get('data', [])
            print(f"\n✅ Generated {len(generated_data)} rows of data")
            if generated_data:
                print(f"Sample row: {json.dumps(generated_data[0], indent=2)}")
            else:
                print("⚠️ No data was generated!")
        else:
            print(f"❌ Data generation failed: {response.text}")
    else:
        print(f"❌ Schema extraction failed: {response.text}")

if __name__ == "__main__":
    # Check if backend is running
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"✅ Backend is healthy and ready\n")
    except:
        print(f"❌ Backend is not running on {BASE_URL}")
        exit(1)
    
    test_ui_schema()
    test_api_schema()
    
    print("\n" + "=" * 60)
    print("🏁 Testing complete!")
