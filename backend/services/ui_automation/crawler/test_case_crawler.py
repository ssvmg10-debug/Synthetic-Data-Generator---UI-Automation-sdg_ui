"""
Test-case-driven UI crawler (Phase 3).
Runs the test flow in a browser and captures per-step URL, title, and interactive elements.
Stores results in crawl_snapshots for use by Planner, Generator, and Healer.
"""
from typing import Dict, Any, List, Optional
import json
import os
import subprocess
from pathlib import Path
from datetime import datetime

from sqlalchemy.orm import Session


def _js_esc(s: str) -> str:
    if s is None:
        return ""
    return str(s).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r")


def generate_crawl_script(plan: Dict[str, Any]) -> str:
    """Generate a Playwright script that runs each step and after each step captures URL, title, elements."""
    url = plan.get("url", "https://example.com")
    steps = plan.get("steps", [])
    script = """const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch({ headless: false, slowMo: 300 });
  const context = await browser.newContext();
  const page = await context.newPage();
  const snapshots = [];
  const capture = async (stepIndex) => {
    const url = page.url();
    const pageTitle = await page.title();
    const elements = await page.evaluate(() => {
      const nodes = document.querySelectorAll('a, button, [role=button], input, [onclick]');
      return Array.from(nodes).slice(0, 50).map(n => ({
        tag: n.tagName.toLowerCase(),
        text: (n.innerText || n.value || n.getAttribute('aria-label') || '').substring(0, 80)
      }));
    });
    snapshots.push({ step_index: stepIndex, url, page_title: pageTitle, elements });
  };

  try {
    await page.goto('""" + _js_esc(url) + """', { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(1500);
    await capture(0);
"""
    step_index = 1
    for step in steps:
        action = step.get("action")
        selector = step.get("selector", "")
        value = step.get("value", "")
        if action == "navigate":
            u = step.get("value", url)
            script += f"    await page.goto('{_js_esc(u)}', {{ waitUntil: 'domcontentloaded', timeout: 30000 }});\n"
            script += "    await page.waitForTimeout(1500);\n"
        elif action == "click" and selector:
            script += f"    await page.locator('{_js_esc(selector)}').first().click({{ timeout: 8000 }}).catch(() => {{}});\n"
            script += "    await page.waitForTimeout(1500);\n"
        elif action == "type" and selector and value:
            script += f"    await page.locator('{_js_esc(selector)}').first().fill('{_js_esc(value)}').catch(() => {{}});\n"
            script += "    await page.waitForTimeout(500);\n"
        elif action == "wait":
            d = step.get("duration", 1000)
            script += f"    await page.waitForTimeout({min(d, 3000)});\n"
        else:
            continue
        script += f"    await capture({step_index});\n"
        step_index += 1

    script += """  } catch (e) {
    console.error(e);
  }
  await browser.close();
  const outPath = process.env.CRAWL_OUTPUT_PATH;
  if (outPath) fs.writeFileSync(outPath, JSON.stringify(snapshots), 'utf8');
})();
"""
    return script


def run_test_case_crawl(
    flow_signature: str,
    plan: Dict[str, Any],
    run_dir: Path,
    timeout: int = 120,
) -> List[Dict[str, Any]]:
    """
    Run the crawl script and return list of { step_index, url, page_title, elements }.
    Does not touch DB; caller persists to crawl_snapshots.
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    script = generate_crawl_script(plan)
    script_path = run_dir / "crawl.js"
    output_path = run_dir / "crawl_snapshots.json"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    cwd = run_dir.parent
    env = os.environ.copy()
    env["CRAWL_OUTPUT_PATH"] = str(output_path.absolute())
    node_bin = cwd / "node_modules" / ".bin"
    env["PATH"] = f"{node_bin};{env.get('PATH', '')}"
    try:
        subprocess.run(
            ["node", str(script_path)],
            cwd=str(cwd),
            env=env,
            timeout=timeout,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return []
    if not output_path.exists():
        return []
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def crawl_and_save(
    flow_signature: str,
    plan: Dict[str, Any],
    db: Session,
    run_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """
    Run test-case crawl and persist to crawl_snapshots. Returns list of snapshots.
    """
    from models import CrawlSnapshot

    if run_dir is None:
        run_dir = Path("test_outputs") / "crawl" / flow_signature.replace("/", "_")
    snapshots = run_test_case_crawl(flow_signature, plan, run_dir)
    for s in snapshots:
        existing = db.query(CrawlSnapshot).filter(
            CrawlSnapshot.flow_signature == flow_signature,
            CrawlSnapshot.step_index == s["step_index"],
        ).first()
        if existing:
            existing.url = s.get("url", "")
            existing.page_title = s.get("page_title", "")
            existing.elements_json = s.get("elements", [])
        else:
            db.add(CrawlSnapshot(
                flow_signature=flow_signature,
                step_index=s["step_index"],
                url=s.get("url", ""),
                page_title=s.get("page_title", ""),
                elements_json=s.get("elements", []),
            ))
    db.commit()
    return snapshots


def get_crawl_snapshots_for_flow(db: Session, flow_signature: str) -> List[Dict[str, Any]]:
    """Return crawl_snapshots for a flow, ordered by step_index."""
    from models import CrawlSnapshot

    rows = db.query(CrawlSnapshot).filter(
        CrawlSnapshot.flow_signature == flow_signature,
    ).order_by(CrawlSnapshot.step_index).all()
    return [
        {
            "step_index": r.step_index,
            "url": r.url,
            "page_title": r.page_title,
            "elements": r.elements_json or [],
        }
        for r in rows
    ]
