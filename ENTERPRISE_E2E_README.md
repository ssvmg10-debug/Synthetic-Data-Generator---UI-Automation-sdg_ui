# Enterprise UI Automation & E2E Report

This document describes the **enterprise-grade UI automation** (testRigor-style) and how to run **30+ test cases each** for **LG India** and **Hilti India** with **per-step screenshots** and **professional HTML reports**.

## What Was Implemented

### 1. **Stronger self-healing (Healer agent)**
- **Multi-strategy**: Registry first, then CSS alternatives (id → data-testid, class → contains, attribute → contains, text → partial/case-insensitive).
- **More error patterns**: Timeout, selector not found, strict mode, unknown selector.
- **Return shape**: `healed_script`, `healed_locator`, `strategy`, `confidence` for downstream and reporting.

### 2. **Per-step screenshots (Generator + Executor)**
- **Generator**: When `capture_screenshots=True` (default), injects `page.screenshot({ path: SCREENSHOT_DIR/step_NN.png })` after each action (navigate, click, type, select, verify, wait).
- **Executor**: Creates `test_outputs/run_<id>/step_screenshots/`, sets `SCREENSHOT_DIR`, runs the test, then collects `step_screenshots: [{ step, path, relative_path }]` and returns them with the result.
- **Report**: Each step in the HTML report shows the matching screenshot (embedded as base64 so the report is self-contained).

### 3. **Planner – enterprise selectors**
- Added patterns for: **Search**, **Menu**, **Cookie accept**, **Shop**, **Products**, **My account**, **Sign in**, **Register**, **Cart**, **Support/Contact**, so LG/Hilti-style sites are covered better.

### 4. **Test cases (30+ per application)**
- **LG India** (`tests/enterprise/lg_india.json`): 35 test cases – homepage, cookie, Shop, TV/Audio/Video, Home Appliances, Air Solutions, Computing, Search, Support, Sign in, Cart, category drill-downs (Refrigerators, Washing Machines, Monitors, etc.).
- **Hilti India** (`tests/enterprise/hilti_india.json`): 35 test cases – homepage, Products, Power tools, Engineering Centre, Business Optimization, Support, Company, Login, Cart, Contact, Search, and sub-categories.

### 5. **Professional HTML report**
- **Summary**: Total / Passed / Failed.
- **Per test case**: ID, name, status, duration, error (if any).
- **Step table**: Step number, action/description, **screenshot** (e.g. login screen with values, selected item, item in cart).
- Screenshots are **embedded** in the HTML so you can verify each step against the image.
- Dark theme, responsive layout.

### 6. **E2E runner** (`run_enterprise_e2e.py`)
- Loads `tests/enterprise/lg_india.json` and `tests/enterprise/hilti_india.json`.
- For each test case: **Planner** → **Generator** (with step screenshots) → **Executor**; on failure runs **Healer** and retries once.
- Writes **reports/enterprise_ui_report_<timestamp>.html** with all results and step screenshots.
- Optional: `--synthetic` runs the **synthetic data** workflow (test-case-driven crawl) for the same apps and writes **reports/synthetic_crawl_report_<timestamp>.html**.

### 7. **Synthetic data – test-case-driven crawl**
- With `--synthetic`, the runner builds combined test-case text (URLs + steps) per app and calls `run_synthetic_data_workflow`. Crawl is driven by **URLs/steps from test cases**, not the whole application.
- Synthetic report lists application, status, run_id, schema_id, rows (and error if any). Crawl snapshots can be added later by extending the UI schema extractor to save a screenshot per URL.

---

## How to Run

### Prerequisites
- **Backend** dependencies installed (`pip install -r requirements.txt`).
- **Node/Playwright** in `backend/`: `cd backend && npm install @playwright/test && npx playwright install`
- **Database** created and migrated (`python run_migrations.py`).
- **Optional**: Azure OpenAI configured for synthetic workflow and planner merge.

### Commands (from project root)

```bash
# Run all tests (LG + Hilti), generate report with step screenshots
python run_enterprise_e2e.py

# LG India only
python run_enterprise_e2e.py --app lg

# Hilti India only
python run_enterprise_e2e.py --app hilti

# Quick check: first 5 tests per app
python run_enterprise_e2e.py --limit 5

# Also run synthetic data crawl for same test cases
python run_enterprise_e2e.py --synthetic

# Custom report path
python run_enterprise_e2e.py --out reports/my_report.html

# Disable step screenshots (faster, smaller report)
python run_enterprise_e2e.py --no-screenshots
```

### Output
- **UI report**: `reports/enterprise_ui_report_<timestamp>.html`  
  Open in a browser to see summary, each test case, and **step-by-step screenshots** (login screen, selected item, cart, etc.) for verification.
- **Synthetic report** (if `--synthetic`): `reports/synthetic_crawl_report_<timestamp>.html`

---

## Verification

- **Login**: In the report, open a test that includes sign-in; the step that loads the login page should show a **screenshot of the login UI** with fields visible.
- **Selecting item**: For tests that open a product/category, the step that selects the item should have a **screenshot of the selected item** (or the list with selection).
- **Adding to cart**: The step after “add to cart” should show a **screenshot with the item in the cart** (or cart count/icon).

If a step has no screenshot (e.g. test failed before that step), the cell shows “—”. Fix failing steps (selectors, timing) and re-run to get full coverage.

---

## References

- [testRigor](https://testrigor.com/) – AI-based test automation (plain English, self-healing).
- **LG India**: https://www.lg.com/in/
- **Hilti India**: https://www.hilti.in/
