"""
Custom uvicorn runner with Windows ProactorEventLoop support
Fixes NotImplementedError when Playwright tries to create subprocesses on Windows
"""
import sys
import asyncio

# CRITICAL: Set event loop policy BEFORE uvicorn imports anything
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("✓ Windows ProactorEventLoop policy set for Playwright support")

if __name__ == "__main__":
    import uvicorn
    
    # Run uvicorn with the correct event loop
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8004,
        reload=True,
        loop="asyncio"  # Use asyncio loop (with our policy)
    )
