"""
UI Schema Extractor
Extracts field schema from UI elements.
Supports test-case-aware crawling (e.g. login then capture post-login page).
Uses Python Playwright (no Node.js required).
"""
from bs4 import BeautifulSoup
import json
import re
import requests
from typing import Dict, Any, List, Optional
import logging
import os
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def _credentials_from_test_case(test_case: str) -> Optional[Dict[str, str]]:
    """Extract username/password from test case text if present."""
    if not test_case:
        return None
    # Patterns: "user name: X", "username: X", "pass: X", "password: X"
    user_m = re.search(r"user\s*name:\s*([^\s,.\n]+)", test_case, re.I) or re.search(
        r"username:\s*([^\s,.\n]+)", test_case, re.I
    )
    pass_m = re.search(r"pass(?:word)?\s*:\s*([^\s,.\n]+)", test_case, re.I)
    if user_m and pass_m:
        return {"username": user_m.group(1).strip(), "password": pass_m.group(1).strip()}
    return None


def _crawl_with_python_playwright(
    url: str,
    output_dir: Path,
    output_file: Path,
    login_creds: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """
    Crawl URL with Python Playwright (sync), save HTML to output_file.
    Returns HTML content or None on failure (caller can fall back to requests).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.debug("playwright not available for crawl, will use requests fallback")
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(5000)
                # Cookie/consent
                for sel in [
                    "button:has-text('Accept')",
                    "button:has-text('Accept all')",
                    "button:has-text('I agree')",
                    "button:has-text('Agree')",
                ]:
                    try:
                        loc = page.locator(sel)
                        if loc.count() > 0:
                            loc.first.click(timeout=2000)
                            page.wait_for_timeout(1000)
                            break
                    except Exception:
                        continue
                if login_creds:
                    try:
                        user_sel = 'input[name*="user"], input[id*="user"], input[type="text"]'
                        pass_sel = 'input[name*="pass"], input[id*="pass"], input[type="password"]'
                        page.locator(user_sel).first.fill(login_creds["username"], timeout=3000)
                        page.locator(pass_sel).first.fill(login_creds["password"], timeout=3000)
                        page.wait_for_timeout(500)
                        page.locator('button[type="submit"], input[type="submit"]').first.click(timeout=3000)
                        page.wait_for_timeout(3000)
                    except Exception as e:
                        logger.debug("Login step skipped: %s", e)
                html = page.content()
            finally:
                browser.close()
        output_file.write_text(html, encoding="utf-8")
        logger.info("✅ HTML extracted with Python Playwright (%s chars)", len(html))
        return html
    except Exception as e:
        logger.warning("Python Playwright crawl failed: %s", e)
        return None

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
    
    def extract_from_url(
        self,
        url: str,
        test_case: Optional[str] = None,
        output_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Crawl URL with Playwright (test-case-aware: can perform login if test case mentions it).
        Persists HTML and schema under temp_crawl; returns schema + html for DB storage.
        """
        logger.info("🌐 UI Schema Extraction: Crawling URL with Playwright (test-case-aware)...")
        logger.info("📍 Target URL: %s", url)
        
        backend_root = Path(__file__).resolve().parent.parent.parent.parent
        temp_base = backend_root / "temp_crawl"
        temp_base.mkdir(exist_ok=True)
        crawls_dir = temp_base / "crawls"
        crawls_dir.mkdir(exist_ok=True)
        
        if output_dir is None:
            url_slug = re.sub(r"[^\w\-.]", "_", url.replace("https://", "").replace("http://", ""))[:80]
            stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_dir = crawls_dir / f"{stamp}_{url_slug}"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / "page_content.html"
        schema_file = output_dir / "schema.json"
        
        creds = _credentials_from_test_case(test_case or "")
        login_creds = creds if (creds and test_case and "login" in (test_case or "").lower()) else None
        
        def _save_and_return(html_content: str):
            schema = self.extract_from_html(html_content)
            output_file.write_text(html_content, encoding="utf-8")
            schema_file.write_text(json.dumps(schema, indent=2), encoding="utf-8")
            return {"schema": schema, "html": html_content, "output_dir": str(output_dir.absolute())}
        
        # 1) Try Python Playwright (no Node.js required)
        html = _crawl_with_python_playwright(url, output_dir, output_file, login_creds)
        if html:
            schema = self.extract_from_html(html)
            with open(schema_file, "w", encoding="utf-8") as f:
                json.dump(schema, f, indent=2)
            logger.info("💾 Saved schema to %s", schema_file)
            return {"schema": schema, "html": html, "output_dir": str(output_dir.absolute())}
        
        # 2) Fallback: requests
        try:
            logger.info("📡 Falling back to requests.get")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return _save_and_return(response.text)
        except Exception as e:
            raise Exception(f"URL crawl failed (Playwright and requests): {str(e)}")
    
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
