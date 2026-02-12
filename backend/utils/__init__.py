"""Utility functions"""
import os
from datetime import datetime
from pathlib import Path

def create_output_directory(base_dir: str = "test_outputs") -> Path:
    """Create output directory if it doesn't exist"""
    output_dir = Path(base_dir)
    output_dir.mkdir(exist_ok=True)
    return output_dir

def generate_timestamp() -> str:
    """Generate timestamp string"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def save_logs(content: str, filename: str, directory: str = "logs") -> str:
    """Save logs to file"""
    log_dir = Path(directory)
    log_dir.mkdir(exist_ok=True)
    
    filepath = log_dir / filename
    with open(filepath, 'w') as f:
        f.write(content)
    
    return str(filepath)

def load_config(config_file: str = "config.json") -> dict:
    """Load configuration from file"""
    import json
    
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            return json.load(f)
    
    return {}

def sanitize_filename(filename: str) -> str:
    """Sanitize filename to remove invalid characters"""
    import re
    return re.sub(r'[<>:"/\\|?*]', '_', filename)
