"""
SDV Generator
Generates synthetic data using Synthetic Data Vault (SDV)
"""
from typing import Dict, Any, List
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import string

class SDVGenerator:
    """
    Simplified SDV-like generator
    For production, use actual SDV library: pip install sdv
    """
    
    def __init__(self):
        self.faker_available = False
        try:
            from faker import Faker
            self.faker = Faker()
            self.faker_available = True
        except ImportError:
            self.faker = None
    
    def generate(self, schema: Dict[str, Any], num_rows: int = 10, model: str = "GaussianCopula") -> List[Dict[str, Any]]:
        """Generate synthetic data based on schema"""
        fields = schema.get('fields', [])
        data = []
        
        for i in range(num_rows):
            row = {}
            for field in fields:
                field_name = field['name']
                field_type = field.get('type', 'string')
                constraints = field.get('constraints', {})
                
                # Generate value based on type
                row[field_name] = self._generate_value(field_name, field_type, constraints)
            
            data.append(row)
        
        return data
    
    def _generate_value(self, field_name: str, field_type: str, constraints: Dict[str, Any]) -> Any:
        """Generate a single value based on type and constraints"""
        
        # Check for categories/enum
        if 'categories' in constraints:
            return random.choice(constraints['categories'])
        
        # Generate based on type
        if field_type == 'boolean':
            return random.choice([True, False])
        
        elif field_type == 'integer':
            min_val = constraints.get('min_value', 1)
            max_val = constraints.get('max_value', 100)
            return random.randint(int(min_val), int(max_val))
        
        elif field_type == 'float':
            min_val = constraints.get('min_value', 0.0)
            max_val = constraints.get('max_value', 100.0)
            return round(random.uniform(min_val, max_val), 2)
        
        elif field_type == 'datetime':
            # Generate random date in last year
            days_ago = random.randint(0, 365)
            return (datetime.now() - timedelta(days=days_ago)).isoformat()
        
        elif field_type == 'categorical':
            if 'categories' in constraints:
                return random.choice(constraints['categories'])
            return f"Category_{random.randint(1, 5)}"
        
        elif field_type == 'string':
            return self._generate_string(field_name, constraints)
        
        else:
            return self._generate_string(field_name, constraints)
    
    def _generate_string(self, field_name: str, constraints: Dict[str, Any]) -> str:
        """Generate string value based on field name and constraints"""
        field_lower = field_name.lower()
        
        # Use Faker if available and field name suggests specific type
        if self.faker_available:
            if 'email' in field_lower:
                return self.faker.email()
            elif 'name' in field_lower and 'user' in field_lower:
                return self.faker.user_name()
            elif 'first' in field_lower and 'name' in field_lower:
                return self.faker.first_name()
            elif 'last' in field_lower and 'name' in field_lower:
                return self.faker.last_name()
            elif 'name' in field_lower:
                return self.faker.name()
            elif 'phone' in field_lower or 'tel' in field_lower:
                return self.faker.phone_number()
            elif 'address' in field_lower:
                return self.faker.address()
            elif 'city' in field_lower:
                return self.faker.city()
            elif 'state' in field_lower:
                return self.faker.state()
            elif 'zip' in field_lower or 'postal' in field_lower:
                return self.faker.zipcode()
            elif 'country' in field_lower:
                return self.faker.country()
            elif 'company' in field_lower:
                return self.faker.company()
            elif 'url' in field_lower or 'website' in field_lower:
                return self.faker.url()
        
        # Fallback: generate random string
        min_length = constraints.get('min_length', 5)
        max_length = constraints.get('max_length', 20)
        length = random.randint(min_length, min(max_length, 50))
        
        # Check pattern constraint
        if 'pattern' in constraints:
            # Simplified pattern handling
            pattern = constraints['pattern']
            if pattern == '[0-9]+':
                return ''.join(random.choices(string.digits, k=length))
            elif pattern == '[a-zA-Z]+':
                return ''.join(random.choices(string.ascii_letters, k=length))
        
        # Default: alphanumeric
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    def generate_with_relationships(self, schemas: List[Dict[str, Any]], num_rows: int = 10) -> Dict[str, List[Dict[str, Any]]]:
        """Generate data for multiple related schemas (for advanced use cases)"""
        result = {}
        
        for schema in schemas:
            schema_name = schema.get('name', 'unnamed')
            result[schema_name] = self.generate(schema, num_rows)
        
        return result
