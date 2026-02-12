# Database Migration Guide

## Quick Start

Follow these steps in order to set up your PostgreSQL database:

### Step 1: Create Database

```powershell
.\create_database.ps1
```

This will:
- ✅ Verify PostgreSQL is running
- ✅ Test connection with credentials from `.env`
- ✅ Create the `qea` database

### Step 2: Run Migrations

```powershell
.\setup_database.ps1
```

This will:
- ✅ Generate initial Alembic migration
- ✅ Create all 9 database tables
- ✅ Verify setup completion

### Step 3: Start the Application

```powershell
# Terminal 1 - Backend
.\start_backend.ps1

# Terminal 2 - Frontend
.\start_streamlit.ps1
```

## Detailed Migration Workflow

### First-Time Setup

```powershell
# 1. Ensure .env file exists with DATABASE_URL
# Example: DATABASE_URL=postgresql://postgres:12345@localhost:5432/qea

# 2. Create PostgreSQL database
.\create_database.ps1

# 3. Generate and apply migrations
.\setup_database.ps1

# 4. Verify tables were created
psql -U postgres -d qea -c "\dt"
```

### Making Schema Changes

When you modify SQLAlchemy models in [backend/models/__init__.py](../backend/models/__init__.py):

```powershell
# 1. Make changes to your model
# Example: Add new column to Schema table

# 2. Generate migration
.\generate_migration.ps1 "Add description column to schemas"

# 3. Review migration file
# Location: backend/alembic/versions/xxxxx_add_description_column.py

# 4. Apply migration
.\migrate_db.ps1

# 5. Verify changes
psql -U postgres -d qea -c "\d schemas"
```

### Rollback Migrations

```powershell
# Rollback one migration
cd backend
alembic downgrade -1

# Rollback to specific version
alembic downgrade abc123

# View migration history
alembic history
```

## Migration Scripts Reference

### create_database.ps1

Creates the PostgreSQL database. Run this first.

**Features:**
- Parses DATABASE_URL from .env
- Tests PostgreSQL connection
- Creates database if it doesn't exist
- Prompts before dropping existing database

**Usage:**
```powershell
.\create_database.ps1
```

### setup_database.ps1

Generates and applies initial migrations. Run after `create_database.ps1`.

**Features:**
- Verifies .env file exists
- Tests database connection
- Generates Alembic migration
- Applies migration to create tables
- Lists all created tables

**Usage:**
```powershell
.\setup_database.ps1
```

**What it creates:**
- schemas
- synthetic_runs
- synthetic_data
- ui_test_cases
- locator_registry
- ui_execution_runs
- api_test_cases
- api_schema_cache
- api_execution_runs

### generate_migration.ps1

Creates a new migration after model changes.

**Usage:**
```powershell
.\generate_migration.ps1 "Description of changes"

# Example:
.\generate_migration.ps1 "Add status field to ui_test_cases"
```

### migrate_db.ps1

Applies pending migrations to the database.

**Usage:**
```powershell
.\migrate_db.ps1
```

## Troubleshooting

### Database Does Not Exist

```
Error: database "qea" does not exist
```

**Solution:**
```powershell
.\create_database.ps1
```

### PostgreSQL Not Running

```
Error: could not connect to server: Connection refused
```

**Solution:**
```powershell
# Check if PostgreSQL is running
Get-Service -Name postgresql*

# Start PostgreSQL
Start-Service -Name postgresql-x64-15
```

### Wrong Password

```
Error: password authentication failed
```

**Solution:**
1. Verify password in `.env` matches your PostgreSQL password
2. Update DATABASE_URL in `.env`:
   ```
   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/qea
   ```

### Migration Already Exists

```
Warning: Migration files already exist!
```

**Solution:**
- Choose "yes" to skip generation and apply existing migrations
- Or delete existing migrations to regenerate:
  ```powershell
  Remove-Item "backend\alembic\versions\*.py"
  .\setup_database.ps1
  ```

### Stale Database Schema

```
Error: Target database is not up to date
```

**Solution:**
```powershell
cd backend

# Check current version
alembic current

# Apply all pending migrations
alembic upgrade head
```

### Need to Start Fresh

```powershell
# 1. Drop database
psql -U postgres -c "DROP DATABASE qea;"

# 2. Recreate and migrate
.\create_database.ps1
.\setup_database.ps1
```

## Manual Migration Commands

For advanced users who prefer manual control:

```powershell
# Navigate to backend
cd backend

# Generate migration
alembic revision --autogenerate -m "Your message here"

# Apply all migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history

# Check current version
alembic current

# Upgrade to specific version
alembic upgrade abc123

# Downgrade to specific version
alembic downgrade abc123

# Show SQL that would be executed (dry run)
alembic upgrade head --sql

# Stamp database to specific version (without running migrations)
alembic stamp head
```

## CI/CD Integration

For automated deployments:

```powershell
# In your CI/CD pipeline

# 1. Set environment variables
$env:DATABASE_URL = "postgresql://user:pass@host:5432/db"

# 2. Apply migrations
cd backend
alembic upgrade head

# 3. Verify success
if ($LASTEXITCODE -ne 0) {
    Write-Error "Migration failed!"
    exit 1
}
```

## Best Practices

1. **Always Review Generated Migrations**
   - Check `backend/alembic/versions/*.py` files
   - Verify upgrade() and downgrade() functions
   - Test rollback capability

2. **Never Edit Applied Migrations**
   - Create new migration instead
   - Alembic tracks applied migrations by revision ID

3. **Backup Before Major Changes**
   ```powershell
   pg_dump -U postgres -d qea -f backup_before_migration.sql
   ```

4. **Test Migrations Locally First**
   - Apply migration on dev database
   - Verify application works
   - Test rollback procedure

5. **Use Descriptive Migration Messages**
   ```powershell
   # Good
   .\generate_migration.ps1 "Add email and phone columns to ui_test_cases"
   
   # Bad
   .\generate_migration.ps1 "Update table"
   ```

6. **Commit Migrations to Version Control**
   ```powershell
   git add backend/alembic/versions/*.py
   git commit -m "Add migration for new schema changes"
   ```

## Migration File Structure

Generated migration files look like this:

```python
"""Add description column to schemas

Revision ID: abc123def456
Revises: previous_id
Create Date: 2024-01-15 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = 'abc123def456'
down_revision = 'previous_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic ###
    op.add_column('schemas', 
        sa.Column('description', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic ###
    op.drop_column('schemas', 'description')
    # ### end Alembic commands ###
```

## Further Reading

- [Alembic Documentation](https://alembic.sqlalchemy.org/en/latest/)
- [SQLAlchemy Models](https://docs.sqlalchemy.org/en/20/orm/mapping_styles.html)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Database Migration Best Practices](https://www.postgresql.org/docs/current/app-psql.html)
