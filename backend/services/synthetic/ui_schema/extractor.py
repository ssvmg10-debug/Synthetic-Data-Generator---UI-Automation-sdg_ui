"""
UI Schema Extractor
Extracts field schema from UI elements.
Supports test-case-aware crawling (e.g. login then capture post-login page).
"""
from bs4 import BeautifulSoup
import json
import re
import requests
from typing import Dict, Any, List, Optional
import logging
import os
import subprocess
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
        
        script_file = output_dir / "crawl_script.js"
        output_file = output_dir / "page_content.html"
        schema_file = output_dir / "schema.json"
        
        creds = _credentials_from_test_case(test_case or "")
        do_login = (
            creds
            and test_case
            and "login" in test_case.lower()
        )
        
        # Build Playwright script: goto URL, optionally login, then capture HTML
        login_block = ""
        if do_login:
            un = creds["username"].replace("\\", "\\\\").replace("'", "\\'")
            pw = creds["password"].replace("\\", "\\\\").replace("'", "\\'")
            login_block = f"""
    console.log('🔐 Test case mentions login - attempting login...');
    try {{
        const userSel = 'input[name*="user"], input[id*="user"], input[type="text"]';
        const passSel = 'input[name*="pass"], input[id*="pass"], input[type="password"]';
        const userEl = await page.$(userSel);
        const passEl = await page.$(passSel);
        if (userEl && passEl) {{
            await userEl.fill('{un}');
            await passEl.fill('{pw}');
            await page.waitForTimeout(500);
            const submit = await page.$('button[type="submit"], input[type="submit"], button:has-text("Login"), input[value="Login"]');
            if (submit) await submit.click();
            await page.waitForTimeout(3000);
            console.log('✅ Login step completed');
        }}
    }} catch (e) {{ console.log('Login step skipped:', e.message); }}
"""
        
        script_content = f"""
const {{ chromium }} = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {{
    const browser = await chromium.launch({{ headless: false, slowMo: 100 }});
    const context = await browser.newContext();
    const page = await context.newPage();
    
    console.log('🌐 Navigating to {url}...');
    await page.goto('{url}', {{ waitUntil: 'networkidle', timeout: 30000 }});
    
    console.log('⏳ Waiting for page to fully render...');
    await page.waitForTimeout(5000);

    // Try to accept common cookie / consent banners so forms are visible
    try {{
        const cookieSelectors = [
            "button:has-text('Accept')",
            "button:has-text('Accept all')",
            "button:has-text('I agree')",
            "button:has-text('Agree')",
            "text='Accept all cookies'"
        ];
        for (const sel of cookieSelectors) {{
            const btn = await page.$(sel);
            if (btn) {{
                console.log('✅ Clicking cookie/consent button:', sel);
                await btn.click().catch(() => {{}});
                await page.waitForTimeout(1000);
                break;
            }}
        }}
    }} catch (e) {{
        console.log('Cookie banner handling skipped:', e.message);
    }}
{login_block}
    console.log('📄 Extracting HTML content...');
    const html = await page.content();
    
    const outDir = process.env.OUTPUT_DIR || __dirname;
    fs.writeFileSync(path.join(outDir, 'page_content.html'), html, 'utf-8');
    console.log('✅ HTML extracted and saved successfully');
    console.log('📊 Content length: ' + html.length + ' characters');
    
    await browser.close();
}})();
"""
        
        try:
            logger.info("📝 Writing Playwright crawl script to %s", output_dir)
            with open(script_file, "w", encoding="utf-8") as f:
                f.write(script_content)
            env = os.environ.copy()
            env["OUTPUT_DIR"] = str(output_dir.absolute())
            script_rel = script_file.relative_to(backend_root).as_posix()
            result = subprocess.run(
                ["node", script_rel],
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                cwd=str(backend_root),
                env=env,
            )
            
            logger.info("📋 Playwright output: %s", result.stdout or result.stderr)
            
            if result.returncode != 0:
                logger.error("❌ Playwright execution failed: %s", result.stderr)
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                html_content = response.text
                schema = self.extract_from_html(html_content)
                output_file.write_text(html_content, encoding="utf-8")
                schema_file.write_text(json.dumps(schema, indent=2), encoding="utf-8")
                return {"schema": schema, "html": html_content, "output_dir": str(output_dir.absolute())}
            elif output_file.exists():
                with open(output_file, "r", encoding="utf-8") as f:
                    html_content = f.read()
                logger.info("✅ Read HTML from %s (%s chars)", output_file, len(html_content))
            else:
                logger.error("❌ Output file not found")
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                html_content = response.text
            
            schema = self.extract_from_html(html_content)
            # Persist schema to same folder
            with open(schema_file, "w", encoding="utf-8") as f:
                json.dump(schema, f, indent=2)
            logger.info("💾 Saved schema to %s", schema_file)
            # Do NOT delete output_dir / HTML / schema — keep for inspection
            
            return {
                "schema": schema,
                "html": html_content,
                "output_dir": str(output_dir.absolute()),
            }
            
        except subprocess.TimeoutExpired:
            logger.error("❌ Playwright timeout - falling back to requests")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            html_content = response.text
            schema = self.extract_from_html(html_content)
            output_file.write_text(html_content, encoding="utf-8")
            schema_file.write_text(json.dumps(schema, indent=2), encoding="utf-8")
            return {"schema": schema, "html": html_content, "output_dir": str(output_dir.absolute())}
        except Exception as e:
            logger.error("❌ Error during URL extraction: %s", e)
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                html_content = response.text
                schema = self.extract_from_html(html_content)
                output_file.write_text(html_content, encoding="utf-8")
                schema_file.write_text(json.dumps(schema, indent=2), encoding="utf-8")
                return {"schema": schema, "html": html_content, "output_dir": str(output_dir.absolute())}
            except Exception as fallback_error:
                raise Exception(f"Failed to fetch URL: {str(e)} | Fallback: {str(fallback_error)}")
    
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
