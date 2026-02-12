"""
API Test Planner Agent
Converts raw test case into structured API test plan
"""
from typing import Dict, Any
import json
import re

class APIPlannerAgent:
    def __init__(self):
        self.http_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
    
    def plan(self, raw_input: str) -> Dict[str, Any]:
        """Convert raw API test case to structured plan"""
        lines = [line.strip() for line in raw_input.split('\n') if line.strip()]
        
        test_name = "Generated API Test"
        method = "GET"
        endpoint = ""
        headers = {}
        payload_fields = []
        expected_status = 200
        expected_schema = {}
        
        for i, line in enumerate(lines):
            # Extract test name from first line
            if i == 0 and not any(m in line.upper() for m in self.http_methods):
                test_name = line
                continue
            
            # Extract HTTP method and endpoint
            method_match = self._extract_method(line)
            if method_match:
                method = method_match
            
            endpoint_match = self._extract_endpoint(line)
            if endpoint_match:
                endpoint = endpoint_match
            
            # Extract headers
            if 'header' in line.lower() or 'authorization' in line.lower():
                header_key, header_value = self._extract_header(line)
                if header_key:
                    headers[header_key] = header_value
            
            # Extract payload fields
            if 'payload' in line.lower() or 'body' in line.lower() or 'data' in line.lower():
                fields = self._extract_payload_fields(line)
                payload_fields.extend(fields)
            
            # Extract expected response
            if 'expect' in line.lower() or 'status' in line.lower() or 'response' in line.lower():
                status = self._extract_status_code(line)
                if status:
                    expected_status = status
                
                schema_fields = self._extract_response_schema(line)
                if schema_fields:
                    expected_schema = schema_fields
        
        return {
            "test_name": test_name,
            "method": method,
            "endpoint": endpoint or "https://api.example.com/endpoint",
            "headers": headers,
            "payload_fields": payload_fields,
            "expected_status": expected_status,
            "expected_schema": expected_schema
        }
    
    def _extract_method(self, line: str) -> str:
        """Extract HTTP method from line"""
        line_upper = line.upper()
        for method in self.http_methods:
            if method in line_upper:
                return method
        return None
    
    def _extract_endpoint(self, line: str) -> str:
        """Extract API endpoint from line"""
        # Look for URLs
        url_match = re.search(r'https?://[^\s]+', line)
        if url_match:
            return url_match.group(0)
        
        # Look for path patterns
        path_match = re.search(r'/[a-zA-Z0-9/_\-]+', line)
        if path_match:
            return path_match.group(0)
        
        return None
    
    def _extract_header(self, line: str) -> tuple:
        """Extract header key-value pair"""
        # Look for pattern: "key: value" or "key = value"
        match = re.search(r'(\w+[-\w]*)\s*[:=]\s*["\']?([^"\']+)["\']?', line)
        if match:
            return match.group(1), match.group(2).strip()
        
        return None, None
    
    def _extract_payload_fields(self, line: str) -> list:
        """Extract payload field definitions"""
        fields = []
        
        # Look for JSON-like structure
        json_match = re.search(r'\{[^}]+\}', line)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                for key, value in data.items():
                    fields.append({
                        "name": key,
                        "type": type(value).__name__,
                        "sample_value": value
                    })
            except:
                pass
        
        # Look for field definitions
        field_matches = re.findall(r'(\w+)\s*[:=]\s*["\']?([^",\']+)["\']?', line)
        for field_name, value in field_matches:
            fields.append({
                "name": field_name,
                "type": self._infer_type(value),
                "sample_value": value
            })
        
        return fields
    
    def _extract_status_code(self, line: str) -> int:
        """Extract expected status code"""
        # Look for 3-digit numbers
        match = re.search(r'\b(2\d{2}|3\d{2}|4\d{2}|5\d{2})\b', line)
        if match:
            return int(match.group(1))
        
        return None
    
    def _extract_response_schema(self, line: str) -> dict:
        """Extract expected response schema"""
        schema = {}
        
        # Look for JSON structure
        json_match = re.search(r'\{[^}]+\}', line)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                for key, value in data.items():
                    schema[key] = {
                        "type": type(value).__name__,
                        "expected_value": value
                    }
            except:
                pass
        
        return schema
    
    def _infer_type(self, value: str) -> str:
        """Infer field type from value"""
        if value.lower() in ['true', 'false']:
            return 'boolean'
        try:
            int(value)
            return 'integer'
        except:
            pass
        try:
            float(value)
            return 'float'
        except:
            pass
        return 'string'
