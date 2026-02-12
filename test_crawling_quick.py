"""
Quick test for UI crawling with headed browser
"""
import requests
import json

BASE_URL = "http://localhost:8000"

print("\n🌐 Testing UI Schema Extraction with Headed Browser Crawling")
print("=" * 70)

# Test with a simple URL that has a form
test_url = "https://www.google.com"

print(f"\n📍 Target: {test_url}")
print(f"🎭 Watch for browser window to open...")
print(f"👀 Check backend console for detailed logs...")
print(f"⏳ This may take 10-15 seconds...")
print()

try:
    response = requests.post(
        f"{BASE_URL}/synthetic/ui-schema",
        json={"url": test_url},
        timeout=45
    )
    
    if response.status_code == 200:
        data = response.json()
        schema = data.get('schema', {})
        fields = schema.get('fields', [])
        
        print(f"✅ SUCCESS!")
        print(f"   Schema ID: {data.get('schema_id')}")
        print(f"   Fields Found: {len(fields)}")
        
        if fields:
            print(f"\n   📋 Extracted Fields:")
            for field in fields[:10]:
                print(f"      • {field['name']} ({field['type']}) - Required: {field['required']}")
        else:
            print(f"\n   ⚠️ No form fields found on the page")
    else:
        print(f"❌ FAILED: {response.status_code}")
        print(f"   {response.text}")

except Exception as e:
    print(f"❌ ERROR: {str(e)}")

print("\n" + "=" * 70)
