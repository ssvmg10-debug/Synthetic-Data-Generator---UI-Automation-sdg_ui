"""
API Schema Extractor
Extracts field schema from API specifications or responses
"""
from typing import Dict, Any, List
import json

class APISchemaExtractor:
    def __init__(self):
        self.type_mapping = {
            "string": "string",
            "integer": "integer",
            "number": "float",
            "boolean": "boolean",
            "array": "array",
            "object": "object"
        }
    
    def extract_from_openapi(self, openapi_spec: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
        """Extract schema from OpenAPI specification"""
        fields = []
        
        # Navigate OpenAPI structure to find request/response schema
        paths = openapi_spec.get('paths', {})
        endpoint_data = paths.get(endpoint, {})
        
        # Try to get request body schema first
        for method in ['post', 'put', 'patch']:
            if method in endpoint_data:
                request_body = endpoint_data[method].get('requestBody', {})
                content = request_body.get('content', {})
                json_content = content.get('application/json', {})
                schema = json_content.get('schema', {})
                
                if schema:
                    fields = self._parse_openapi_schema(schema, openapi_spec.get('components', {}))
                    break
        
        # If no request body, try response schema
        if not fields:
            for method in ['get', 'post', 'put', 'patch', 'delete']:
                if method in endpoint_data:
                    responses = endpoint_data[method].get('responses', {})
                    # Try 200, 201, or first available response
                    for status_code in ['200', '201', '202']:
                        if status_code in responses:
                            content = responses[status_code].get('content', {})
                            json_content = content.get('application/json', {})
                            schema = json_content.get('schema', {})
                            
                            if schema:
                                fields = self._parse_openapi_schema(schema, openapi_spec.get('components', {}))
                                break
                    
                    if fields:
                        break
        
        return {
            "source": "api_openapi",
            "endpoint": endpoint,
            "fields": fields,
            "total_fields": len(fields)
        }
    
    def extract_from_response(self, sample_response: Dict[str, Any]) -> Dict[str, Any]:
        """Extract schema from sample API response"""
        fields = self._infer_schema(sample_response)
        
        return {
            "source": "api_response",
            "fields": fields,
            "total_fields": len(fields)
        }
    
    def _parse_openapi_schema(self, schema: Dict[str, Any], components: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse OpenAPI schema definition"""
        fields = []
        
        # Handle $ref
        if '$ref' in schema:
            ref_path = schema['$ref'].split('/')
            if ref_path[0] == '#' and ref_path[1] == 'components' and ref_path[2] == 'schemas':
                schema_name = ref_path[3]
                schema = components.get('schemas', {}).get(schema_name, {})
        
        # Parse properties
        properties = schema.get('properties', {})
        required_fields = schema.get('required', [])
        
        for field_name, field_schema in properties.items():
            field_info = {
                "name": field_name,
                "type": self.type_mapping.get(field_schema.get('type', 'string'), 'string'),
                "required": field_name in required_fields,
                "description": field_schema.get('description', ''),
                "constraints": {}
            }
            
            # Add constraints
            if 'minLength' in field_schema:
                field_info['constraints']['min_length'] = field_schema['minLength']
            if 'maxLength' in field_schema:
                field_info['constraints']['max_length'] = field_schema['maxLength']
            if 'minimum' in field_schema:
                field_info['constraints']['min_value'] = field_schema['minimum']
            if 'maximum' in field_schema:
                field_info['constraints']['max_value'] = field_schema['maximum']
            if 'enum' in field_schema:
                field_info['constraints']['categories'] = field_schema['enum']
            if 'pattern' in field_schema:
                field_info['constraints']['pattern'] = field_schema['pattern']
            
            fields.append(field_info)
        
        return fields
    
    def _infer_schema(self, data: Any, parent_key: str = '') -> List[Dict[str, Any]]:
        """Infer schema from data structure"""
        fields = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                field_name = f"{parent_key}.{key}" if parent_key else key
                field_type = self._infer_type(value)
                
                field_info = {
                    "name": field_name,
                    "type": field_type,
                    "required": False,  # Can't determine from sample
                    "constraints": {}
                }
                
                # Add sample value for reference
                if not isinstance(value, (dict, list)):
                    field_info["sample_value"] = value
                
                fields.append(field_info)
                
                # Recursively handle nested objects
                if isinstance(value, dict):
                    nested_fields = self._infer_schema(value, field_name)
                    fields.extend(nested_fields)
        
        return fields
    
    def _infer_type(self, value: Any) -> str:
        """Infer field type from value"""
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "float"
        elif isinstance(value, str):
            return "string"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        else:
            return "string"
