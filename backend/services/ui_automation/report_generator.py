"""
Professional HTML report generator for UI automation runs.
Produces a single HTML file with embedded or linked step screenshots for verification.
"""
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime
import base64
import json


def _img_to_data_uri(path: Path) -> str:
    """Embed image as data URI for self-contained HTML."""
    if not path or not Path(path).exists():
        return ""
    try:
        data = Path(path).read_bytes()
        return "data:image/png;base64," + base64.b64encode(data).decode("ascii")
    except Exception:
        return ""


def _clean_error_for_report(err: str) -> str:
    """Strip npm/node env warnings so the report shows the actual failure."""
    if not err:
        return ""
    lines = []
    for line in err.splitlines():
        s = line.strip()
        if "npm warn" in s.lower() or "NO_COLOR" in s or "FORCE_COLOR" in s or "trace-warnings" in s:
            continue
        if s.startswith("[1A") or s.startswith("[2K"):
            continue
        lines.append(line)
    out = "\n".join(lines).strip()
    return (out[:1500] + "...") if len(out) > 1500 else out


def generate_html_report(
    title: str,
    test_results: List[Dict[str, Any]],
    output_path: str | Path,
    embed_screenshots: bool = True,
    application: str = "",
) -> str:
    """
    Generate professional HTML report.
    test_results: list of {
      "id", "name", "status", "duration_sec", "plan": { "steps": [...] },
      "step_screenshots": [ {"step": 1, "path": "..."}, ... ],
      "error": optional
    }
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_dir = output_path.parent
    passed = sum(1 for r in test_results if r.get("status") == "passed")
    failed = len(test_results) - passed

    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "<meta charset='UTF-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<title>{title}</title>",
        "<style>",
        "body { font-family: system-ui, 'Segoe UI', sans-serif; margin: 24px; background: #0f172a; color: #e2e8f0; }",
        "h1 { color: #38bdf8; border-bottom: 2px solid #334155; padding-bottom: 8px; }",
        "h2 { color: #94a3b8; margin-top: 32px; }",
        ".summary { display: flex; gap: 24px; margin: 20px 0; flex-wrap: wrap; }",
        ".summary .card { background: #1e293b; padding: 16px 24px; border-radius: 12px; min-width: 140px; }",
        ".summary .card.passed { border-left: 4px solid #22c55e; }",
        ".summary .card.failed { border-left: 4px solid #ef4444; }",
        ".summary .card.total { border-left: 4px solid #38bdf8; }",
        "table { width: 100%; border-collapse: collapse; margin: 12px 0; background: #1e293b; border-radius: 8px; overflow: hidden; }",
        "th, td { padding: 12px; text-align: left; border-bottom: 1px solid #334155; }",
        "th { background: #334155; color: #94a3b8; }",
        ".step-row td { vertical-align: top; }",
        ".step-desc { max-width: 400px; }",
        ".step-img { max-width: 320px; max-height: 240px; border-radius: 8px; border: 1px solid #475569; cursor: pointer; }",
        ".step-img:hover { outline: 2px solid #38bdf8; }",
        ".status-passed { color: #22c55e; }",
        ".status-failed { color: #ef4444; }",
        ".meta { color: #64748b; font-size: 14px; margin: 8px 0; }",
        "a { color: #38bdf8; }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{title}</h1>",
        f"<p class='meta'>Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} | Application: {application or 'N/A'}</p>",
        "<div class='summary'>",
        f"<div class='card total'><strong>Total</strong><br>{len(test_results)}</div>",
        f"<div class='card passed'><strong>Passed</strong><br>{passed}</div>",
        f"<div class='card failed'><strong>Failed</strong><br>{failed}</div>",
        "</div>",
    ]

    for r in test_results:
        tid = r.get("id", "unknown")
        name = r.get("name", tid)
        status = r.get("status", "unknown")
        duration = r.get("duration_sec")
        plan = r.get("plan") or {}
        steps = plan.get("steps", [])
        step_screenshots = r.get("step_screenshots") or []
        error = _clean_error_for_report(r.get("error") or "")
        screenshot_by_step = {s["step"]: s["path"] for s in step_screenshots}

        html_parts.append(f"<h2 id='{tid}'>{tid}: {name}</h2>")
        html_parts.append(f"<p class='meta'>Status: <span class='status-{status}'>{status}</span>")
        if duration is not None:
            html_parts.append(f" | Duration: {duration:.1f}s")
        html_parts.append("</p>")
        if error:
            err_escaped = error.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html_parts.append(f"<pre class='status-failed' style='white-space:pre-wrap;max-width:800px;'>{err_escaped}</pre>")

        html_parts.append("<table><thead><tr><th>Step</th><th>Action / Description</th><th>Screenshot</th></tr></thead><tbody>")
        max_step = max(len(steps) + 1, max(screenshot_by_step.keys(), default=0))
        for num in range(1, max_step + 1):
            if num == 1:
                desc = "Initial page load"
                action = "navigate"
            elif num - 2 < len(steps):
                step = steps[num - 2]
                desc = step.get("description", step.get("action", ""))
                action = step.get("action", "")
            else:
                desc = ""
                action = ""
            img_path = screenshot_by_step.get(num)
            if embed_screenshots and img_path:
                src = _img_to_data_uri(Path(img_path))
                img_html = f"<img class='step-img' src='{src}' alt='Step {num}' title='Step {num}'>" if src else "<span>—</span>"
            elif img_path:
                try:
                    rel = Path(img_path).relative_to(report_dir)
                except ValueError:
                    rel = img_path
                img_html = f"<a href='{rel}' target='_blank'>View</a>"
            else:
                img_html = "<span>—</span>"
            html_parts.append(f"<tr class='step-row'><td>{num}</td><td class='step-desc'><strong>{action}</strong> {desc}</td><td>{img_html}</td></tr>")
        html_parts.append("</tbody></table>")

    html_parts.append("</body></html>")
    html_content = "\n".join(html_parts)
    output_path.write_text(html_content, encoding="utf-8")
    return str(output_path)
