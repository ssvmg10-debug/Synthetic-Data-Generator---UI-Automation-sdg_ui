# LG India E2E Suite – 100% Pass Rate Target

All test cases in `backend/lg_test_cases.py` are designed to be run **end-to-end** against https://www.lg.com/in. The goal is **100% pass rate** for the suite.

## Run the full suite (all 25 test cases)

From the **project root**, with the **backend running** (e.g. `cd backend && uvicorn main:app --port 8000`):

```bash
# Run all LG test cases E2E
python run_lg_test_cases.py --all
```

- Each test is executed via `POST /ui/run` (plan → generate → execute → heal if needed).
- The script prints per-test pass/fail and a **summary** with total, passed, failed, and **pass rate %**.
- **Exit code:** `0` only when all tests passed (100%); `1` if any failed.

## Options

| Option | Description |
|--------|-------------|
| `--all` | Run all 25 test cases (full E2E suite). |
| `--report PATH` | Write JSON and Markdown report to `PATH` (e.g. `reports/lg_e2e`). |
| `--fail-fast` | Stop on first failure (use with `--all`). |
| `--no-browser` | Run Playwright headless (no visible browser). |
| `--timeout N` | Request timeout per test in seconds (default 500). |
| `--id lg_01_...` | Run a single test case by id. |
| `--index N` | Run the N-th test case (0-based). |
| `--list` | List all test case ids and names. |

## Examples

```bash
# Full suite with report (aim for 100%)
python run_lg_test_cases.py --all --report reports/lg_e2e

# Full suite, stop on first failure
python run_lg_test_cases.py --all --fail-fast

# Single case
python run_lg_test_cases.py --id lg_01_buy_tv_under_30k

# List all cases
python run_lg_test_cases.py --list
```

## Backend and environment

- **Backend** must be running (default port 8000). Set `BACKEND_PORT` or `VITE_API_URL` if different (e.g. `http://localhost:8001`).
- **Playwright** must be installed from the backend directory: `cd backend && npx playwright install`.
- LG-specific config (cookie step, selectors) is applied automatically via `config/app_config.py` when the plan URL is lg.com.

## Interpreting results

- **Pass rate 100%:** All run tests passed; exit code 0.
- **Pass rate &lt; 100%:** One or more tests failed; failed cases are listed with error snippets; exit code 1.

Use the generated **report** (`.json` / `.md`) to track progress and debug failures until the suite reaches 100%.
