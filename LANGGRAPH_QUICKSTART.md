# LangGraph Agent System - Quick Start Guide

## 🚀 Overview

This system uses **LangGraph** to orchestrate intelligent agent workflows for:
1. **Synthetic Data Generation** - Automatically crawls pages and generates test data
2. **UI Test Automation** - Self-healing Playwright tests with autonomous recovery

## 📋 Prerequisites

- Python 3.12+
- PostgreSQL database
- Azure OpenAI API access
- Virtual environment activated

## ⚡ Quick Start

### 1. Activate Virtual Environment
```powershell
C:\Users\gparavasthu\Workspace\Truvelocity\code_export\agentic-sdlc-platform\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies (if not already done)
```bash
cd backend
pip install -r requirements.txt
```

### 3. Run Database Migrations
```powershell
cd backend
python -c "from alembic.config import Config; from alembic import command; cfg = Config('alembic.ini'); command.upgrade(cfg, 'head')"
```

This creates 5 new agent tables:
- `agent_checkpoints` - Workflow state
- `workflow_executions` - Execution tracking
- `healing_history` - Self-healing audit
- `crawl_cache` - Page crawl cache
- `agent_memory` - Agent memory

### 4. Start Backend Server
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Test the Workflows

#### Option A: Using curl

**Synthetic Data Generation:**
```bash
curl -X POST http://localhost:8000/api/synthetic-data/generate-from-text \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "Generate 10 test users for the registration form at https://example.com/register. Include name, email, phone, age, and address.",
    "model": "GaussianCopula"
  }'
```

**UI Automation with Self-Healing:**
```bash
curl -X POST http://localhost:8000/api/ui-automation/run-workflow \
  -H "Content-Type: application/json" \
  -d '{
    "raw_input": "Test login at https://practicetestautomation.com/practice-test-login/ with username: student, password: Password123. Click login and verify success."
  }'
```

#### Option B: Using Python Test Script
```bash
python test_langgraph_workflows.py
```

#### Option C: Using Streamlit UI
```bash
# Terminal 1: Backend
cd backend
uvicorn main:app --reload

# Terminal 2: Streamlit
cd streamlit_ui
streamlit run Home.py
```

Then navigate to:
- **Synthetic Data**: http://localhost:8501/SyntheticData
- **UI Automation**: http://localhost:8501/UIAutomation

## 🔧 How It Works

### Synthetic Data Workflow (Automatic)
```
User Input → Parse URLs → Crawl Pages → Merge Schemas → Generate Data
```

**Example:**
```
Input: "Fill form at https://example.com with name, email, phone"
↓
Workflow extracts URL → Crawls page → Detects form fields → Generates 10 rows
```

### UI Automation Workflow (Self-Healing)
```
Test Case → Plan → Generate Script → Execute
                                      ↓
                      [Failed?] → Heal → Retry (max 3x)
                                      ↓
                                  [Success!]
```

**Example:**
```
Input: "Login at https://example.com with test@test.com"
↓
Plan created → Playwright script generated → Execution fails (locator wrong)
↓
HealerAgent fixes locator → Retry → Success!
```

## 📊 API Endpoints

### Synthetic Data

#### POST `/api/synthetic-data/generate-from-text`
**New LangGraph workflow endpoint**

Request:
```json
{
  "user_input": "Generate 5 customer records with name, email, phone, company",
  "model": "GaussianCopula"
}
```

Response:
```json
{
  "message": "Synthetic data generated successfully via agent workflow",
  "run_id": 123,
  "schema_id": 456,
  "rows_generated": 5,
  "data": [
    {"name": "John Doe", "email": "john@example.com", ...},
    ...
  ]
}
```

### UI Automation

#### POST `/api/ui-automation/run-workflow`
**New LangGraph workflow with self-healing**

Request:
```json
{
  "raw_input": "Test search: Go to https://google.com, search for 'LangGraph', click first result"
}
```

OR

```json
{
  "feature_description": "Search functionality test",
  "page_url": "https://google.com"
}
```

Response (Success):
```json
{
  "success": true,
  "status": "passed",
  "test_case_id": 789,
  "healing_attempts": 1,
  "healing_history": [
    {
      "attempt": 1,
      "failed_locator": "input[name='q']",
      "healed_locator": "input[title='Search']",
      "strategy": "attribute_fallback",
      "confidence": 0.95
    }
  ],
  "script": "// Generated Playwright script...",
  "message": "Test passed with 1 healing attempts"
}
```

Response (Failed):
```json
{
  "success": false,
  "status": "failed",
  "error": "Element not found after 3 healing attempts",
  "healing_attempts": 3,
  "healing_history": [...]
}
```

## 🩺 Self-Healing Features

### How It Works
1. **Execution Fails** - Playwright can't find an element
2. **Extract Locator** - Identify which selector failed
3. **Heal** - HealerAgent generates alternative locators using:
   - Attribute fallback (id → class → text → xpath)
   - Fuzzy matching
   - Context-aware search
   - GPT-4 analysis
4. **Retry** - Execute with healed script
5. **Repeat** - Max 3 healing attempts

### Healing Audit Trail
All attempts saved to database:
```sql
SELECT * FROM healing_history WHERE testcase_id = 789;
```

Result:
```
| failed_locator       | healed_locator      | strategy          | success | confidence |
|---------------------|---------------------|-------------------|---------|------------|
| button#submit       | button[type='submit'] | attribute_fallback | true    | 0.95       |
```

## 📁 Key Files

```
backend/
├── agents/
│   ├── synthetic_data/
│   │   ├── nodes.py        # 4 workflow nodes
│   │   └── graph.py        # StateGraph definition
│   └── ui_automation/
│       ├── nodes.py        # 6 workflow nodes (wraps existing agents)
│       └── graph.py        # StateGraph with healing loop
│
├── routers/
│   ├── synthetic_data.py   # /generate-from-text endpoint
│   └── ui_automation.py    # /run-workflow endpoint
│
└── services/
    └── ui_automation/
        └── agents/
            ├── planner/    # ✅ Integrated
            ├── generator/  # ✅ Integrated
            └── healer/     # ✅ Integrated (CRITICAL)
```

## 🔍 Debugging

### Check Workflow Status
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db import DATABASE_URL
from models import WorkflowExecution

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
db = Session()

# Get latest workflow
workflow = db.query(WorkflowExecution).order_by(WorkflowExecution.created_at.desc()).first()
print(f"Status: {workflow.status}")
print(f"Current Node: {workflow.current_node}")
print(f"Result: {workflow.result_json}")
```

### Check Healing History
```python
from models import HealingHistory

healing_events = db.query(HealingHistory).filter(
    HealingHistory.testcase_id == 789
).all()

for event in healing_events:
    print(f"Failed: {event.failed_locator}")
    print(f"Healed: {event.healed_locator}")
    print(f"Strategy: {event.strategy_used}")
    print(f"Success: {event.success}")
    print(f"Confidence: {event.confidence_score}")
    print("---")
```

### View Logs
```bash
# Backend logs
tail -f backend/logs/app.log

# Look for:
# 🔹 NODE 1: PARSE TEST CASE
# 🔹 NODE 2: CRAWL PAGES
# 🔹 NODE 5: HEAL FAILURE (SELF-HEALING)
```

## 🎯 Example Use Cases

### Use Case 1: E-commerce Testing
```bash
curl -X POST http://localhost:8000/api/ui-automation/run-workflow \
  -H "Content-Type: application/json" \
  -d '{
    "raw_input": "Test checkout: Go to https://shop.example.com, add product to cart, click checkout, fill shipping details, click place order"
  }'
```

The workflow will:
1. Plan the test steps
2. Generate Playwright script
3. Execute the test
4. **If any locator fails** → Heal automatically → Retry
5. Return final status with healing history

### Use Case 2: Form Testing with Synthetic Data
```bash
# Step 1: Generate test data
curl -X POST http://localhost:8000/api/synthetic-data/generate-from-text \
  -H "Content-Type: application/json" \
  -d '{
    "user_input": "Generate 5 customer records for the form at https://shop.example.com/register with name, email, phone, address"
  }'

# Response: { "run_id": 123, "data": [...] }

# Step 2: Use generated data in UI test
curl -X POST http://localhost:8000/api/ui-automation/run-workflow \
  -H "Content-Type: application/json" \
  -d '{
    "raw_input": "Fill registration form at https://shop.example.com/register",
    "use_synthetic_data": true,
    "synthetic_run_id": 123
  }'
```

## 📈 Monitoring

### Workflow Metrics
```sql
-- Successful workflows
SELECT COUNT(*) FROM workflow_executions WHERE status = 'completed';

-- Average healing attempts
SELECT AVG(healing_attempts) FROM ui_testcases WHERE status = 'passed';

-- Most common healing strategies
SELECT strategy_used, COUNT(*) as count 
FROM healing_history 
WHERE success = true 
GROUP BY strategy_used 
ORDER BY count DESC;
```

## 🛠 Troubleshooting

### Issue: "No module named 'langgraph'"
**Solution:**
```bash
pip install langgraph langchain langchain-openai langchain-community chromadb playwright
```

### Issue: "Table agent_checkpoints does not exist"
**Solution:**
```bash
cd backend
python -c "from alembic.config import Config; from alembic import command; cfg = Config('alembic.ini'); command.upgrade(cfg, 'head')"
```

### Issue: "Azure OpenAI API error"
**Solution:**
Check environment variables in `config.json`:
```json
{
  "AZURE_OPENAI_API_KEY": "your-key",
  "AZURE_OPENAI_ENDPOINT": "https://your-resource.openai.azure.com/",
  "AZURE_OPENAI_DEPLOYMENT": "gpt-4"
}
```

### Issue: "Playwright browser not installed"
**Solution:**
```bash
playwright install chromium
```

## 🎓 Next Steps

1. **Customize Healing Strategies**: Edit `backend/services/ui_automation/agents/healer/agent.py`
2. **Add Validation**: Integrate ValidatorAgent into workflow
3. **Enable Checkpointing**: Use LangGraph's built-in checkpoint feature for resume
4. **Add Memory**: Implement ChromaDB for agent long-term memory
5. **Monitor**: Set up Prometheus metrics

## 📚 Documentation

- [Full Implementation Guide](LANGGRAPH_IMPLEMENTATION.md)
- [Architecture Overview](ARCHITECTURE.md)
- [Testing Guide](TESTING_GUIDE.md)

---

**Status**: ✅ **System Ready**

For support, check logs and healing_history table for debugging self-healing issues.
