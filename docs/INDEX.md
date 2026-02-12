# Documentation Index

Welcome to the Enterprise Test Automation Platform documentation!

## 📚 Getting Started

### 🚀 Quick Start
- **[README](../README.md)** - Main project overview and quick start guide
- **[Quick Reference](./QUICK_REFERENCE.md)** - Essential commands and troubleshooting

## 🗄️ Database Setup

### PostgreSQL & Migrations
- **[PostgreSQL Setup Guide](./POSTGRESQL_SETUP.md)** - Complete PostgreSQL installation and configuration
- **[Migration Guide](./MIGRATION_GUIDE.md)** - Database migration workflow with Alembic

**Topics Covered:**
- Installing PostgreSQL on Windows
- Creating databases
- Running migrations
- Schema management
- Backup and restore
- Performance tuning
- Troubleshooting

## 🤖 AI Integration

### Azure OpenAI
- **[Azure OpenAI Guide](./AZURE_OPENAI_GUIDE.md)** - Complete guide to Azure OpenAI integration

**Topics Covered:**
- Configuration and credentials
- Using the helper module
- AI agent integration patterns
- Prompt engineering best practices
- Error handling
- Token management
- Cost estimation
- Security best practices

## 🔄 Integration Summary

- **[PostgreSQL & Azure OpenAI Integration](./POSTGRES_AZURE_INTEGRATION.md)** - Summary of all changes and integration details

**Topics Covered:**
- Complete list of changes made
- File-by-file modifications
- Setup workflow
- Benefits of the new architecture
- Next steps for AI agent integration
- Security reminders

## 📖 Documentation by Topic

### Setup & Installation
1. [README - Quick Start](../README.md#quick-start)
2. [PostgreSQL Setup](./POSTGRESQL_SETUP.md)
3. [Migration Guide](./MIGRATION_GUIDE.md)

### Configuration
1. [Environment Variables](./POSTGRESQL_SETUP.md#configuration)
2. [Azure OpenAI Configuration](./AZURE_OPENAI_GUIDE.md#configuration)
3. [Database Connection](./POSTGRESQL_SETUP.md#connection-string-format)

### Database Operations
1. [Creating Database](./MIGRATION_GUIDE.md#step-1-create-database)
2. [Running Migrations](./MIGRATION_GUIDE.md#step-2-run-migrations)
3. [Making Schema Changes](./MIGRATION_GUIDE.md#making-schema-changes)
4. [Rollback Migrations](./MIGRATION_GUIDE.md#rollback-migrations)
5. [Backup & Restore](./POSTGRESQL_SETUP.md#backup-and-restore)

### AI Development
1. [Azure OpenAI Basics](./AZURE_OPENAI_GUIDE.md#usage-in-code)
2. [AI Agent Patterns](./AZURE_OPENAI_GUIDE.md#ai-agent-integration)
3. [Best Practices](./AZURE_OPENAI_GUIDE.md#best-practices)
4. [Error Handling](./AZURE_OPENAI_GUIDE.md#error-handling)

### Troubleshooting
1. [Quick Reference](./QUICK_REFERENCE.md#troubleshooting)
2. [PostgreSQL Issues](./POSTGRESQL_SETUP.md#troubleshooting)
3. [Azure OpenAI Issues](./AZURE_OPENAI_GUIDE.md#troubleshooting)
4. [Migration Issues](./MIGRATION_GUIDE.md#troubleshooting)

### Advanced Topics
1. [Connection Pooling](./POSTGRESQL_SETUP.md#connection-pooling)
2. [Performance Tuning](./POSTGRESQL_SETUP.md#performance-tuning)
3. [Monitoring](./POSTGRESQL_SETUP.md#monitoring)
4. [Security](./POSTGRESQL_SETUP.md#security-best-practices)
5. [Production Deployment](./POSTGRESQL_SETUP.md#production-deployment)

## 🎯 Common Tasks

### First-Time Setup
```powershell
# 1. Create .env file with credentials
# 2. Run:
.\setup.ps1
.\create_database.ps1
.\setup_database.ps1
.\start_backend.ps1
```

See: [Quick Reference](./QUICK_REFERENCE.md#complete-setup-5-steps)

### Making Schema Changes
```powershell
# 1. Edit backend/models/__init__.py
# 2. Run:
.\generate_migration.ps1 "Description"
.\migrate_db.ps1
```

See: [Migration Guide](./MIGRATION_GUIDE.md#making-schema-changes)

### Integrating AI Agents
```python
from utils.azure_openai import chat_completion, create_system_message, create_user_message

messages = [
    create_system_message("You are an expert..."),
    create_user_message("Task description...")
]

response = chat_completion(messages)
```

See: [Azure OpenAI Guide](./AZURE_OPENAI_GUIDE.md#ai-agent-integration)

### Database Backup
```powershell
pg_dump -U postgres -d qea -f backup.sql
```

See: [PostgreSQL Setup](./POSTGRESQL_SETUP.md#backup-and-restore)

## 📋 Scripts Reference

### Database Scripts
| Script | Purpose |
|--------|---------|
| `create_database.ps1` | Create PostgreSQL database |
| `setup_database.ps1` | Generate and apply initial migrations |
| `generate_migration.ps1` | Create new migration |
| `migrate_db.ps1` | Apply pending migrations |

### Application Scripts
| Script | Purpose |
|--------|---------|
| `setup.ps1` | Initial project setup |
| `start_backend.ps1` | Start FastAPI backend |
| `start_streamlit.ps1` | Start Streamlit frontend |

See: [Migration Guide - Scripts Reference](./MIGRATION_GUIDE.md#migration-scripts-reference)

## 🔑 Key Files

### Configuration
- `.env` - Environment variables and credentials
- `backend/alembic.ini` - Alembic configuration
- `requirements.txt` - Python dependencies

### Application Code
- `backend/db.py` - Database connection
- `backend/models/__init__.py` - SQLAlchemy models
- `backend/utils/azure_openai.py` - Azure OpenAI helper

### Migrations
- `backend/alembic/env.py` - Migration environment
- `backend/alembic/versions/*.py` - Migration files

See: [Integration Summary - File Structure](./POSTGRES_AZURE_INTEGRATION.md#file-structure-after-changes)

## 🎓 Learning Path

### For New Users
1. Read [README](../README.md)
2. Follow [Quick Reference - Complete Setup](./QUICK_REFERENCE.md#complete-setup-5-steps)
3. Explore [PostgreSQL Setup Guide](./POSTGRESQL_SETUP.md)
4. Learn [Azure OpenAI basics](./AZURE_OPENAI_GUIDE.md#usage-in-code)

### For Developers
1. Understand [Database Schema](./POSTGRES_AZURE_INTEGRATION.md#database-schema)
2. Learn [Migration Workflow](./MIGRATION_GUIDE.md#detailed-migration-workflow)
3. Study [AI Agent Patterns](./AZURE_OPENAI_GUIDE.md#ai-agent-integration)
4. Review [Best Practices](./AZURE_OPENAI_GUIDE.md#best-practices)

### For DevOps
1. [Production Deployment](./POSTGRESQL_SETUP.md#production-deployment)
2. [Backup Strategy](./POSTGRESQL_SETUP.md#backup-and-restore)
3. [Monitoring Setup](./POSTGRESQL_SETUP.md#monitoring)
4. [Security Configuration](./POSTGRESQL_SETUP.md#security-best-practices)

## 🆘 Getting Help

### Quick Issues
Check [Quick Reference - Troubleshooting](./QUICK_REFERENCE.md#troubleshooting)

### Database Issues
See [PostgreSQL Setup - Troubleshooting](./POSTGRESQL_SETUP.md#troubleshooting)

### Migration Issues
See [Migration Guide - Troubleshooting](./MIGRATION_GUIDE.md#troubleshooting)

### AI Integration Issues
See [Azure OpenAI Guide - Troubleshooting](./AZURE_OPENAI_GUIDE.md#troubleshooting)

## 📞 Support Resources

- **PostgreSQL Documentation**: https://www.postgresql.org/docs/
- **Alembic Documentation**: https://alembic.sqlalchemy.org/
- **SQLAlchemy Documentation**: https://docs.sqlalchemy.org/
- **Azure OpenAI Documentation**: https://learn.microsoft.com/en-us/azure/ai-services/openai/
- **OpenAI API Reference**: https://platform.openai.com/docs/api-reference

## 🔄 Document Updates

This documentation is maintained alongside the codebase. Last major update covers:
- PostgreSQL migration from SQLite
- Azure OpenAI integration
- Alembic migration setup
- Environment variable configuration
- Updated PowerShell scripts

## 📝 Contributing

When updating documentation:
1. Keep examples up to date
2. Test all commands
3. Update cross-references
4. Add new topics to this index
5. Follow existing formatting

---

**Quick Links:**
[README](../README.md) | 
[Quick Reference](./QUICK_REFERENCE.md) | 
[PostgreSQL Setup](./POSTGRESQL_SETUP.md) | 
[Migration Guide](./MIGRATION_GUIDE.md) | 
[Azure OpenAI Guide](./AZURE_OPENAI_GUIDE.md) | 
[Integration Summary](./POSTGRES_AZURE_INTEGRATION.md)
