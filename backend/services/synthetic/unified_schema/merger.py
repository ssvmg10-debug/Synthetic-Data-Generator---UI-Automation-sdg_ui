"""
Schema Merger
Combines UI and API schemas into unified schema
"""
from typing import Dict, Any, List, Optional

class SchemaMerger:
    def merge(self, ui_schema: Optional[Dict[str, Any]], api_schema: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge UI and API schemas into unified schema"""
        unified_fields = []
        field_map = {}
        
        # Process UI schema fields
        if ui_schema and 'fields' in ui_schema:
            for field in ui_schema['fields']:
                field_name = field['name']
                field_map[field_name] = {
                    "name": field_name,
                    "type": field.get('type'),
                    "required": field.get('required', False),
                    "ui_label": field.get('label'),
                    "constraints": field.get('constraints', {}),
                    "sources": ["ui"]
                }
        
        # Process API schema fields
        if api_schema and 'fields' in api_schema:
            for field in api_schema['fields']:
                field_name = field['name']
                
                if field_name in field_map:
                    # Merge with existing UI field
                    existing = field_map[field_name]
                    existing['sources'].append('api')
                    existing['api_description'] = field.get('description', '')
                    
                    # Merge constraints
                    api_constraints = field.get('constraints', {})
                    existing['constraints'].update(api_constraints)
                    
                    # Resolve type conflicts (API takes precedence for type)
                    if field.get('type') and field['type'] != existing['type']:
                        existing['type_conflict'] = {
                            'ui': existing['type'],
                            'api': field['type']
                        }
                        existing['type'] = field['type']  # API type wins
                else:
                    # New field from API
                    field_map[field_name] = {
                        "name": field_name,
                        "type": field.get('type'),
                        "required": field.get('required', False),
                        "api_description": field.get('description', ''),
                        "constraints": field.get('constraints', {}),
                        "sources": ["api"]
                    }
        
        unified_fields = list(field_map.values())
        
        return {
            "source": "unified",
            "fields": unified_fields,
            "total_fields": len(unified_fields),
            "ui_only_fields": len([f for f in unified_fields if f['sources'] == ['ui']]),
            "api_only_fields": len([f for f in unified_fields if f['sources'] == ['api']]),
            "common_fields": len([f for f in unified_fields if 'ui' in f['sources'] and 'api' in f['sources']])
        }
    
    def resolve_conflicts(self, unified_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve any conflicts in merged schema"""
        fields = unified_schema.get('fields', [])
        
        for field in fields:
            # If type conflict exists, prefer API type
            if 'type_conflict' in field:
                field['type'] = field['type_conflict']['api']
                field['resolved_type'] = True
        
        return unified_schema
