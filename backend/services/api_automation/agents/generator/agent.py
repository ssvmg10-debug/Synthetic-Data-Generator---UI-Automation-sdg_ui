"""
API Test Generator Agent
Generates API request payloads from structured plans
"""
from typing import Dict, Any, List, Optional
import json

class APIGeneratorAgent:
    def generate(self, structured_plan: Dict[str, Any], synthetic_data: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Generate API request from structured plan"""
        method = structured_plan.get('method', 'GET')
        endpoint = structured_plan.get('endpoint', 'https://api.example.com')
        headers = structured_plan.get('headers', {})
        payload_fields = structured_plan.get('payload_fields', [])
        
        # Build payload
        payload = {}
        if method in ['POST', 'PUT', 'PATCH'] and payload_fields:
            if synthetic_data and len(synthetic_data) > 0:
                # Use synthetic data
                payload = self._merge_with_synthetic_data(payload_fields, synthetic_data[0])
            else:
                # Use sample values from plan
                for field in payload_fields:
                    field_name = field.get('name')
                    sample_value = field.get('sample_value', '')
                    payload[field_name] = sample_value
        
        # Set default headers
        if 'Content-Type' not in headers and method in ['POST', 'PUT', 'PATCH']:
            headers['Content-Type'] = 'application/json'
        
        return {
            "method": method,
            "url": endpoint,
            "headers": headers,
            "payload": payload if payload else None
        }
    
    def _merge_with_synthetic_data(self, payload_fields: List[Dict[str, Any]], synthetic_row: Dict[str, Any]) -> Dict[str, Any]:
        """Merge payload fields with synthetic data"""
        payload = {}
        
        for field in payload_fields:
            field_name = field.get('name')
            
            # Try to find matching field in synthetic data
            if field_name in synthetic_row:
                payload[field_name] = synthetic_row[field_name]
            else:
                # Try case-insensitive match
                for key, value in synthetic_row.items():
                    if key.lower() == field_name.lower():
                        payload[field_name] = value
                        break
                else:
                    # Use sample value as fallback
                    payload[field_name] = field.get('sample_value', '')
        
        return payload
    
    def generate_curl_command(self, api_request: Dict[str, Any]) -> str:
        """Generate curl command for the API request"""
        method = api_request.get('method', 'GET')
        url = api_request.get('url', '')
        headers = api_request.get('headers', {})
        payload = api_request.get('payload')
        
        curl_cmd = f"curl -X {method}"
        
        # Add headers
        for key, value in headers.items():
            curl_cmd += f" -H '{key}: {value}'"
        
        # Add payload
        if payload:
            curl_cmd += f" -d '{json.dumps(payload)}'"
        
        curl_cmd += f" '{url}'"
        
        return curl_cmd
    
    def generate_python_requests(self, api_request: Dict[str, Any]) -> str:
        """Generate Python requests code"""
        method = api_request.get('method', 'GET').lower()
        url = api_request.get('url', '')
        headers = api_request.get('headers', {})
        payload = api_request.get('payload')
        
        code = "import requests\n\n"
        code += f"url = '{url}'\n"
        code += f"headers = {json.dumps(headers, indent=4)}\n"
        
        if payload:
            code += f"payload = {json.dumps(payload, indent=4)}\n"
            code += f"\nresponse = requests.{method}(url, headers=headers, json=payload)\n"
        else:
            code += f"\nresponse = requests.{method}(url, headers=headers)\n"
        
        code += "print(f'Status Code: {response.status_code}')\n"
        code += "print(f'Response: {response.json()}')\n"
        
        return code
