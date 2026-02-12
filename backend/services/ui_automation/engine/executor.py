"""
Playwright Executor
Executes UI tests using Playwright.
Phase 2: On failure, reads failure_context.json (step, URL, page elements) when generated script writes it.
"""
from typing import Dict, Any, List
import subprocess
import os
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def _backend_dir() -> Path:
    """Backend root (so node_modules/@playwright/test and playwright.config resolve)."""
    return Path(__file__).resolve().parent.parent.parent.parent


class PlaywrightExecutor:
    def __init__(self):
        self.output_dir = _backend_dir() / "test_outputs"
        self.output_dir.mkdir(exist_ok=True)

    def execute(
        self,
        script: str,
        test_case_id: int,
        capture_step_screenshots: bool = True,
    ) -> Dict[str, Any]:
        """Execute Playwright script. Sets SCREENSHOT_DIR for per-step screenshots and returns step_screenshots."""
        logger.info("Starting test execution for test case %s", test_case_id)
        run_dir = self.output_dir / f"run_{test_case_id}"
        run_dir.mkdir(exist_ok=True)
        screenshot_dir = run_dir / "step_screenshots"
        screenshot_dir.mkdir(exist_ok=True)
        test_file = run_dir / "test.spec.js"
        logs_path = run_dir / "logs.txt"

        try:
            headed_script = script.replace(
                "test('",
                "test.use({ headless: false, slowMo: 500 });\n\ntest('",
            )
            with open(test_file, "w") as f:
                f.write(headed_script)

            backend_root = _backend_dir()
            node_bin_path = backend_root / "node_modules" / ".bin"
            cwd = backend_root
            # Pass path relative to cwd so Playwright finds the test file (use forward slashes for CLI)
            test_file_rel = test_file.relative_to(cwd).as_posix()
            env = os.environ.copy()
            env["PATH"] = f"{node_bin_path};{env.get('PATH', '')}"
            env["SCREENSHOT_DIR"] = str(screenshot_dir.absolute())
            failure_context_path = run_dir / "failure_context.json"
            env["FAILURE_CONTEXT_PATH"] = str(failure_context_path.absolute())

            # Use npx so local node_modules/@playwright/test is used
            cmd = f'npx playwright test "{test_file_rel}" --reporter=line --headed'
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
                cwd=str(cwd),
                shell=True,
                env=env,
            )

            logs = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n\nExit Code: {result.returncode}"
            # Always write as UTF-8 so logs.txt isn't empty on Windows due to encoding issues.
            with open(logs_path, "w", encoding="utf-8", errors="replace") as f:
                f.write(logs)

            status = "passed" if result.returncode == 0 else "failed"
            step_screenshots: List[Dict[str, Any]] = []
            if capture_step_screenshots and screenshot_dir.exists():
                for p in sorted(screenshot_dir.glob("step_*.png")):
                    step_num = p.stem.replace("step_", "")
                    step_screenshots.append({
                        "step": int(step_num) if step_num.isdigit() else step_num,
                        "path": str(p.absolute()),
                        "relative_path": p.name,
                    })

            last_screenshot = step_screenshots[-1]["path"] if step_screenshots else None
            if status == "passed":
                logger.info("Test execution completed successfully")
            else:
                logger.error("Test execution failed: %s", result.stderr)

            # Prefer stdout for failure message (Playwright puts test errors there)
            err_msg = None
            if result.returncode != 0:
                err_msg = (result.stdout or "").strip() or (result.stderr or "").strip()
                if len(err_msg) > 2000:
                    err_msg = err_msg[:2000] + "..."

            # Phase 2: Read failure context if script wrote it (step, URL, page elements for healer)
            failed_step_index = None
            failure_url = None
            failure_page_elements = None
            failed_selector = None
            if result.returncode != 0:
                fc_path = run_dir / "failure_context.json"
                if fc_path.exists():
                    try:
                        with open(fc_path, "r", encoding="utf-8") as f:
                            fc = json.load(f)
                        failed_step_index = fc.get("failed_step_index")
                        failure_url = fc.get("failure_url")
                        failure_page_elements = fc.get("failure_page_elements")
                        failed_selector = fc.get("failed_selector")
                    except Exception as e:
                        logger.debug("Could not read failure context: %s", e)

            return {
                "status": status,
                "logs": logs,
                "logs_path": str(logs_path),
                "screenshot_path": last_screenshot,
                "step_screenshots": step_screenshots,
                "exit_code": result.returncode,
                "error": err_msg,
                "failed_step_index": failed_step_index,
                "failure_url": failure_url,
                "failure_page_elements": failure_page_elements,
                "failed_selector": failed_selector,
            }

        except subprocess.TimeoutExpired:
            return {
                "status": "failed",
                "logs": "Test execution timed out",
                "logs_path": None,
                "screenshot_path": None,
                "step_screenshots": [],
                "error": "Timeout after 180 seconds",
            }
        except Exception as e:
            return {
                "status": "failed",
                "logs": f"Execution error: {str(e)}",
                "logs_path": None,
                "screenshot_path": None,
                "step_screenshots": [],
                "error": str(e),
            }
    
    def check_playwright_installed(self) -> bool:
        """Check if Playwright is installed"""
        try:
            result = subprocess.run(
                ["npx", "playwright", "--version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def install_playwright(self) -> Dict[str, Any]:
        """Install Playwright"""
        try:
            result = subprocess.run(
                ["npm", "install", "@playwright/test"],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                # Install browsers
                subprocess.run(
                    ["npx", "playwright", "install"],
                    capture_output=True,
                    timeout=300
                )
                
                return {
                    "success": True,
                    "message": "Playwright installed successfully"
                }
            else:
                return {
                    "success": False,
                    "message": f"Installation failed: {result.stderr}"
                }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Installation error: {str(e)}"
            }
