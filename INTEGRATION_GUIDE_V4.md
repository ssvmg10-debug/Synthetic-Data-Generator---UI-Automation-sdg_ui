# Quick Integration Guide - Adding v4 Endpoint

## Step 1: Locate the File

Open: `backend/routers/ui_automation.py`

## Step 2: Find the Insertion Point

Search for: `@router.get("/enterprise-v3/metrics/`

Insert the new endpoint **BEFORE** this line (around line 1300).

## Step 3: Add the Endpoint

Copy the entire content from `backend/ADD_THIS_TO_ROUTER.py` and paste it.

## Step 4: Verify Imports

Make sure these imports exist at the top of `ui_automation.py`:

```python
from services.ui_automation.enterprise_flow_engine import EnterpriseFlowEngine, EnterpriseFlowResult
```

(This should already be there from v3)

## Step 5: Test the Endpoint

### Option A: Using curl

```bash
curl -X POST http://localhost:8004/api/ui-automation/run-enterprise-v4 \
  -H "Content-Type: application/json" \
  -d '{
    "raw_input": "navigate to https://www.lg.com/in\nclick on air solutions",
    "visible_browser": true
  }'
```

### Option B: Using test script

```bash
cd backend
python test_enterprise_v4.py
```

## Step 6: Verify Response

Expected response structure:

```json
{
  "test_case_id": 123,
  "result": {
    "status": "passed",
    "error": null,
    "steps_executed": 3,
    "instruction_mode": true,
    "instructions_compiled": 3,
    "health_score": 1.0,
    "execution_time": 8.5,
    "screenshots": [...],
    "screenshot_path": "...",
    "logs_path": "..."
  },
  "features": [
    "Instruction Compiler",
    "Deterministic DOM Targeting",
    "Strict Step Execution",
    "Controlled Recovery",
    "State Verification"
  ]
}
```

## Alternative: Use Existing Endpoint

If you don't want to add a new endpoint, the existing `/run` endpoint already uses v4 when you set `use_enterprise_v3: true`:

```bash
curl -X POST http://localhost:8004/api/ui-automation/run \
  -H "Content-Type: application/json" \
  -d '{
    "raw_input": "navigate to https://www.lg.com/in\nclick on air solutions",
    "use_enterprise_v3": true,
    "visible_browser": true
  }'
```

The response will include `enterprise_v4: true` field.

## Troubleshooting

### Import Error
If you get import errors, verify:
```python
from services.ui_automation.instruction_compiler import InstructionCompiler
from services.ui_automation.intent_engine_v2 import EnterpriseIntentEngine
```

These files should exist:
- `backend/services/ui_automation/instruction_compiler.py`
- `backend/services/ui_automation/intent_engine_v2.py`

### Endpoint Not Found
Restart the backend:
```bash
cd backend
python run_uvicorn.py
```

### Module Not Found
Check your Python path includes the backend directory.

## Success Indicators

✅ Endpoint responds (no 404)  
✅ Response has `instruction_mode: true`  
✅ Response has `instructions_compiled > 0`  
✅ Logs show "INSTRUCTION MODE"  
✅ No random exploration in logs  

## Done!

Your v4 architecture is now fully integrated and ready to use.

Try the LG India test case and watch it execute deterministically!
