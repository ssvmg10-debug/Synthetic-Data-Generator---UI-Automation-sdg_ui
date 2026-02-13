# Implementation Plan: Visible Browser & In-App Live View (Cursor IDE–Style)

This document describes how to add **Cursor IDE–style** behavior: (1) a **visible browser** during UI automation so users can watch the test run, and (2) an **in-app live view** so the run can be watched inside the application without switching to a separate window.

---

## Goal

- **Visible browser**: When running UI automation, optionally open a real browser window (on the machine where the backend runs) so the user can watch the test execute—same idea as Cursor opening a browser for testing.
- **In-app live view**: Optionally show a **live view** inside the application (screenshot stream or step-by-step screenshots) so the run is visible in the app even when the user doesn’t look at the separate browser window.

---

## Current State

- **Playwright executor** already runs in **headed mode** by default:
  - CLI: `npx playwright test ... --headed` (see `backend/services/ui_automation/engine/executor.py`).
  - Config: `playwright.executor.config.js` has `headless: false`.
- So when the backend runs **on the same machine** as the user (e.g. `localhost`), a Chromium window already opens. There is no UI toggle or API flag to switch between headed/headless.
- **Screenshots**: The executor already captures per-step screenshots under `test_outputs/run_{test_case_id}/step_screenshots/` and returns them in the response after the run completes. There is no “live” feed during the run.

---

## Scope

| Feature | Description |
|--------|-------------|
| **1. Configurable visible browser** | API flag and UI toggle: “Run with visible browser” (headed) vs “Run in background” (headless). When backend is local, headed = user sees a browser window. |
| **2. In-app live view** | During a run, show the latest step screenshot inside the app (e.g. a “Live view” panel) that updates every 1–2 s until the run finishes. |

---

## Architecture Overview

- **Backend** continues to run Playwright in a subprocess. Headed/headless is controlled by:
  - Executor: pass `headed: bool` into `execute()` and build the CLI and/or config accordingly.
  - API: add a request field (e.g. `visible_browser: bool`) and pass it through to the executor.
- **Live view** works by:
  - The executor (and generated script) already write step screenshots to `run_dir/step_screenshots/step_*.png` as the test runs.
  - Backend exposes an endpoint that returns the **latest** screenshot for the “current” or a given run (e.g. by `test_case_id` or `execution_id`).
  - Frontend polls this endpoint every 1–2 s while a run is in progress and displays the image in a “Live view” panel.

To support polling **during** a run, we need either:

- **Option A (simpler)**  
  - Keep the existing **synchronous** `POST /ui/run`.  
  - When a run **starts**, backend registers a “current run” (e.g. in-memory: `current_run = { test_case_id, started_at }`).  
  - New endpoint: `GET /ui/current-run/live-screenshot` returns the latest `step_*.png` from `test_outputs/run_{test_case_id}/step_screenshots/` (or 404 if no run / no screenshot yet).  
  - When the run **ends**, backend clears the current run.  
  - Frontend: after sending `POST /ui/run`, **in a separate flow** (e.g. a “Watch live” button or automatic when “visible browser” is on), start polling `GET /ui/current-run/live-screenshot` until the POST request completes or a timeout.  
  - Caveat: the POST blocks the HTTP connection, so the frontend cannot get `execution_id` until the run finishes. So the frontend must “infer” that a run is in progress when the user clicked Run and the request is still pending. While the request is in flight, the frontend can poll the “current run” live screenshot endpoint (backend knows current run from the in-memory store).

- **Option B (richer)**  
  - Make execution **asynchronous**: `POST /ui/run` creates a test case and an execution row with status `running`, returns **202 Accepted** with `execution_id` immediately, and runs the executor in a **background task**.  
  - New endpoint: `GET /ui/executions/{execution_id}/live-screenshot` returns the latest step screenshot for that execution (using `execution.test_case_id` → `run_dir`).  
  - New endpoint: `GET /ui/executions/{execution_id}/status` returns `{ status: "running" | "passed" | "failed", ... }`.  
  - Frontend: on Run → POST → 202 + `execution_id` → poll status and live-screenshot until status is not `running`.  
  - This allows multiple runs and a cleaner “run by id” model; implementation is a bit more (background task, create execution at start).

**Recommendation:** Start with **Option A** for a minimal “Cursor-like” live view with minimal backend change; later move to **Option B** if you want multiple concurrent runs and a stable execution-id–based API.

---

## Phase 1: Configurable Visible Browser (Headed / Headless)

### 1.1 Backend: Executor

- **File**: `backend/services/ui_automation/engine/executor.py`
- Add parameter to `execute()`:
  - `headed: bool = True` (default keeps current behavior).
- Use it to:
  - Build the CLI: if `headed` then add `--headed`, else add `--headless`.
  - Optionally pass an env var (e.g. `PLAYWRIGHT_HEADED=1/0`) and read it in `playwright.executor.config.js` to set `headless: !env.PLAYWRIGHT_HEADED`. Prefer CLI flag if it overrides config.
- Ensure `playwright.executor.config.js` does not force `headless: false` when we want headless; either:
  - Rely on CLI `--headed` / `--headless` to override config, or
  - Generate a small config snippet or pass headless via env and read it in the config.

**Playwright behavior:** `npx playwright test --headed` overrides config `headless: true` and shows the browser. So: `cmd += ' --headed' if headed else ' --headless'`.

### 1.2 Backend: API

- **Files**: `backend/routers/ui_automation.py`, request model `UITestRequest`.
- Add optional field, e.g.:
  - `visible_browser: Optional[bool] = True`  
  (or `headed: Optional[bool] = True`).
- In `run_full_ui_test` and in the LangGraph workflow endpoint (`run_ui_automation_workflow_endpoint`), pass this flag through to the executor:
  - `executor.execute(..., headed=request.visible_browser if request.visible_browser is not None else True)`.
- In `execute_ui_test` (if used), accept and pass the same.

### 1.3 Frontend

- Where the user triggers “Run UI automation” (e.g. chat send or a dedicated Run button), add a checkbox or toggle:
  - **“Show browser during run”** (default on): sets `visible_browser: true`.
  - Off: sets `visible_browser: false`.
- Send this in the request body for `POST /ui/run` (and `POST /ui/run-workflow` if supported).

### 1.4 Documentation

- In README or a short “UI Automation” doc, state:
  - When **visible browser** is on, a browser window opens on the **machine where the backend is running** (e.g. on your PC when backend is local). This is the same idea as Cursor opening a browser when testing.
  - For **remote backends** (e.g. server/CI), the browser would open on the server; use **in-app live view** (Phase 2) to see the run from the client.

---

## Phase 2: In-App Live View (Latest Screenshot While Run Is in Progress)

### 2.1 Backend: “Current run” registry (Option A)

- **File**: New small module, e.g. `backend/services/ui_automation/engine/current_run.py`, or a few variables in `executor.py` / router.
- In-memory store (or thread-safe structure):
  - `current_run: Optional[Dict] = None`  
    e.g. `{ "test_case_id": int, "started_at": datetime }`.
- When a run **starts** (in `run_full_ui_test` or the workflow endpoint, right after creating the test case and before calling the executor):
  - Set `current_run = { "test_case_id": test_case.id, "started_at": ... }`.
- When the run **ends** (success or exception):
  - Clear `current_run = None` in a `finally` block.

### 2.2 Backend: Live screenshot endpoint

- **File**: `backend/routers/ui_automation.py`.
- New endpoint: `GET /ui/current-run/live-screenshot`
  - If no `current_run`: return **404** (or 204 No Content).
  - Else: `run_dir = test_outputs / f"run_{current_run['test_case_id']}"`, `screenshot_dir = run_dir / "step_screenshots"`.
  - If `screenshot_dir` exists, find the latest file matching `step_*.png` (by name or mtime).
  - If found: stream the file with `Content-Type: image/png` (e.g. `FileResponse` or equivalent).
  - If not found (no screenshot yet): return **404** (frontend can keep polling).

Use a lock or atomic read of `current_run` to avoid races.

### 2.3 Backend: Run in thread (so “current run” is set during execution)

- The request handler that runs the executor is currently **synchronous** (blocking) until the executor returns. So `current_run` is set at the start and cleared at the end; during that time, another request can call `GET /ui/current-run/live-screenshot` and get the latest step screenshot. No change needed to run the executor in a thread for Option A, as long as the executor runs in the same process and writes step screenshots under `run_dir` as it goes. The only requirement is that the **executor’s subprocess** writes step screenshots **during** the run (which it already does). So the live endpoint will see new `step_*.png` files as the test progresses.

### 2.4 Frontend: Live view panel

- When the user starts a UI automation run (e.g. sends a message that triggers `POST /ui/run`):
  - Start the POST request (e.g. with long timeout).
  - Optionally show a “Live view” panel (e.g. above or beside the chat).
  - Start polling: every 1–2 s, call `GET /ui/current-run/live-screenshot` (or a URL that returns the image).
  - Display the image in the panel (e.g. `<img src="/api/ui/current-run/live-screenshot?t=<timestamp>" />` with timestamp to avoid cache, or fetch as blob and set as object URL).
  - When the POST completes (success or error) or after a timeout (e.g. 8 minutes), stop polling and, if desired, show the final step screenshots from the response instead.

### 2.5 Optional: Execution-based live view (Option B)

- If you later switch to **async execution** (202 + background task):
  - Create `UIExecutionRun` at **start** with `status = "running"`, return `execution_id` in 202.
  - Run the executor in a background task (e.g. `asyncio.to_thread(executor.execute, ...)` or a thread pool). On completion, update the execution row (status, logs_path, etc.).
  - Add `GET /ui/executions/{execution_id}/live-screenshot`: resolve `execution.test_case_id` → `run_dir` → latest `step_*.png`; return image or 404.
  - Add `GET /ui/executions/{execution_id}/status`: return `{ status, ... }`.
  - Frontend: after 202, poll both endpoints until `status !== "running"`.

---

## Phase 3: UX and Edge Cases

- **Multiple tabs/users**: Option A uses a single “current run”. If only one run at a time is allowed, this is fine. For multiple users, Option B (execution_id–based) is better; optionally add a “run token” or session so the live endpoint only returns screenshots for “this” user’s run.
- **Stale screenshots**: Live endpoint always returns the **latest** `step_*.png` in that run dir; no need to delete old ones during the run.
- **Backend on another machine**: Visible browser will open on the server; user relies on **live view** in the app to watch. Document this.
- **Security**: Live screenshot endpoint should be protected by the same auth as the rest of the UI automation API (e.g. require login or API key if applicable).

---

## Implementation Checklist

### Phase 1: Visible browser

- [ ] **Executor**: Add `headed: bool = True` to `execute()`; build CLI with `--headed` or `--headless` accordingly.
- [ ] **Config**: Ensure `playwright.executor.config.js` does not force headed when `--headless` is used (rely on CLI override or env).
- [ ] **API**: Add `visible_browser: Optional[bool] = True` to `UITestRequest`; pass to executor in `/ui/run` and `/ui/run-workflow`.
- [ ] **Frontend**: Add “Show browser during run” toggle; send `visible_browser` in request.
- [ ] **Docs**: Short note that visible browser opens on the machine where the backend runs; recommend live view for remote backends.

### Phase 2: Live view (Option A)

- [ ] **Backend**: In-memory `current_run` set when run starts, cleared when run ends (in `run_full_ui_test` and workflow endpoint).
- [ ] **Backend**: `GET /ui/current-run/live-screenshot` returning latest `step_*.png` from current run’s `step_screenshots` dir.
- [ ] **Frontend**: When a run is started, show “Live view” panel and poll live-screenshot every 1–2 s until the run request completes or times out.
- [ ] **Frontend**: Display the image in the panel; optionally show “Waiting for first screenshot…” when 404.

### Phase 3 (optional)

- [ ] **Async execution**: 202 + background task; create execution at start; `GET /ui/executions/{id}/live-screenshot` and `.../status`.
- [ ] **Auth**: Ensure live screenshot endpoint is behind same auth as other UI automation endpoints.

---

## Summary

- **Visible browser**: Add a single flag (API + UI) to choose headed vs headless. When backend is local and headed is on, the user sees a browser window like in Cursor.
- **In-app live view**: Expose the latest step screenshot via a “current run” (or execution) endpoint and poll from the frontend so the run can be watched inside the app. This gives a Cursor-like “see the test run” experience without requiring the user to look at a separate window.
