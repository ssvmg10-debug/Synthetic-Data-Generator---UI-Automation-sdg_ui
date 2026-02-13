# LG India UI Automation & In-App Live View

## LG test cases (25 end-to-end) – target 100%

- **Location**: `backend/lg_test_cases.py` – 25 test cases covering search, PDP, cart, checkout, categories (TV, Appliances, Computing, Support), pincode, guest checkout, compare, etc.
- **Run the full E2E suite (all 25, target 100% pass rate)**:
  ```bash
  python run_lg_test_cases.py --all
  python run_lg_test_cases.py --all --report reports/lg_e2e   # with report
  ```
  Exit code is 0 only when all tests pass (100%). See **[LG_100_E2E_SUITE.md](LG_100_E2E_SUITE.md)** for options.
- **Run one case** (from project root):
  ```bash
  python run_lg_test_cases.py --id lg_01_buy_tv_under_30k
  ```
- **Run first case by index**:
  ```bash
  python run_lg_test_cases.py
  ```
- **List all cases**:
  ```bash
  python run_lg_test_cases.py --list
  ```

Backend must be running (e.g. `cd backend && uvicorn main:app --port 8000`). Default API base is `http://localhost:8000`; set `BACKEND_PORT` or `VITE_API_URL` if you use another port.

---

## In-app browser (Cursor-style live view)

The **in-application browser** works like **Cursor IDE’s browser view**: you see the browser **inside the app** as a live-updating stream.

1. When you start a UI automation run, the backend sets a “current run” and runs Playwright (headed or headless).
2. The **generated script** writes:
   - **Per-step screenshots**: `step_01.png`, `step_02.png`, …
   - **Live stream**: every **2 seconds** it overwrites `live.png` with the current page screenshot.
3. The frontend **polls** `GET /ui/current-run/live-screenshot` every **1 second**. The backend returns `live.png` when it’s recent (&lt; 15 s), otherwise the latest `step_*.png`.
4. The “Live browser” panel in the UI Automation chat shows this stream, so you watch the run inside the app without switching to a separate window.

**Chrome DevTools Protocol (CDP) is not required**; the view is a real-time screenshot stream served by the backend.

### Making the live view work

1. **Backend and frontend ports**
   - Backend: usually `8000` (or set `BACKEND_PORT`).
   - Frontend (Vite): `5173`. The Vite proxy forwards `/ui`, `/chats`, etc. to the backend. Proxy target is taken from `BACKEND_PORT` or `VITE_BACKEND_PORT` (default `8000`). If your backend runs on `8001`, start Vite with:
     ```bash
     set BACKEND_PORT=8001
     npm run dev
     ```
   - So the live screenshot URL becomes `http://localhost:5173/ui/current-run/live-screenshot?t=...` and is proxied to the backend.

2. **Playwright must be installed (backend)**
   - From **backend** directory:
     ```bash
     npm install @playwright/test
     npx playwright install
     ```
   - This installs Chromium (and optionally Firefox/WebKit). Without this, the executor cannot run and no step screenshots are produced.

3. **When the live view shows**
   - The panel shows “Starting run…” during plan/generate. **Screenshots appear only when the stage is “execute” or “heal”** (when the Playwright script is actually running and writing `step_*.png`). If the run fails before the first step screenshot (e.g. script error), the panel may show a placeholder until the run finishes.

4. **Cache**
   - The live-screenshot endpoint sends **no-cache** headers so the browser doesn’t reuse an old image when polling.

---

## True embedded browser (CDP) – optional future

If you want a **real browser instance rendered inside the app** (like an iframe or embedded Chromium), that would require:

- A browser launched with **remote debugging** (e.g. `chromium.launch({ args: ['--remote-debugging-port=9222'] })`).
- A frontend that connects via **CDP** or a **screenshot/streaming API** to show the live view. That’s a larger feature and not implemented here; the current “in-app browser” is the **live screenshot polling** above.

---

## Stopping long-running UI/crawler processes

If a previous UI automation or crawler run is still running (e.g. for days):

1. **List long-running processes** (Node, Python, etc. running more than 24 hours):
   ```powershell
   .\scripts\stop_long_running_ui_processes.ps1
   ```
2. **Kill them**:
   ```powershell
   .\scripts\stop_long_running_ui_processes.ps1 -Kill
   ```
3. Optional: use `-HoursOlderThan 2` to target processes older than 2 hours.

You can also close any stray Chromium/Edge windows or kill `node` / `python` processes from Task Manager if you know they belong to this project.
