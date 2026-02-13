# LG India E2E reports

- **lg_e2e.json** – Machine-readable results (suite, run_at, total, passed, failed, pass_rate_percent, results[]).
- **lg_e2e.md** – Human-readable report (table + per-case pass/fail and errors).

Regenerate after starting the backend:

```bash
# Terminal 1 – start backend
cd backend
python -m uvicorn main:app --port 8000

# Terminal 2 – run full suite and report
cd ..
python run_lg_test_cases.py --all --report reports/lg_e2e
```

Target: **100%** pass rate.
