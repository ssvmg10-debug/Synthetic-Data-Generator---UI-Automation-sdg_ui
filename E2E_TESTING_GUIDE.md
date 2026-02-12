# End-to-End Testing Guide
## Integrated Synthetic Data Generation + UI Automation

This guide shows how to run complete end-to-end tests combining SDV (Synthetic Data Vault) and Playwright Test Agents.

---

## 🎯 Quick Start - Running Your Test Cases

### Option 1: Using the Integrated API (Recommended)

```bash
POST http://localhost:8000/integrated/run-full-workflow
Content-Type: application/json

{
  "test_cases": [
    "Navigate to https://www.lg.com/in, search for lg 108cm tv, click buy for product under 30000, fill pincode 500032",
    "Open https://sauce-demo.myshopify.com/, click grey shirt, add to cart, checkout as guest, fill form",
    "Open https://www.hilti.in/, navigate to Power Tools > Rotary Hammers, add to cart, checkout"
  ],
  "use_synthetic_data": true,
  "schema_info": {
    "fields": [
      {"name": "first_name", "type": "string"},
      {"name": "last_name", "type": "string"},
      {"name": "email", "type": "email"},
      {"name": "phone", "type": "phone"},
      {"name": "address", "type": "address"},
      {"name": "city", "type": "string"},
      {"name": "zipcode", "type": "zipcode"}
    ]
  },
  "num_records": 10
}
```

**Response:**
```json
{
  "workflow_id": "integrated_20260211_160000",
  "started_at": "2026-02-11T16:00:00",
  "completed_at": "2026-02-11T16:05:30",
  "synthetic_data": {
    "status": "success",
    "records_generated": 10,
    "data": [...]
  },
  "test_cases": [
    {
      "test_number": 1,
      "description": "Navigate to https://www.lg.com/in...",
      "status": "success",
      "stages": {
        "planning": {"status": "success"},
        "generation": {"status": "success"},
        "validation": {"status": "success"},
        "execution": {"status": "success"}
      }
    }
  ],
  "summary": {
    "total_tests": 3,
    "passed": 2,
    "failed": 0,
    "healed": 1
  }
}
```

### Option 2: Using Standard UI Automation Endpoint

```bash
POST http://localhost:8000/ui/run
Content-Type: application/json

{
  "raw_input": "open https://sauce-demo.myshopify.com/, click on grey shirt, add to cart, checkout as guest, fill all fields",
  "use_synthetic_data": true
}
```

---

## 🧪 Test Cases Provided

### Test Case 1: LG India - TV Purchase
**Steps:**
1. Navigate to https://www.lg.com/in
2. Click on search option
3. Search for "lg 108cm tv"
4. Click Buy Now for product under ₹30,000
5. Fill pincode: 500032
6. Click Check
7. Click Checkout
8. Continue as Guest
9. Fill billing/shipping details

**Playwright Test:** `test_outputs/comprehensive_e2e_tests.spec.js` (Test 1)

### Test Case 2: Sauce Demo - Grey Shirt Checkout
**Steps:**
1. Open https://sauce-demo.myshopify.com/
2. Click on grey shirt
3. Click Add to Cart (don't click My Cart)
4. Click Checkout
5. Sign in and continue as guest
6. Fill all checkout form fields
7. Click Pay Now

**Playwright Test:** `test_outputs/comprehensive_e2e_tests.spec.js` (Test 2)

### Test Case 3: Hilti India - Rotary Hammer
**Steps:**
1. Open https://www.hilti.in/
2. Navigate to Power Tools
3. Navigate to Rotary Hammers
4. Click on any item
5. Add to cart
6. Checkout

**Playwright Test:** `test_outputs/comprehensive_e2e_tests.spec.js` (Test 3)

---

## 🎬 Running Tests in HEADED Mode

All tests run in **headed mode** by default - you'll see the browser window with 500ms slowdown for visibility.

### Run All Tests
```powershell
cd backend
$env:Path = "$PWD\node_modules\.bin;$env:Path"
playwright test test_outputs/comprehensive_e2e_tests.spec.js --headed --workers=1 --project=chromium
```

### Run Single Test
```powershell
playwright test test_outputs/comprehensive_e2e_tests.spec.js --headed --workers=1 --project=chromium --grep "Sauce Demo"
```

### Run with Debugging
```powershell
playwright test test_outputs/comprehensive_e2e_tests.spec.js --headed --debug
```

---

## 🔧 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    USER REQUEST                              │
│   "Test checkout flow with synthetic customer data"         │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          v
┌─────────────────────────────────────────────────────────────┐
│              INTEGRATED TESTING ROUTER                       │
│         /integrated/run-full-workflow                        │
└──────────┬──────────────────────────────┬───────────────────┘
           │                               │
           v                               v
┌──────────────────────┐     ┌────────────────────────────────┐
│   SYNTHETIC DATA     │     │    UI AUTOMATION AGENTS        │
│   GENERATOR (SDV)    │     │  (Playwright Test Agents)      │
└──────────┬───────────┘     └─────┬──────────────────────────┘
           │                       │
           │  ┌────────────────────┘
           │  │  ┌─────────────────────────────┐
           │  │  │  1. Planner Agent          │
           │  │  │     - Converts NL to plan  │
           │  │  └─────────────────────────────┘
           │  │  ┌─────────────────────────────┐
           │  └──│  2. Generator Agent        │
           │     │     - Creates Playwright   │
           │     │       scripts              │
           │     └─────────────────────────────┘
           │     ┌─────────────────────────────┐
           └─────│  3. Data Injector          │
                 │     - Inserts SDV data     │
                 │       into scripts         │
                 └─────────────────────────────┘
                 ┌─────────────────────────────┐
                 │  4. Executor               │
                 │     - Runs in HEADED mode  │
                 └─────────────────────────────┘
                 ┌─────────────────────────────┐
                 │  5. Healer Agent           │
                 │     - Auto-fixes failures  │
                 └─────────────────────────────┘
                           │
                           v
                 ┌─────────────────────────────┐
                 │   TEST RESULTS & LOGS       │
                 │  - Screenshots              │
                 │  - Videos                   │
                 │  - Execution logs           │
                 └─────────────────────────────┘
```

---

## 📦 Key Files

| File | Purpose |
|------|---------|
| `routers/integrated_testing.py` | Integrated workflow router (SDV + Playwright) |
| `routers/ui_automation.py` | Standard UI automation endpoint |
| `routers/synthetic_data.py` | SDV data generation |
| `services/ui_automation/agents/playwright_test_agents.py` | Playwright Test Agents wrapper |
| `services/ui_automation/engine/executor.py` | Test execution engine (HEADED mode) |
| `services/synthetic/sdv_engine/generator.py` | SDV data generator |
| `test_outputs/comprehensive_e2e_tests.spec.js` | Your 3 test cases |
| `playwright.config.ts` | Playwright configuration (headed mode enabled) |

---

## 🩹 Self-Healing

If tests fail due to selector issues, the **Healer Agent** automatically:
1. Analyzes the error
2. Inspects the page structure
3. Suggests alternative selectors
4. Re-runs the test with fixes

**Healing is logged:**
```
❌ Test FAILED - Attempting self-healing...
🩹 Test HEALED successfully!
```

---

## 📊 Synthetic Data Integration

When `use_synthetic_data: true`:

1. **SDV generates realistic test data:**
   - Names, emails, phone numbers
   - Addresses, cities, zipcodes
   - Credit card numbers (test mode)
   - Custom fields from your schema

2. **Data is injected into tests:**
   ```javascript
   await page.fill('input[name="email"]', 'jane.doe@example.com');  // From SDV
   await page.fill('input[name="phone"]', '555-1234567');           // From SDV
   ```

3. **Multiple test runs use different data:**
   - Each execution gets unique synthetic data
   - No hardcoded test data
   - Realistic variation

---

## 🚀 Quick Commands

### Start Backend
```powershell
cd backend
C:\Users\gparavasthu\Workspace\Truvelocity\code_export\agentic-sdlc-platform\venv\Scripts\python.exe -m uvicorn main:app --reload
```

### Run Tests
```powershell
cd backend
$env:Path = "$PWD\node_modules\.bin;$env:Path"
playwright test test_outputs/comprehensive_e2e_tests.spec.js --headed --workers=1
```

### View Test Report
```powershell
npx playwright show-report
```

---

## ✅ Validation Checklist

Before running, ensure:
- [ ] Backend is running: `http://localhost:8000/docs`
- [ ] @playwright/test installed: `npm list @playwright/test`
- [ ] Browsers installed: `npx playwright install`
- [ ] Python packages installed: `pip list | grep langgraph`
- [ ] Database initialized: `python init_db.py`

---

## 🐛 Troubleshooting

### Issue: "Cannot find module '@playwright/test'"
**Solution:**
```powershell
cd backend
npm install
npx playwright install
```

### Issue: "Test timeout"
**Solution:** Increase timeout in `playwright.config.ts`:
```typescript
timeout: 180000,  // 3 minutes
```

### Issue: "WinError 2: The system cannot find the file specified"
**Solution:** Fixed! Executor now uses correct PATH with `node_modules/.bin`

### Issue: "Selector not found"
**Solution:** Self-healing will automatically fix this, or adjust selectors in test file

---

## 📈 Expected Results

### All 3 tests should:
✅ Open in headed browser (visible)  
✅ Navigate to correct URLs  
✅ Perform actions with 500ms delay  
✅ Fill forms (with SDV data if enabled)  
✅ Take screenshots on failure  
✅ Generate detailed logs  
✅ Self-heal if selectors fail  

### Output:
```
Running 3 tests using 1 worker

  ✓  LG India - Search TV and Checkout (45s)
  ✓  Sauce Demo - Grey Shirt Checkout (32s)
  ✓  Hilti India - Rotary Hammer Purchase (28s)

  3 passed (1.8m)
```

---

## 🎯 Next Steps

1. **View browser execution in headed mode** ✅ (Running now)
2. **Check logs** in `backend/test_outputs/logs_*.txt`
3. **Review screenshots** in `backend/test-results/`
4. **Integrate with CI/CD** using `--headed=false` for headless execution
5. **Add more test cases** to `comprehensive_e2e_tests.spec.js`
6. **Enable SDV** for dynamic test data generation

---

## 📞 Support

- Backend API Docs: http://localhost:8000/docs
- Playwright Docs: https://playwright.dev
- Test Agents Docs: https://playwright.dev/docs/test-agents
- SDV Docs: https://docs.sdv.dev

---

**Status:** ✅ All fixes applied, tests running in headed mode!
