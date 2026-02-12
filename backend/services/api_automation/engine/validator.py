"""
API Response Validator
Validates API responses against expected schema
"""
from typing import Dict, Any, List

class APIValidator:
    def validate(self, response: Any, expected_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate API response against expected schema"""
        issues = []
        warnings = []
        
        if not expected_schema:
            return {
                "status": "skipped",
                "message": "No expected schema provided",
                "issues": [],
                "warnings": []
            }
        
        # Validate response structure
        if not isinstance(response, dict):
            issues.append(f"Expected dict response, got {type(response).__name__}")
            return {
                "status": "failed",
                "issues": issues,
                "warnings": warnings
            }
        
        # Check each expected field
        for field_name, field_spec in expected_schema.items():
            if field_name not in response:
                issues.append(f"Missing expected field: {field_name}")
                continue
            
            # Validate type
            expected_type = field_spec.get('type')
            actual_value = response[field_name]
            
            if expected_type and not self._check_type(actual_value, expected_type):
                issues.append(f"Field '{field_name}': expected type {expected_type}, got {type(actual_value).__name__}")
            
            # Validate value if specified
            expected_value = field_spec.get('expected_value')
            if expected_value is not None and actual_value != expected_value:
                warnings.append(f"Field '{field_name}': expected value '{expected_value}', got '{actual_value}'")
        
        # Check for unexpected fields
        for field_name in response:
            if field_name not in expected_schema:
                warnings.append(f"Unexpected field in response: {field_name}")
        
        status = "success" if len(issues) == 0 else "failed"
        
        return {
            "status": status,
            "issues": issues,
            "warnings": warnings,
            "validated_fields": len(expected_schema),
            "response_fields": len(response)
        }
    
    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check if value matches expected type"""
        type_map = {
            'string': str,
            'str': str,
            'integer': int,
            'int': int,
            'float': float,
            'number': (int, float),
            'boolean': bool,
            'bool': bool,
            'list': list,
            'array': list,
            'dict': dict,
            'object': dict
        }
        
        expected_python_type = type_map.get(expected_type.lower(), str)
        return isinstance(value, expected_python_type)
    
    def validate_status_code(self, actual_status: int, expected_status: int) -> Dict[str, Any]:
        """Validate status code"""
        if actual_status == expected_status:
            return {
                "status": "success",
                "message": f"Status code matches: {actual_status}"
            }
        else:
            return {
                "status": "failed",
                "message": f"Expected status {expected_status}, got {actual_status}"
            }
    
    def validate_json_schema(self, response: Dict[str, Any], json_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Validate against JSON Schema (requires jsonschema library)"""
        try:
            from jsonschema import validate, ValidationError
            
            try:
                validate(instance=response, schema=json_schema)
                return {
                    "status": "success",
                    "message": "Response matches JSON schema"
                }
            except ValidationError as e:
                return {
                    "status": "failed",
                    "message": f"Schema validation failed: {e.message}",
                    "path": list(e.path)
                }
        
        except ImportError:
            return {
                "status": "skipped",
                "message": "jsonschema library not installed"
            }
