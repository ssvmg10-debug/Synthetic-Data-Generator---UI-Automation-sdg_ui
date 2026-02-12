# Quick Reference - PostgreSQL & Azure OpenAI Setup

## 🚀 Complete Setup (5 Steps)

```powershell
# Step 1: Create .env file
# Add these lines to .env in project root:
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/qea
AZURE_API_KEY=your_azure_key
AZURE_ENDPOINT=https://your-endpoint.cognitiveservices.azure.com/
AZURE_DEPLOYMENT=gpt-4.1
AZURE_API_VERSION=2024-02-15-preview

# Step 2: Install dependencies (if not done)
.\setup.ps1

# Step 3: Create PostgreSQL database
.\create_database.ps1

# Step 4: Run migrations to create tables
.\setup_database.ps1

# Step 5: Start the application
.\start_backend.ps1    # Terminal 1
.\start_streamlit.ps1  # Terminal 2
```

## 📋 Common Commands

### Database Operations
```powershell
# Create database
.\create_database.ps1

# Run migrations
.\setup_database.ps1

# Generate new migration after model changes
.\generate_migration.ps1 "Description"

# Apply migrations
.\migrate_db.ps1

# View tables in database
psql -U postgres -d qea -c "\dt"

# Connect to database
psql -U postgres -d qea
```

### Application Operations
```powershell
# Activate virtual environment
C:\Users\gparavasthu\Workspace\Truvelocity\code_export\agentic-sdlc-platform\venv\Scripts\Activate.ps1

# Start backend
.\start_backend.ps1

# Start frontend
.\start_streamlit.ps1

# Check backend health
curl http://localhost:8000/health
```

### Alembic Commands
```powershell
cd backend

# Generate migration
alembic revision --autogenerate -m "Message"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View history
alembic history

# Check current version
alembic current
```

## 🔧 Troubleshooting

### Database Connection Failed
```powershell
# Check PostgreSQL is running
Get-Service -Name postgresql*

# Start PostgreSQL
Start-Service -Name postgresql-x64-15

# Test connection
psql -U postgres -c "SELECT version();"
```

### Database Doesn't Exist
```powershell
# Create it
.\create_database.ps1
```

### Wrong Password
```powershell
# Update .env file with correct password
# DATABASE_URL=postgresql://postgres:CORRECT_PASSWORD@localhost:5432/qea
```

### Azure OpenAI Error
```powershell
# Verify .env has correct values:
# - AZURE_API_KEY
# - AZURE_ENDPOINT
# - AZURE_DEPLOYMENT

# Test in Python
python -c "from utils.azure_openai import verify_config; verify_config()"
```

## 📁 Key Files

| File | Purpose |
|------|---------|
| `.env` | Configuration and credentials |
| `backend/db.py` | Database connection setup |
| `backend/models/__init__.py` | Database table definitions |
| `backend/utils/azure_openai.py` | Azure OpenAI helper functions |
| `backend/alembic/versions/*.py` | Database migrations |

## 🎯 Next Steps After Setup

1. **Verify Backend**: http://localhost:8000/docs (Swagger UI)
2. **Access Frontend**: http://localhost:8501
3. **Check Database**: `psql -U postgres -d qea -c "\dt"`
4. **Test Azure OpenAI**: See [docs/AZURE_OPENAI_GUIDE.md](./AZURE_OPENAI_GUIDE.md)

## 📚 Documentation

- **Full Setup Guide**: [README.md](../README.md)
- **PostgreSQL Details**: [docs/POSTGRESQL_SETUP.md](./POSTGRESQL_SETUP.md)
- **Azure OpenAI Guide**: [docs/AZURE_OPENAI_GUIDE.md](./AZURE_OPENAI_GUIDE.md)
- **Migration Workflow**: [docs/MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)
- **Integration Summary**: [docs/POSTGRES_AZURE_INTEGRATION.md](./POSTGRES_AZURE_INTEGRATION.md)

## ⚡ Quick Database Reset

```powershell
# Drop database
psql -U postgres -c "DROP DATABASE qea;"

# Recreate and migrate
.\create_database.ps1
.\setup_database.ps1
```

## 🔐 Security Checklist

- [ ] `.env` file is in `.gitignore`
- [ ] Strong PostgreSQL password
- [ ] Azure OpenAI keys are private
- [ ] Regular database backups scheduled
- [ ] PostgreSQL only accessible from localhost (for dev)

## 📊 Database Tables

1. schemas - Schema definitions
2. synthetic_runs - Generation history
3. synthetic_data - Generated data
4. ui_test_cases - UI test definitions
5. locator_registry - Element locators
6. ui_execution_runs - UI test results
7. api_test_cases - API test definitions
8. api_schema_cache - Cached API specs
9. api_execution_runs - API test results

## 🎨 Example: Using Azure OpenAI

```python
from utils.azure_openai import chat_completion, create_system_message, create_user_message

# Simple chat
messages = [
    create_system_message("You are a test automation expert."),
    create_user_message("Create a test plan for a login page")
]

response = chat_completion(messages, temperature=0.7)
print(response)

# JSON response
from utils.azure_openai import json_completion

response = json_completion(messages, temperature=0.5)
import json
data = json.loads(response)
```
