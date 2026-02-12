"""
UI Schema Extractor
Extracts field schema from UI elements
"""
from bs4 import BeautifulSoup
import requests
from typing import Dict, Any, List
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

class UISchemaExtractor:
    def __init__(self):
        self.field_type_mapping = {
            "text": "string",
            "email": "string",
            "number": "integer",
            "tel": "string",
            "date": "datetime",
            "checkbox": "boolean",
            "radio": "categorical",
            "select": "categorical"
        }
    
    def extract_from_html(self, html_content: str) -> Dict[str, Any]:
        """Extract schema from raw HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        fields = []
        
        # Find all input, select, textarea elements
        for element in soup.find_all(['input', 'select', 'textarea']):
            field_info = self._extract_field_info(element)
            if field_info:
                fields.append(field_info)
        
        return {
            "source": "ui",
            "fields": fields,
            "total_fields": len(fields)
        }
    
    def extract_from_url(self, url: str) -> Dict[str, Any]:
        """Extract schema by fetching URL using Playwright (HEADED mode)"""
        logger.info(f"🌐 UI Schema Extraction: Crawling URL with Playwright (HEADED mode)...")
        logger.info(f"📍 Target URL: {url}")
        
        try:
            # Temp dir under backend so path is correct regardless of process cwd
            backend_root = Path(__file__).resolve().parent.parent.parent.parent
            temp_dir = backend_root / "temp_crawl"
            temp_dir.mkdir(exist_ok=True)
            script_file = temp_dir / "crawl_script.js"
            output_file = temp_dir / "page_content.html"
            
            # Create Playwright script that saves HTML to file
            script_content = f"""
const {{ chromium }} = require('playwright');
const fs = require('fs');

(async () => {{
    const browser = await chromium.launch({{ 
        headless: false,
        slowMo: 500
    }});
    const context = await browser.newContext();
    const page = await context.newPage();
    
    console.log('🌐 Navigating to {url}...');
    await page.goto('{url}', {{ waitUntil: 'networkidle', timeout: 30000 }});
    
    console.log('⏳ Waiting for page to fully render...');
    await page.waitForTimeout(2000);
    
    console.log('📄 Extracting HTML content...');
    const html = await page.content();
    
    console.log('Saving HTML to file...');
    fs.writeFileSync('page_content.html', html, 'utf-8');
    
    console.log('✅ HTML extracted and saved successfully');
    console.log('📊 Content length: ' + html.length + ' characters');
    
    await browser.close();
}})();
"""
            
            logger.info("📝 Writing Playwright crawl script...")
            with open(script_file, 'w', encoding='utf-8') as f:
                f.write(script_content)
            
            logger.info("🎭 Launching Playwright browser (HEADED mode)...")
            logger.info("👀 Browser window will open - you can watch the crawling!")
            
            # Execute Playwright script (use script name only so cwd is correct; avoid temp_crawl/temp_crawl)
            result = subprocess.run(
                ["node", "crawl_script.js"],
                capture_output=True,
                text=True,
                timeout=45,
                encoding="utf-8",
                cwd=str(temp_dir.absolute()),
            )
            
            logger.info(f"📋 Playwright output: {result.stdout}")
            
            if result.returncode != 0:
                logger.error(f"❌ Playwright execution failed: {result.stderr}")
                logger.info("⚠️ Falling back to requests library...")
                # Fallback to requests
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                html_content = response.text
            elif output_file.exists():
                # Read HTML from saved file
                logger.info(f"✅ Reading HTML from saved file: {output_file}")
                with open(output_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                logger.info(f"📊 HTML content length: {len(html_content)} characters")
            else:
                logger.error("❌ Output file not found, falling back to requests")
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                html_content = response.text
            
            # Clean up temp files
            try:
                if script_file.exists():
                    script_file.unlink()
                if output_file.exists():
                    output_file.unlink()
            except Exception as cleanup_error:
                logger.warning(f"⚠️ Cleanup warning: {cleanup_error}")
            
            return self.extract_from_html(html_content)
            
        except subprocess.TimeoutExpired:
            logger.error("❌ Playwright timeout - falling back to requests")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return self.extract_from_html(response.text)
        except Exception as e:
            logger.error(f"❌ Error during URL extraction: {str(e)}")
            logger.info("⚠️ Attempting fallback to requests library...")
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                return self.extract_from_html(response.text)
            except Exception as fallback_error:
                raise Exception(f"Failed to fetch URL: {str(e)} | Fallback also failed: {str(fallback_error)}")
    
    def extract_from_structure(self, fields_structure: Dict[str, Any]) -> Dict[str, Any]:
        """Extract schema from provided structure"""
        fields = []
        
        for field_name, field_config in fields_structure.items():
            field_info = {
                "name": field_name,
                "type": field_config.get("type", "string"),
                "required": field_config.get("required", False),
                "constraints": field_config.get("constraints", {}),
                "label": field_config.get("label", field_name)
            }
            fields.append(field_info)
        
        return {
            "source": "ui_structure",
            "fields": fields,
            "total_fields": len(fields)
        }
    
    def _extract_field_info(self, element) -> Dict[str, Any]:
        """Extract information from a single field element"""
        field_name = element.get('name') or element.get('id')
        if not field_name:
            return None
        
        field_type = element.get('type', 'text') if element.name == 'input' else element.name
        
        field_info = {
            "name": field_name,
            "type": self.field_type_mapping.get(field_type, "string"),
            "required": element.has_attr('required'),
            "label": self._get_label(element),
            "constraints": self._get_constraints(element)
        }
        
        # Handle select options
        if element.name == 'select':
            options = [opt.get_text(strip=True) for opt in element.find_all('option') if opt.get_text(strip=True)]
            if options:
                field_info["constraints"]["categories"] = options
        
        return field_info
    
    def _get_label(self, element) -> str:
        """Try to find label for the field"""
        field_id = element.get('id')
        if field_id:
            label = element.find_previous('label', {'for': field_id})
            if label:
                return label.get_text(strip=True)
        
        placeholder = element.get('placeholder')
        if placeholder:
            return placeholder
        
        return element.get('name', 'Unknown')
    
    def _get_constraints(self, element) -> Dict[str, Any]:
        """Extract validation constraints"""
        constraints = {}
        
        if element.get('minlength'):
            constraints['min_length'] = int(element.get('minlength'))
        if element.get('maxlength'):
            constraints['max_length'] = int(element.get('maxlength'))
        if element.get('min'):
            constraints['min_value'] = float(element.get('min'))
        if element.get('max'):
            constraints['max_value'] = float(element.get('max'))
        if element.get('pattern'):
            constraints['pattern'] = element.get('pattern')
        
        return constraints
