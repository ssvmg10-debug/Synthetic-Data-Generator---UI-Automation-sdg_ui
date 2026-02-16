"""
Custom uvicorn runner with Windows ProactorEventLoop support.
Fixes NotImplementedError when Playwright tries to create subprocesses on Windows.
Sets event loop policy BEFORE uvicorn is imported.
On Windows, reload=False by default so the same process (with our policy) runs the app;
with reload=True the spawned worker gets default SelectorEventLoop and Playwright breaks.
"""
import sys
import os
import asyncio
import logging


class SkipRunStatusAccessFilter(logging.Filter):
    """Filter out uvicorn.access logs for /ui/current-run/status (high-frequency polling)."""

    def filter(self, record):
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(getattr(record, "msg", "")) + str(getattr(record, "args", ""))
        return "current-run/status" not in msg


# CRITICAL: Set event loop policy BEFORE uvicorn imports anything
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("✓ Windows ProactorEventLoop policy set for Playwright support")

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("BACKEND_PORT", "8001"))
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "uvicorn.log")

    # On Windows, reload spawns a child process that does NOT run this file, so it gets
    # SelectorEventLoop and Playwright's async subprocess fails. Use reload=False on Windows
    # unless UVICORN_RELOAD=1 is set (then user accepts Playwright may fail in that mode).
    use_reload = os.getenv("UVICORN_RELOAD", "").strip().lower() in ("1", "true", "yes")
    if sys.platform == "win32" and not use_reload:
        use_reload = False
        print("✓ Reload disabled on Windows so Playwright async works (set UVICORN_RELOAD=1 to enable)")

    # Log config: uvicorn + app logs to console and file
    # Suppress uvicorn.access for /ui/current-run/status (frontend polling - clutters logs)
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
        },
        "filters": {
            "skip_run_status": {
                "()": "__main__.SkipRunStatusAccessFilter",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.FileHandler",
                "formatter": "default",
                "filename": log_file,
                "encoding": "utf-8",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["console", "file"], "level": "INFO"},
            "uvicorn.error": {"handlers": ["console", "file"], "level": "INFO"},
            "uvicorn.access": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "filters": ["skip_run_status"],
            },
        },
        "root": {"handlers": ["console", "file"], "level": "INFO"},
    }

    print(f"Logs: {log_file}")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=use_reload,
        log_level="info",
        log_config=log_config,
    )
