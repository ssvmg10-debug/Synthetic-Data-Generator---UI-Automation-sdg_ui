"""
Valid Data Generator for Form Fields
Generates realistic, valid data for Indian e-commerce forms
"""
import random
import re


def generate_valid_data(field_label: str, provided_value: str = None) -> str:
    """
    Generate valid data based on field label.
    
    If provided_value is already valid, return it.
    Otherwise, generate appropriate valid data.
    
    Args:
        field_label: Field description (e.g., "email", "mobile", "first name")
        provided_value: Optional pre-provided value
    
    Returns:
        Valid data string for the field
    """
    if not provided_value or provided_value.lower() in ['none', 'null', '']:
        # No value provided, generate based on field type
        field_lower = field_label.lower()
        
        # Email detection
        if any(keyword in field_lower for keyword in ['email', 'e-mail', 'mail']):
            return generate_indian_email()
        
        # Mobile/Phone detection
        elif any(keyword in field_lower for keyword in ['mobile', 'phone', 'contact', 'tel']):
            return generate_indian_mobile()
        
        # First Name detection
        elif any(keyword in field_lower for keyword in ['first name', 'fname', 'firstname']):
            return generate_indian_first_name()
        
        # Last Name detection
        elif any(keyword in field_lower for keyword in ['last name', 'lname', 'lastname', 'surname']):
            return generate_indian_last_name()
        
        # Full Name detection
        elif 'name' in field_lower and 'user' not in field_lower:
            return f"{generate_indian_first_name()} {generate_indian_last_name()}"
        
        # Pincode detection
        elif any(keyword in field_lower for keyword in ['pincode', 'pin', 'postal', 'zip']):
            return "500032"  # Default valid Hyderabad pincode
        
        # Address detection
        elif any(keyword in field_lower for keyword in ['address', 'street', 'location']):
            return generate_indian_address()
        
        # State detection
        elif 'state' in field_lower:
            return "Telangana"
        
        # City detection
        elif 'city' in field_lower:
            return "Hyderabad"
        
        # Default: return the label itself as hint
        return field_label
    
    else:
        # Value provided, check if it needs validation/correction
        provided_lower = provided_value.lower()
        
        # Check if it's a placeholder that needs generation
        if any(word in provided_lower for word in ['billing', 'shipping', 'details', 'fill', 'enter']):
            field_lower = field_label.lower()
            
            if 'email' in field_lower or 'email' in provided_lower:
                return generate_indian_email()
            elif 'mobile' in field_lower or 'phone' in field_lower or 'mobile' in provided_lower:
                return generate_indian_mobile()
            elif 'name' in field_lower or 'name' in provided_lower:
                return f"{generate_indian_first_name()} {generate_indian_last_name()}"
            elif 'address' in field_lower or 'address' in provided_lower:
                return generate_indian_address()
        
        # Return provided value as-is if it looks valid
        return provided_value


def generate_indian_mobile() -> str:
    """
    Generate valid Indian mobile number (10 digits starting with 6, 7, 8, or 9).
    
    Returns:
        String like "9876543210"
    """
    first_digit = random.choice(['6', '7', '8', '9'])
    remaining_digits = ''.join([str(random.randint(0, 9)) for _ in range(9)])
    return first_digit + remaining_digits


def generate_indian_email() -> str:
    """
    Generate realistic Indian email address.
    
    Returns:
        String like "rajesh.kumar@gmail.com"
    """
    first_names = ['rajesh', 'priya', 'amit', 'sneha', 'vikram', 'anjali', 'arjun', 'kavya', 'rohan', 'neha']
    last_names = ['kumar', 'sharma', 'patel', 'singh', 'reddy', 'iyer', 'gupta', 'verma', 'nair', 'das']
    domains = ['gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com']
    
    first = random.choice(first_names)
    last = random.choice(last_names)
    domain = random.choice(domains)
    
    return f"{first}.{last}{random.randint(10, 99)}@{domain}"


def generate_indian_first_name() -> str:
    """
    Generate common Indian first name.
    
    Returns:
        String like "Rajesh" or "Priya"
    """
    male_names = ['Rajesh', 'Amit', 'Vikram', 'Arjun', 'Rohan', 'Karan', 'Aditya', 'Rahul', 'Sanjay', 'Deepak']
    female_names = ['Priya', 'Sneha', 'Anjali', 'Kavya', 'Neha', 'Pooja', 'Isha', 'Divya', 'Riya', 'Shreya']
    
    return random.choice(male_names + female_names)


def generate_indian_last_name() -> str:
    """
    Generate common Indian last name.
    
    Returns:
        String like "Kumar" or "Sharma"
    """
    last_names = ['Kumar', 'Sharma', 'Patel', 'Singh', 'Reddy', 'Iyer', 'Gupta', 'Verma', 'Nair', 'Das', 
                  'Rao', 'Mehta', 'Joshi', 'Agarwal', 'Desai']
    
    return random.choice(last_names)


def generate_indian_address() -> str:
    """
    Generate realistic Indian address.
    
    Returns:
        String like "123 MG Road, Jubilee Hills"
    """
    street_numbers = [str(random.randint(1, 999)) for _ in range(1)]
    street_names = ['MG Road', 'Brigade Road', 'Residency Road', 'Main Road', 'Cross Street', 
                    'Park Street', 'Station Road', 'Market Road', 'Temple Street', 'Gandhi Road']
    areas = ['Jubilee Hills', 'Banjara Hills', 'Koramangala', 'Indiranagar', 'Whitefield', 
             'HSR Layout', 'Jayanagar', 'Malleswaram', 'Anna Nagar', 'T Nagar']
    
    number = random.choice(street_numbers)
    street = random.choice(street_names)
    area = random.choice(areas)
    
    return f"{number} {street}, {area}"


def is_valid_indian_mobile(mobile: str) -> bool:
    """
    Check if mobile number is valid Indian format.
    
    Args:
        mobile: Mobile number string
    
    Returns:
        True if valid (10 digits starting with 6/7/8/9)
    """
    # Remove spaces, dashes, etc.
    cleaned = re.sub(r'[^\d]', '', mobile)
    
    # Check if 10 digits and starts with 6, 7, 8, or 9
    if len(cleaned) == 10 and cleaned[0] in ['6', '7', '8', '9']:
        return True
    
    return False
