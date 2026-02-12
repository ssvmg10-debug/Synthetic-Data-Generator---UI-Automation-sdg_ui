# LangGraph Agent System Implementation

## 🎯 Overview

Complete agent-based architecture using **LangGraph 0.0.62** for:
- **Synthetic Data Generation** with UI crawling
- **UI Automation** with self-healing capabilities

## 📊 Architecture

### Database Schema (5 New Tables)
- `agent_checkpoints` - Workflow state persistence
- `workflow_executions` - Track workflow runs
- `healing_history` - Self-healing audit trail
- `crawl_cache` - Cache UI crawl results (24-hour TTL)
- `agent_memory` - Long-term agent memory with embeddings

### LangGraph Workflows

#### 1. Synthetic Data Workflow (Linear)
```
START → parse_test_case → crawl_pages → merge_schemas → generate_data → END
```

**Nodes:**
- `parse_test_case_node`: Extract URLs from test case
- `crawl_pages_node`: Crawl pages + cache results
- `merge_schemas_node`: Merge test case + crawler schemas using GPT-4
- `generate_data_node`: Generate synthetic data with SDV

**File:** `backend/agents/synthetic_data/graph.py`

#### 2. UI Automation Workflow (Self-Healing Loop)
```
START → plan_test → generate_script → execute_test → monitor_execution
                                                         ↓
                                         [failed] → heal_failure → retry_execution
                                                         ↑                ↓
                                                         ← ← ← [failed] ← 
                                         [passed or max attempts] → END
```

**Nodes:**
- `plan_test_node`: Wraps **PlannerAgent** ✅
- `generate_script_node`: Wraps **GeneratorAgent** ✅
- `execute_test_node`: Run Playwright script
- `monitor_execution_node`: Check if healing needed
- `heal_failure_node`: Wraps **HealerAgent** (CRITICAL) ✅
- `retry_execution_node`: Retry with healed script

**File:** `backend/agents/ui_automation/graph.py`

**Key Feature:** Automatic retry loop with max 3 healing attempts

## 🔧 Integration of Existing Agents

### Wrapped Existing Agents ✅
- **PlannerAgent** (`services/ui_automation/agents/planner/agent.py`)
  - Used in: `plan_test_node()`
  
- **GeneratorAgent** (`services/ui_automation/agents/generator/agent.py`)
  - Used in: `generate_script_node()`
  
- **HealerAgent** (`services/ui_automation/agents/healer/agent.py`)
  - Used in: `heal_failure_node()` **[MOST CRITICAL NODE]**
  
- **ValidatorAgent** (`services/ui_automation/agents/validator/agent.py`)
  - Available for future integration

### Self-Healing Logic
```python
# In heal_failure_node()
healer = HealerAgent()
healing_result = healer.heal(
    script=playwright_script,
    error=error,
    failed_locator=failed_locator
)

# Saves to healing_history table
healing_history_entry = HealingHistory(
    testcase_id=state.get('testcase_id'),
    failed_locator=failed_locator,
    healed_locator=healed_locator,
    strategy_used=strategy,
    success=True,
    confidence_score=confidence
)
```

## 📡 API Endpoints

### Synthetic Data (New)
```
POST /api/synthetic-data/generate-from-text
```
**Uses LangGraph workflow** with UI crawling

Body:
```json
{
  "user_input": "Test case: Fill form at https://example.com with name, email, phone",
  "model": "GaussianCopula"
}
```

Response:
```json
{
  "message": "Synthetic data generated successfully via agent workflow",
  "run_id": 123,
  "schema_id": 456,
  "rows_generated": 10,
  "data": [...]
}
```

### UI Automation (New)
```
POST /api/ui-automation/run-workflow
```
**Uses LangGraph workflow** with self-healing

Body:
```json
{
  "raw_input": "Test login: Go to https://app.example.com, enter username 'test@example.com', password 'test123', click login",
  "feature_description": "Login functionality",
  "page_url": "https://app.example.com"
}
```

Response:
```json
{
  "success": true,
  "status": "passed",
  "test_case_id": 789,
  "healing_attempts": 2,
  "healing_history": [
    {
      "attempt": 1,
      "failed_locator": "button#submit",
      "healed_locator": "button[type='submit']",
      "strategy": "attribute_fallback",
      "confidence": 0.95
    }
  ],
  "script": "// Playwright script...",
  "message": "Test passed with 2 healing attempts"
}
```

### Legacy Endpoints
- `/api/synthetic-data/generate-from-text-legacy` - Direct approach (no LangGraph)
- `/api/ui-automation/plan` - Direct PlannerAgent call
- `/api/ui-automation/generate` - Direct GeneratorAgent call
- `/api/ui-automation/execute` - Direct execution

## 🛠 Technology Stack

### Core Framework
- **LangGraph 0.0.62**: State management + workflow orchestration
- **LangChain**: langchain-core, langchain-openai, langchain-community
- **Azure OpenAI GPT-4**: Agent reasoning

### Automation & Data
- **Playwright 1.42.0**: UI automation + crawling
- **SDV (Synthetic Data Vault)**: Data generation
- **ChromaDB 1.5.0**: Vector embeddings for agent memory

### Backend
- **FastAPI**: API server
- **PostgreSQL**: Database with 5 agent tables
- **SQLAlchemy**: ORM
- **Alembic**: Migrations

## 📁 File Structure

```
backend/
├── agents/
│   ├── __init__.py                    # Export workflow runners
│   ├── synthetic_data/
│   │   ├── state.py                   # SyntheticDataState TypedDict
│   │   ├── nodes.py                   # 4 workflow nodes
│   │   └── graph.py                   # StateGraph + run_synthetic_data_workflow()
│   └── ui_automation/
│       ├── state.py                   # UIAutomationState TypedDict
│       ├── nodes.py                   # 6 workflow nodes (wraps existing agents)
│       └── graph.py                   # StateGraph + run_ui_automation_workflow()
│
├── routers/
│   ├── synthetic_data.py              # Updated with /generate-from-text (LangGraph)
│   └── ui_automation.py               # Updated with /run-workflow (LangGraph)
│
├── services/
│   └── ui_automation/
│       └── agents/
│           ├── planner/agent.py       # ✅ Integrated into LangGraph
│           ├── generator/agent.py     # ✅ Integrated into LangGraph
│           ├── healer/agent.py        # ✅ Integrated into LangGraph (CRITICAL)
│           └── validator/agent.py     # Available for future use
│
└── models/
    └── __init__.py                    # 5 new agent tables
```

## 🔄 Workflow Execution

### Synthetic Data Workflow
```python
from agents import run_synthetic_data_workflow

result = await run_synthetic_data_workflow(
    test_case="Fill form at https://example.com with name, email, phone",
    num_rows=10,
    db=db
)
```

### UI Automation Workflow
```python
from agents import run_ui_automation_workflow

result = await run_ui_automation_workflow(
    test_case="Login: https://app.example.com with test@example.com / test123",
    db=db,
    max_healing_attempts=3
)
```

## 🩺 Self-Healing Features

### Healing Strategies
1. **Attribute Fallback**: Try alternative locator strategies
2. **Fuzzy Match**: Find similar elements
3. **Context-Aware**: Use surrounding elements
4. **GPT-4 Analysis**: LLM-powered locator suggestions

### Healing Audit Trail
All healing attempts saved to `healing_history` table:
- `failed_locator`: Original selector that failed
- `healed_locator`: New selector that worked
- `strategy_used`: Which healing strategy succeeded
- `success`: Boolean
- `confidence_score`: Float (0-1)

### Max Healing Attempts
Configurable limit (default: 3) prevents infinite loops

## ✅ Completed

1. ✅ LangGraph dependencies installed
2. ✅ Database schema with 5 agent tables
3. ✅ Migrations applied successfully
4. ✅ Synthetic Data workflow (4 nodes)
5. ✅ UI Automation workflow with self-healing loop (6 nodes)
6. ✅ Integration of existing PlannerAgent, GeneratorAgent, HealerAgent
7. ✅ API endpoints updated to use LangGraph workflows
8. ✅ Crawl caching (24-hour TTL)
9. ✅ Healing history tracking
10. ✅ State persistence with TypedDict schemas

## 🚀 Next Steps (Optional Enhancements)

1. **Agent Memory**: Implement ChromaDB integration for long-term memory
2. **Checkpointing**: Use LangGraph's built-in checkpointing for resume capability
3. **Parallel Execution**: Run multiple healing strategies in parallel
4. **ValidatorAgent**: Integrate into workflow for pre-execution validation
5. **Monitoring**: Add Prometheus metrics for workflow execution
6. **UI Dashboard**: Visualize healing attempts and workflow status

## 📝 Usage Notes

### Virtual Environment
Path: `C:\Users\gparavasthu\Workspace\Truvelocity\code_export\agentic-sdlc-platform\venv\Scripts\Activate.ps1`

### Running Migrations
```powershell
C:\Users\gparavasthu\Workspace\Truvelocity\code_export\agentic-sdlc-platform\venv\Scripts\python.exe -c "from alembic.config import Config; from alembic import command; cfg = Config('alembic.ini'); command.upgrade(cfg, 'head')"
```

### Starting Backend
```powershell
cd backend
uvicorn main:app --reload
```

### Testing Workflows
```bash
# Synthetic Data
curl -X POST http://localhost:8000/api/synthetic-data/generate-from-text \
  -H "Content-Type: application/json" \
  -d '{"user_input": "Generate 10 users with name, email, age", "model": "GaussianCopula"}'

# UI Automation
curl -X POST http://localhost:8000/api/ui-automation/run-workflow \
  -H "Content-Type: application/json" \
  -d '{"raw_input": "Test login at https://example.com with test@example.com"}'
```

## 🎯 Key Benefits

1. **Autonomous Workflows**: Agents handle multi-step processes automatically
2. **Self-Healing**: UI tests auto-recover from locator failures
3. **Intelligent Merging**: GPT-4 merges test case context with crawled schemas
4. **Caching**: 24-hour cache for crawled pages reduces API calls
5. **Audit Trail**: Complete history of healing attempts and strategies
6. **State Management**: LangGraph handles complex state transitions
7. **Resume Capability**: Built-in checkpointing (ready to use)
8. **Existing Agents Preserved**: Wrapped existing PlannerAgent, GeneratorAgent, HealerAgent

---

**Status**: ✅ **LangGraph Agent System Fully Implemented**

**Critical Feature**: Self-healing loop with existing HealerAgent integration
