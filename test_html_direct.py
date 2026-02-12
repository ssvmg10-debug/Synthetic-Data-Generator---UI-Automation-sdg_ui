"""Test with HTML content directly"""
import requests

BASE_URL = "http://localhost:8000"

html = """
<form>
    <input type="text" name="username" placeholder="Username" required />
    <input type="password" name="password" placeholder="Password" required />
    <button type="submit">Login</button>
</form>
"""

print("Testing with direct HTML...")
response = requests.post(f"{BASE_URL}/synthetic/ui-schema", json={"html_content": html})
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
