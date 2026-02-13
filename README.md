# Enterprise Test Automation Platform

A unified platform for synthetic data generation, UI automation, and API automation with AI-powered agents.

## 🏗️ Architecture

```
Backend (FastAPI) → localhost:8000
React (Vite) Frontend → localhost:5173
Database → PostgreSQL (production-ready)
AI Provider → Azure OpenAI (gpt-4.1)
```

### One Backend, Three Modules
- **Synthetic Data Generator**: Generate test data from UI/API schemas
- **UI Automation**: AI-powered UI testing with Playwright
- **API Automation**: Intelligent API testing and validation

## 📁 Project Structure

```
project-root/
├── backend/
│   ├── main.py                    # FastAPI entry point
│   ├── db.py                      # Database configuration
│   ├── routers/                   # API routers
│   │   ├── synthetic_data.py
│   │   ├── ui_automation.py
│   │   └── api_automation.py
│   ├── services/                  # Business logic
│   │   ├── synthetic/
│   │   │   ├── ui_schema/
│   │   │   ├── api_schema/
│   │   │   ├── unified_schema/
│   │   │   └── sdv_engine/
│   │   ├── ui_automation/
│   │   │   ├── agents/
│   │   │   └── engine/
│   │   └── api_automation/
│   │       ├── agents/
│   │       └── engine/
│   └── models/                    # Database models
│
├── frontend/                      # React (Vite) UI
│   ├── src/
│   │   ├── App.tsx
│   │   └── components/           # AgentChat, SyntheticResponseCard, etc.
│   ├── package.json
│   └── vite.config.ts
│
├── requirements.txt
├── setup.ps1
├── start_backend.ps1
├── start_frontend.ps1
├── start_all.ps1                 # Start backend + frontend
└── RUN.md                        # Run commands (see this file)
```

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- PostgreSQL 12+ installed and running
- Azure OpenAI access

### 1. Environment Setup

Create a `.env` file in the project root:

```env
# PostgreSQL Database
DATABASE_URL=postgresql://postgres:12345@localhost:5432/qea

# Azure OpenAI Configuration
AZURE_API_KEY=your_azure_api_key_here
AZURE_ENDPOINT=https://your-endpoint.cognitiveservices.azure.com/
AZURE_DEPLOYMENT=gpt-4.1
AZURE_API_VERSION=2024-02-15-preview
```

### 2. Initial Setup (One-time)

```powershell
# Run setup script
.\setup.ps1

# Setup database with Alembic migrations
.\setup_database.ps1
```

The `setup_database.ps1` script will:
- Verify PostgreSQL connection
- Generate Alembic migrations
- Create all database tables
- Verify setup completion

### 3. Start Backend and Frontend

**Option A – Start both (recommended):**

```powershell
.\start_all.ps1
```

Opens backend (port 8000) and React UI (port 5173). Open **http://localhost:5173** in your browser.

**Option B – Start separately:**

```powershell
# Terminal 1 – Backend
.\start_backend.ps1

# Terminal 2 – Frontend (React)
.\start_frontend.ps1
```

- Backend: **http://localhost:8000** (API docs: http://localhost:8000/docs)
- Frontend: **http://localhost:5173**

See **[RUN.md](RUN.md)** for full run options and manual commands.

### 4. UI Automation: Playwright & in-app live view

For UI automation, install Playwright and browsers from the **backend** directory:

```powershell
cd backend
npm install @playwright/test
npx playwright install
```

Then run LG India test cases (25 end-to-end flows) from the project root:

```powershell
python run_lg_test_cases.py --list
python run_lg_test_cases.py --id lg_01_buy_tv_under_30k
```

The **in-app live view** (screenshots during a run) works when backend and frontend are running and the Vite proxy targets the backend. No CDP is required. See **[docs/LG_UI_AUTOMATION_AND_LIVE_VIEW.md](docs/LG_UI_AUTOMATION_AND_LIVE_VIEW.md)** for details and for stopping long-running UI/crawler processes (`scripts/stop_long_running_ui_processes.ps1`).

## 📚 Features

### 🧬 Synthetic Data Generator
- Extract schemas from UI forms (HTML parsing)
- Extract schemas from API specs (OpenAPI/Swagger)
- Merge UI and API schemas
- Generate realistic test data using SDV models
- Export data as CSV/JSON

### 🎭 UI Automation
- Natural language test case input
- AI-powered test planning
- Playwright script generation
- Self-healing selectors
- Automatic screenshots and logs
- Integration with synthetic data

### 🌐 API Automation
- Natural language API test description
- Intelligent request generation
- Response validation
- Schema-based testing
- Synthetic data for payloads

## 🗄️ Database Schema

PostgreSQL database with 9 tables managed by Alembic:
- **schemas**: UI/API schema definitions
- **synthetic_runs**: Data generation execution history
- **synthetic_data**: Generated test data records
- **ui_test_cases**: UI automation test definitions
- **locator_registry**: Element locator cache for self-healing
- **ui_execution_runs**: UI test execution history
- **api_test_cases**: API test definitions
- **api_schema_cache**: Cached API specifications
- **api_execution_runs**: API test execution history

### Database Migrations

```powershell
# Generate new migration after model changes
.\generate_migration.ps1 "Description of changes"

# Apply migrations
.\migrate_db.ps1

# View migration history
cd backend
alembic history

# Rollback one migration
alembic downgrade -1
```
- API automation (test cases, executions, schema cache)

## 🔧 API Endpoints

### Synthetic Data
- `POST /synthetic/ui-schema` - Extract UI schema
- `POST /synthetic/api-schema` - Extract API schema
- `POST /synthetic/merge-schema` - Merge schemas
- `POST /synthetic/generate` - Generate synthetic data
- `GET /synthetic/runs/{run_id}` - Get run details

### UI Automation
- `POST /ui/run` - Run full UI test
- `GET /ui/results/{execution_id}` - Get test results
- `GET /ui/locators` - Get locator registry

### API Automation
- `POST /api/run` - Run full API test
- `GET /api/results/{execution_id}` - Get test results
- `GET /api/schema-cache` - Get schema cache

## 🧪 Example Usage

### Synthetic Data Generation
1. Navigate to Synthetic Data page
2. Define or extract schema
3. Choose number of rows and model
4. Generate and download data

### UI Test Automation
1. Navigate to UI Automation page
2. Describe test in plain English
3. Optionally use synthetic data
4. Run test and view results

### API Test Automation
1. Navigate to API Automation page
2. Describe API test
3. Optionally use synthetic data
4. Run test and view response

## 📝 Dependencies

### Backend
- FastAPI - Web framework
- SQLAlchemy - Database ORM
- BeautifulSoup - HTML parsing
- httpx - HTTP client
- Faker - Data generation

### Frontend
- Streamlit - UI framework
- pandas - Data manipulation
- requests - HTTP client

### Optional
- Playwright - Browser automation
- SDV - Advanced synthetic data
- OpenAI - LLM enhancements

## 🛠️ Development

### Adding New Features

1. **Backend**: Add service in `backend/services/`
2. **Router**: Add endpoint in `backend/routers/`
3. **Frontend**: Add page in `streamlit_ui/pages/`
4. **Client**: Add method in `backend_client.py`

### Database Migrations

```python
# In backend directory
from db import init_db
init_db()
```

## 📦 Deployment

### Local
Use provided PowerShell scripts

### Production
1. Use production WSGI server (Gunicorn)
2. Switch to PostgreSQL
3. Add authentication
4. Enable HTTPS
5. Use environment variables for config

## 🤝 Contributing

1. Create feature branch
2. Implement changes
3. Test thoroughly
4. Submit pull request

## 📄 License

Internal enterprise use only

## 🆘 Support

For issues or questions, contact the development team.

---

**Version**: 1.0.0  
**Last Updated**: February 2026  
**Maintainer**: Enterprise QE Team
