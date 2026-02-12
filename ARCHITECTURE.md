# ARCHITECTURE DIAGRAM
# Enterprise Test Automation Platform

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                    ENTERPRISE TEST AUTOMATION PLATFORM                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Port 8501)                                │
│                         Streamlit Application                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Home.py    │  │ Synthetic    │  │     UI       │  │     API      │  │
│  │              │  │   Data.py    │  │Automation.py │  │Automation.py │  │
│  │  - Welcome   │  │              │  │              │  │              │  │
│  │  - Nav       │  │  - Extract   │  │  - Test      │  │  - Test      │  │
│  │  - Health    │  │  - Merge     │  │    Case      │  │    Case      │  │
│  │              │  │  - Generate  │  │  - Execute   │  │  - Execute   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                     Backend Client (HTTP)                             │ │
│  │  - Health Check  - Synthetic Data APIs  - UI APIs  - API APIs       │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 │ HTTP Requests
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BACKEND (Port 8000)                                 │
│                         FastAPI Application                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                           main.py                                     │ │
│  │  - FastAPI App  - CORS Middleware  - Router Registration            │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │
│  │  Synthetic Data  │  │  UI Automation   │  │  API Automation  │        │
│  │     Router       │  │     Router       │  │     Router       │        │
│  │                  │  │                  │  │                  │        │
│  │  6 Endpoints:    │  │  7 Endpoints:    │  │  6 Endpoints:    │        │
│  │  - ui-schema     │  │  - plan          │  │  - plan          │        │
│  │  - api-schema    │  │  - generate      │  │  - generate      │        │
│  │  - merge-schema  │  │  - validate      │  │  - execute       │        │
│  │  - generate      │  │  - execute       │  │  - run           │        │
│  │  - runs/{id}     │  │  - run           │  │  - results/{id}  │        │
│  │                  │  │  - results/{id}  │  │  - schema-cache  │        │
│  │                  │  │  - locators      │  │                  │        │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘        │
│           │                     │                      │                   │
│           ▼                     ▼                      ▼                   │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                          SERVICES LAYER                             │  │
│  ├─────────────────────────────────────────────────────────────────────┤  │
│  │                                                                     │  │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐  │  │
│  │  │  Synthetic Data  │  │  UI Automation   │  │ API Automation │  │  │
│  │  │    Services      │  │    Services      │  │   Services     │  │  │
│  │  ├──────────────────┤  ├──────────────────┤  ├────────────────┤  │  │
│  │  │ UI Schema        │  │ Agents:          │  │ Agents:        │  │  │
│  │  │  - Extractor     │  │  - Planner       │  │  - Planner     │  │  │
│  │  │                  │  │  - Generator     │  │  - Generator   │  │  │
│  │  │ API Schema       │  │  - Validator     │  │                │  │  │
│  │  │  - Extractor     │  │  - Healer        │  │ Engine:        │  │  │
│  │  │                  │  │                  │  │  - Executor    │  │  │
│  │  │ Unified Schema   │  │ Engine:          │  │  - Validator   │  │  │
│  │  │  - Merger        │  │  - Playwright    │  │                │  │  │
│  │  │                  │  │    Executor      │  │                │  │  │
│  │  │ SDV Engine       │  │                  │  │                │  │  │
│  │  │  - Generator     │  │                  │  │                │  │  │
│  │  └──────────────────┘  └──────────────────┘  └────────────────┘  │  │
│  │                                                                     │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                         DATABASE LAYER                                │ │
│  │                         SQLAlchemy ORM                                │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                │                                            │
└────────────────────────────────┼────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATABASE (SQLite)                                   │
│                  enterprise_automation.db                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │
│  │  Synthetic Data  │  │  UI Automation   │  │  API Automation  │        │
│  │     Tables       │  │     Tables       │  │     Tables       │        │
│  ├──────────────────┤  ├──────────────────┤  ├──────────────────┤        │
│  │ - schemas        │  │ - ui_testcases   │  │ - api_testcases  │        │
│  │ - synthetic_runs │  │ - locator_       │  │ - api_schema_    │        │
│  │ - synthetic_data │  │   registry       │  │   cache          │        │
│  │                  │  │ - ui_execution_  │  │ - api_execution_ │        │
│  │                  │  │   runs           │  │   runs           │        │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                            DATA FLOW EXAMPLES                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  FLOW 1: Synthetic Data Generation                                         │
│  ────────────────────────────────────                                      │
│  User → Streamlit → Backend API → UI Schema Extractor                      │
│                                  → API Schema Extractor                     │
│                                  → Schema Merger                            │
│                                  → SDV Generator                            │
│                                  → Database (Save)                          │
│                                  → Return Data → Streamlit → User          │
│                                                                             │
│  FLOW 2: UI Test Automation                                                │
│  ────────────────────────────                                              │
│  User → Streamlit → Backend API → Planner Agent (Parse)                    │
│                                  → Generator Agent (Script)                 │
│                                  → Validator Agent (Check)                  │
│                                  → Executor (Playwright)                    │
│                                  → Healer Agent (If failed)                 │
│                                  → Database (Save Results)                  │
│                                  → Return Results → Streamlit → User       │
│                                                                             │
│  FLOW 3: API Test Automation                                               │
│  ─────────────────────────────                                             │
│  User → Streamlit → Backend API → Planner Agent (Parse)                    │
│                                  → Generator Agent (Request)                │
│                                  → Executor (HTTP Call)                     │
│                                  → Validator (Response Check)               │
│                                  → Database (Save Results)                  │
│                                  → Return Results → Streamlit → User       │
│                                                                             │
│  FLOW 4: Integrated Flow (Synthetic Data + UI Test)                        │
│  ─────────────────────────────────────────────────                         │
│  User → Generate Synthetic Data → Store in DB (run_id)                     │
│       → Create UI Test Case                                                │
│       → Enable Synthetic Data (use run_id)                                 │
│       → Backend fetches synthetic data from DB                             │
│       → Injects data into test script                                      │
│       → Executes test with data                                            │
│       → Returns results to user                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                          DEPLOYMENT ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌────────────────┐          ┌────────────────┐                           │
│  │   Terminal 1   │          │   Terminal 2   │                           │
│  │                │          │                │                           │
│  │  Activate venv │          │  Activate venv │                           │
│  │       ↓        │          │       ↓        │                           │
│  │  cd backend    │          │  streamlit run │                           │
│  │       ↓        │          │  Home.py       │                           │
│  │  python main.py│          │                │                           │
│  │       ↓        │          │       ↓        │                           │
│  │  FastAPI       │          │  Streamlit     │                           │
│  │  Port 8000     │◄────────►│  Port 8501     │                           │
│  │                │   HTTP   │                │                           │
│  └────────┬───────┘          └────────┬───────┘                           │
│           │                           │                                    │
│           │                           │                                    │
│           └───────────┬───────────────┘                                    │
│                       ↓                                                    │
│              ┌──────────────────┐                                         │
│              │  SQLite Database │                                         │
│              │  (Single File)   │                                         │
│              └──────────────────┘                                         │
│                                                                             │
│  Access Points:                                                            │
│  - Backend API: http://localhost:8000                                      │
│  - API Docs: http://localhost:8000/docs                                    │
│  - Frontend: http://localhost:8501                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                           TECHNOLOGY STACK                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Backend Technologies:                                                      │
│  ├─ FastAPI 0.109.0        - Web framework                                │
│  ├─ SQLAlchemy 2.0         - ORM                                          │
│  ├─ Pydantic              - Data validation                               │
│  ├─ httpx                 - HTTP client                                   │
│  ├─ BeautifulSoup4        - HTML parsing                                  │
│  ├─ Faker                 - Test data generation                          │
│  └─ uvicorn               - ASGI server                                   │
│                                                                             │
│  Frontend Technologies:                                                     │
│  ├─ Streamlit 1.30        - UI framework                                  │
│  ├─ pandas                - Data manipulation                             │
│  ├─ requests              - HTTP client                                   │
│  └─ matplotlib (optional) - Visualization                                 │
│                                                                             │
│  Database:                                                                  │
│  └─ SQLite                - Embedded database                             │
│                                                                             │
│  Optional:                                                                  │
│  ├─ Playwright            - Browser automation                            │
│  ├─ SDV                   - Advanced synthetic data                       │
│  └─ OpenAI API            - LLM enhancements                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                           KEY DESIGN PRINCIPLES                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. SIMPLICITY                                                             │
│     - Single backend process                                               │
│     - Single frontend process                                              │
│     - No containers required                                               │
│     - No message queues                                                    │
│                                                                             │
│  2. MODULARITY                                                             │
│     - Three independent modules                                            │
│     - Separate routers                                                     │
│     - Isolated services                                                    │
│     - Clean interfaces                                                     │
│                                                                             │
│  3. INTEGRATION                                                            │
│     - Modules can work together                                            │
│     - Shared database                                                      │
│     - Unified API                                                          │
│     - Cross-module data flow                                               │
│                                                                             │
│  4. EXTENSIBILITY                                                          │
│     - Easy to add new agents                                               │
│     - Pluggable services                                                   │
│     - Configurable behavior                                                │
│     - Open for enhancement                                                 │
│                                                                             │
│  5. PRODUCTION-READY                                                       │
│     - Error handling                                                       │
│     - Data persistence                                                     │
│     - API documentation                                                    │
│     - Logging support                                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Quick Reference

### Start Commands
```powershell
# Terminal 1 - Backend
cd backend && python main.py

# Terminal 2 - Frontend
streamlit run streamlit_ui/Home.py
```

### Access URLs
- Frontend: http://localhost:8501
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Module Overview
- **Synthetic Data**: Generate realistic test data
- **UI Automation**: Automate browser testing
- **API Automation**: Automate API testing
