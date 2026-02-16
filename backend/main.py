"""
FastAPI Backend Main Entry Point
Single backend service running on port 8000
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from routers import synthetic_data, ui_automation, api_automation, chats, run_status
import logging
import sys
import os
import asyncio

# Fix for Windows: Use ProactorEventLoop for Playwright subprocess support
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Configure logging to show in console and file
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "uvicorn.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding="utf-8")
    ]
)
# Ensure uvicorn logs also go to same format
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

logger = logging.getLogger(__name__)
logger.info(f"Logging to file: {log_file}")

app = FastAPI(
    title="Enterprise Test Automation Platform",
    description="Unified backend for Synthetic Data Generation, UI & API Automation",
    version="1.0.0"
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every incoming request so you can see what is running in the backend terminal.
    Skips high-frequency polling endpoints that clutter logs (run status, chats list).
    """
    method = request.method
    path = request.url.path
    skip_log = path in ("/ui/current-run/status", "/chats") and method == "GET"
    if not skip_log:
        logger.info("[REQUEST] %s %s", method, path)
    response = await call_next(request)
    if not skip_log:
        logger.info("[RESPONSE] %s %s -> %s", method, path, response.status_code)
    return response


# CORS for React frontend (Vite dev server on 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(synthetic_data.router, prefix="/synthetic", tags=["Synthetic Data"])
app.include_router(ui_automation.router, prefix="/ui", tags=["UI Automation"])
app.include_router(api_automation.router, prefix="/api", tags=["API Automation"])
app.include_router(chats.router, prefix="/chats", tags=["Chats"])
app.include_router(run_status.router, prefix="/run-status", tags=["Run Status"])
# app.include_router(integrated_testing.router)  # TODO: Fix model imports

@app.on_event("startup")
async def startup_event():
    port = os.getenv("BACKEND_PORT") or os.getenv("PORT") or "8000"
    logger.info("=" * 80)
    logger.info("Enterprise Test Automation Platform - Starting Up")
    logger.info("=" * 80)
    logger.info("Server: http://localhost:%s", port)
    logger.info("API Docs: http://localhost:%s/docs", port)
    logger.info("=" * 80)

@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {
        "message": "Enterprise Test Automation Platform API",
        "endpoints": {
            "synthetic": "/synthetic/*",
            "ui_automation": "/ui/*",
            "api_automation": "/api/*",
            "chats": "/chats/*",
            "run_status": "/run-status/*"
        }
    }

@app.get("/health")
async def health_check():
    logger.info("Health check endpoint accessed")
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting Uvicorn server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
