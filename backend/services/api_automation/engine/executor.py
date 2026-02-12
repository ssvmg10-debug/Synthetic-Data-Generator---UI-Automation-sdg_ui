"""
API Executor
Executes API requests using httpx
"""
from typing import Dict, Any
import httpx
import json

class APIExecutor:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
    
    def execute(self, api_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute API request"""
        method = api_request.get('method', 'GET').upper()
        url = api_request.get('url', '')
        headers = api_request.get('headers', {})
        payload = api_request.get('payload')
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                if method == 'GET':
                    response = client.get(url, headers=headers)
                elif method == 'POST':
                    response = client.post(url, headers=headers, json=payload)
                elif method == 'PUT':
                    response = client.put(url, headers=headers, json=payload)
                elif method == 'PATCH':
                    response = client.patch(url, headers=headers, json=payload)
                elif method == 'DELETE':
                    response = client.delete(url, headers=headers)
                else:
                    return {
                        "success": False,
                        "error": f"Unsupported HTTP method: {method}"
                    }
                
                # Parse response
                try:
                    response_data = response.json()
                except:
                    response_data = response.text
                
                return {
                    "success": response.is_success,
                    "status_code": response.status_code,
                    "response": response_data,
                    "headers": dict(response.headers),
                    "elapsed_time": response.elapsed.total_seconds()
                }
        
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": f"Request timed out after {self.timeout} seconds"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": f"Request failed: {str(e)}"
            }
    
    def execute_batch(self, api_requests: list) -> list:
        """Execute multiple API requests"""
        results = []
        
        for req in api_requests:
            result = self.execute(req)
            results.append(result)
        
        return results
