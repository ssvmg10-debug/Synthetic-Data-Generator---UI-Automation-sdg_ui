# PostgreSQL & Azure OpenAI Integration - Summary

## Changes Made

This document summarizes all changes made to migrate from SQLite to PostgreSQL and integrate Azure OpenAI.

## 1. Environment Configuration

### Created: `.env`
**Purpose:** Store sensitive configuration and credentials

**Contents:**
- `DATABASE_URL`: PostgreSQL connection string
- `AZURE_API_KEY`: Azure OpenAI API key
- `AZURE_ENDPOINT`: Azure OpenAI endpoint URL
- `AZURE_DEPLOYMENT`: GPT model deployment name (gpt-4.1)
- `AZURE_API_VERSION`: API version

**Example:**
```env
DATABASE_URL=postgresql://postgres:12345@localhost:5432/qea
AZURE_API_KEY=your_key_here
AZURE_ENDPOINT=https://your-endpoint.cognitiveservices.azure.com/
AZURE_DEPLOYMENT=gpt-4.1
AZURE_API_VERSION=2024-02-15-preview
```

## 2. Database Configuration

### Modified: `backend/db.py`
**Changes:**
- ✅ Replaced SQLite with PostgreSQL connection
- ✅ Added `python-dotenv` for environment variable loading
- ✅ Added connection pooling configuration:
  - `pool_size=10`: Maintain 10 connections
  - `max_overflow=20`: Allow up to 30 total connections
  - `pool_pre_ping=True`: Verify connections before use
  - `pool_recycle=3600`: Recycle connections hourly

**Before:**
```python
SQLALCHEMY_DATABASE_URL = "sqlite:///./enterprise_automation.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)
```

**After:**
```python
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600
)
```

### Modified: `requirements.txt`
**Added Dependencies:**
- `psycopg2-binary==2.9.9`: PostgreSQL adapter
- `alembic==1.13.1`: Database migrations
- `python-dotenv==1.0.0`: Environment variables
- `openai==1.10.0`: Azure OpenAI client

## 3. Database Migrations (Alembic)

### Created: `backend/alembic.ini`
Alembic configuration file with PostgreSQL connection settings.

### Created: `backend/alembic/env.py`
Migration environment setup that:
- Loads `.env` variables
- Imports SQLAlchemy models
- Configures migration context
- Supports both online and offline migrations

### Created: `backend/alembic/script.py.mako`
Template for generating migration files.

### Created: `backend/alembic/versions/`
Directory for migration scripts (populated when migrations are generated).

### Modified: `backend/init_db.py`
Updated to warn users to use Alembic migrations instead of direct table creation.

## 4. Azure OpenAI Integration

### Created: `backend/utils/azure_openai.py`
**Purpose:** Unified interface for Azure OpenAI API calls

**Features:**
- `chat_completion()`: Send chat requests
- `json_completion()`: Get JSON-formatted responses
- `create_system_message()`: Helper for system prompts
- `create_user_message()`: Helper for user prompts
- `create_assistant_message()`: Helper for assistant responses
- Automatic configuration verification

**Usage Example:**
```python
from utils.azure_openai import chat_completion, create_system_message, create_user_message

messages = [
    create_system_message("You are a test automation expert."),
    create_user_message("Generate a test plan for login page")
]

response = chat_completion(messages, temperature=0.7)
```

## 5. PowerShell Scripts

### Created: `create_database.ps1`
**Purpose:** Create PostgreSQL database

**Features:**
- Parse DATABASE_URL from `.env`
- Test PostgreSQL connection
- Create database if it doesn't exist
- Prompt before dropping existing database

### Created: `setup_database.ps1`
**Purpose:** Generate and apply initial migrations

**Features:**
- Verify `.env` exists
- Test database connection
- Generate Alembic migrations
- Create all tables
- Display success summary

### Created: `generate_migration.ps1`
**Purpose:** Create new migration after model changes

**Usage:**
```powershell
.\generate_migration.ps1 "Description of changes"
```

### Created: `migrate_db.ps1`
**Purpose:** Apply pending migrations

**Usage:**
```powershell
.\migrate_db.ps1
```

## 6. Documentation

### Created: `docs/POSTGRESQL_SETUP.md`
**Contents:**
- PostgreSQL installation guide
- Database creation steps
- Connection string format
- Migration commands
- Backup and restore procedures
- Performance tuning tips
- Troubleshooting guide
- Security best practices

### Created: `docs/AZURE_OPENAI_GUIDE.md`
**Contents:**
- Azure OpenAI configuration
- Getting credentials
- Usage examples
- AI agent integration patterns
- Best practices
- Error handling
- Token management
- Cost estimation
- Troubleshooting

### Created: `docs/MIGRATION_GUIDE.md`
**Contents:**
- Quick start guide
- Detailed migration workflow
- Script reference
- Troubleshooting
- Manual migration commands
- CI/CD integration
- Best practices

### Updated: `README.md`
**Changes:**
- Updated architecture section (PostgreSQL + Azure OpenAI)
- Added prerequisites (PostgreSQL, Azure OpenAI)
- Updated quick start with `.env` setup
- Added database migration steps
- Updated database schema section
- Added migration command reference

## 7. Database Schema

**9 Tables Created by Migration:**

1. **schemas** - UI/API schema definitions
2. **synthetic_runs** - Data generation execution history
3. **synthetic_data** - Generated test data records
4. **ui_test_cases** - UI automation test definitions
5. **locator_registry** - Element locator cache for self-healing
6. **ui_execution_runs** - UI test execution history
7. **api_test_cases** - API test definitions
8. **api_schema_cache** - Cached API specifications
9. **api_execution_runs** - API test execution history

## Setup Workflow

### For New Installation:

```powershell
# 1. Create .env file with credentials
# DATABASE_URL, AZURE_API_KEY, etc.

# 2. Install dependencies
.\setup.ps1

# 3. Create PostgreSQL database
.\create_database.ps1

# 4. Run migrations to create tables
.\setup_database.ps1

# 5. Start backend
.\start_backend.ps1

# 6. Start frontend (new terminal)
.\start_streamlit.ps1
```

### For Schema Changes:

```powershell
# 1. Modify models in backend/models/__init__.py

# 2. Generate migration
.\generate_migration.ps1 "Description of changes"

# 3. Review migration file in backend/alembic/versions/

# 4. Apply migration
.\migrate_db.ps1
```

## Benefits of Changes

### PostgreSQL Benefits:
- ✅ Production-ready reliability
- ✅ ACID compliance
- ✅ Better concurrent access
- ✅ Advanced features (JSON columns, full-text search)
- ✅ Horizontal scalability
- ✅ Better performance for large datasets

### Alembic Benefits:
- ✅ Version-controlled schema changes
- ✅ Easy rollback capability
- ✅ Track migration history
- ✅ Automated migration generation
- ✅ Safe collaborative development

### Azure OpenAI Benefits:
- ✅ Enterprise-grade AI capabilities
- ✅ GPT-4 for intelligent test generation
- ✅ Self-healing test scripts
- ✅ Natural language test planning
- ✅ Automated test case generation
- ✅ Smart validation and assertions

### Environment Variables Benefits:
- ✅ Keep secrets out of code
- ✅ Easy configuration per environment
- ✅ Secure credential management
- ✅ Simple deployment configuration

## File Structure After Changes

```
project-root/
├── .env                           # NEW: Environment configuration
├── .gitignore                     # Should include .env
├── create_database.ps1            # NEW: Create PostgreSQL database
├── setup_database.ps1             # NEW: Run migrations
├── generate_migration.ps1         # NEW: Generate new migration
├── migrate_db.ps1                 # NEW: Apply migrations
├── requirements.txt               # UPDATED: Added PostgreSQL, Alembic, OpenAI
├── README.md                      # UPDATED: PostgreSQL setup instructions
│
├── backend/
│   ├── alembic.ini                # NEW: Alembic configuration
│   ├── alembic/                   # NEW: Migration directory
│   │   ├── env.py                 # NEW: Migration environment
│   │   ├── script.py.mako         # NEW: Migration template
│   │   └── versions/              # NEW: Migration files
│   ├── db.py                      # UPDATED: PostgreSQL with pooling
│   ├── init_db.py                 # UPDATED: Warn to use Alembic
│   ├── utils/
│   │   └── azure_openai.py        # NEW: Azure OpenAI helper
│   └── ...
│
├── docs/
│   ├── POSTGRESQL_SETUP.md        # NEW: PostgreSQL guide
│   ├── AZURE_OPENAI_GUIDE.md      # NEW: Azure OpenAI guide
│   ├── MIGRATION_GUIDE.md         # NEW: Migration workflow guide
│   └── ...
│
└── ...
```

## Next Steps for AI Agent Integration

To integrate Azure OpenAI into the AI agents:

### 1. Update UI Automation Agents

**Files to modify:**
- `backend/services/ui_automation/agents/planner/agent.py`
- `backend/services/ui_automation/agents/generator/agent.py`
- `backend/services/ui_automation/agents/validator/agent.py`
- `backend/services/ui_automation/agents/healer/agent.py`

**Example:**
```python
from utils.azure_openai import json_completion, create_system_message, create_user_message

def plan_test(feature_description: str):
    messages = [
        create_system_message("You are a UI test planning expert..."),
        create_user_message(f"Plan tests for: {feature_description}")
    ]
    return json_completion(messages, temperature=0.5)
```

### 2. Update API Automation Agents

**Files to modify:**
- `backend/services/api_automation/agents/planner/agent.py`
- `backend/services/api_automation/agents/generator/agent.py`

### 3. Update Synthetic Data Agents

**Files to modify:**
- `backend/services/synthetic/ui_schema/extractor.py` (if using AI for schema extraction)
- `backend/services/synthetic/api_schema/extractor.py` (if using AI for schema analysis)

## Security Reminders

1. ✅ Add `.env` to `.gitignore`
2. ✅ Never commit credentials to git
3. ✅ Use different `.env` files for dev/staging/prod
4. ✅ Rotate Azure OpenAI keys regularly
5. ✅ Use strong PostgreSQL passwords
6. ✅ Limit PostgreSQL network access
7. ✅ Enable SSL for production databases

## Troubleshooting Quick Reference

| Issue | Solution |
|-------|----------|
| Database doesn't exist | Run `.\create_database.ps1` |
| PostgreSQL not running | Start service: `Start-Service postgresql-x64-15` |
| Wrong password | Update DATABASE_URL in `.env` |
| Migration failed | Check `alembic history` and `alembic current` |
| Azure OpenAI error | Verify credentials in `.env` |
| Connection pool exhausted | Increase `pool_size` in `db.py` |

## Support Resources

- **PostgreSQL Setup**: See [docs/POSTGRESQL_SETUP.md](./POSTGRESQL_SETUP.md)
- **Azure OpenAI**: See [docs/AZURE_OPENAI_GUIDE.md](./AZURE_OPENAI_GUIDE.md)
- **Migrations**: See [docs/MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)
- **README**: See [README.md](../README.md)
