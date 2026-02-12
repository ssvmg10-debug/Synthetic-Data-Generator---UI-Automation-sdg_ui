# PostgreSQL Database Setup Guide

## Overview

The platform uses PostgreSQL as the production database with Alembic for schema migrations. This provides:
- **Production-ready** reliability and performance
- **ACID compliance** for data integrity
- **Connection pooling** for concurrent users
- **Schema versioning** through Alembic migrations
- **Easy rollback** of database changes

## Prerequisites

### Install PostgreSQL

**Windows:**
1. Download PostgreSQL from [postgresql.org/download/windows](https://www.postgresql.org/download/windows/)
2. Run the installer (version 12 or higher recommended)
3. During installation:
   - Set password for postgres user (remember this!)
   - Use default port: 5432
   - Select default locale

**Verify Installation:**
```powershell
psql --version
# Should output: psql (PostgreSQL) 15.x or higher
```

### Create Database

Open pgAdmin or use command line:

```sql
-- Using psql command line
psql -U postgres

-- Create database
CREATE DATABASE qea;

-- Verify
\l
```

Or using pgAdmin:
1. Open pgAdmin
2. Right-click "Databases" → Create → Database
3. Name: `qea`
4. Owner: `postgres`
5. Click Save

## Configuration

### Environment Variables

Create/update `.env` file in project root:

```env
# PostgreSQL Configuration
DATABASE_URL=postgresql://postgres:12345@localhost:5432/qea

# Components:
# - postgres: username
# - 12345: password (change to your postgres password!)
# - localhost: database host
# - 5432: PostgreSQL port
# - qea: database name
```

**Important:** Replace `12345` with your actual PostgreSQL password!

### Connection String Format

```
postgresql://[user]:[password]@[host]:[port]/[database]

Examples:
- Local: postgresql://postgres:mypassword@localhost:5432/qea
- Remote: postgresql://user:pass@db.example.com:5432/production
- With SSL: postgresql://user:pass@host:5432/db?sslmode=require
```

## Database Migrations with Alembic

### Initial Setup

The project includes Alembic configuration. To set up the database:

```powershell
# Run the automated setup script
.\setup_database.ps1
```

This script will:
1. ✅ Verify `.env` file exists
2. ✅ Test PostgreSQL connection
3. ✅ Generate initial migration
4. ✅ Create all database tables
5. ✅ Verify setup completion

### Manual Setup (Alternative)

If you prefer manual setup:

```powershell
# Navigate to backend directory
cd backend

# Generate initial migration
alembic revision --autogenerate -m "Initial migration - create all tables"

# Review the generated migration file
# Location: backend/alembic/versions/xxxxx_initial_migration.py

# Apply migration
alembic upgrade head
```

### Migration Commands

```powershell
# Generate new migration after model changes
cd backend
alembic revision --autogenerate -m "Add new column to users"

# Or use the convenience script
.\generate_migration.ps1 "Add new column to users"

# Apply all pending migrations
alembic upgrade head

# Or use the convenience script
.\migrate_db.ps1

# View migration history
alembic history

# Check current version
alembic current

# Rollback one migration
alembic downgrade -1

# Rollback to specific version
alembic downgrade abc123

# Rollback all migrations
alembic downgrade base
```

## Database Schema

### Tables Created

The initial migration creates 9 tables:

1. **schemas**
   - Stores UI/API schema definitions
   - Columns: id, name, type, schema_json, created_at

2. **synthetic_runs**
   - Tracks data generation executions
   - Columns: id, schema_id, rows, status, created_at, completed_at

3. **synthetic_data**
   - Stores generated test data
   - Columns: id, run_id, data_json, created_at

4. **ui_test_cases**
   - UI test definitions
   - Columns: id, name, description, script, status, created_at

5. **locator_registry**
   - Element locator cache for self-healing
   - Columns: id, page_url, element_name, locator_type, locator_value, confidence

6. **ui_execution_runs**
   - UI test execution history
   - Columns: id, test_case_id, status, logs, screenshots, started_at, completed_at

7. **api_test_cases**
   - API test definitions
   - Columns: id, name, endpoint, method, request_body, assertions, created_at

8. **api_schema_cache**
   - Cached API specifications
   - Columns: id, url, schema_json, last_updated

9. **api_execution_runs**
   - API test execution history
   - Columns: id, test_case_id, status, request, response, started_at, completed_at

### View Schema

```sql
-- Connect to database
psql -U postgres -d qea

-- List all tables
\dt

-- Describe specific table
\d schemas

-- View all schemas with data
SELECT tablename FROM pg_tables WHERE schemaname = 'public';
```

## Connection Pooling

The application uses SQLAlchemy's connection pooling for optimal performance:

```python
# backend/db.py configuration
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,           # Number of connections to maintain
    max_overflow=20,        # Additional connections if needed
    pool_pre_ping=True,     # Verify connections before use
    pool_recycle=3600       # Recycle connections every hour
)
```

**Benefits:**
- ⚡ Faster query execution (reuse connections)
- 📊 Handle concurrent users efficiently
- 🔄 Automatic connection health checks
- 🛡️ Prevent stale connection issues

## Backup and Restore

### Backup Database

```powershell
# Full database backup
pg_dump -U postgres -d qea -f backup_qea.sql

# Compressed backup
pg_dump -U postgres -d qea | gzip > backup_qea.sql.gz

# Backup specific tables
pg_dump -U postgres -d qea -t synthetic_runs -t synthetic_data -f data_backup.sql

# Scheduled backup (Windows Task Scheduler)
# Create a .bat file:
@echo off
set PGPASSWORD=your_password
pg_dump -U postgres -d qea -f "C:\backups\qea_%date:~-4,4%%date:~-10,2%%date:~-7,2%.sql"
```

### Restore Database

```powershell
# Drop existing database (CAUTION!)
dropdb -U postgres qea

# Create fresh database
createdb -U postgres qea

# Restore from backup
psql -U postgres -d qea -f backup_qea.sql

# Or restore compressed backup
gunzip -c backup_qea.sql.gz | psql -U postgres -d qea
```

## Performance Tuning

### Indexes

Add indexes for frequently queried columns:

```sql
-- Create indexes (add to migration file)
CREATE INDEX idx_synthetic_runs_schema_id ON synthetic_runs(schema_id);
CREATE INDEX idx_synthetic_data_run_id ON synthetic_data(run_id);
CREATE INDEX idx_ui_execution_runs_test_case_id ON ui_execution_runs(test_case_id);
CREATE INDEX idx_api_execution_runs_test_case_id ON api_execution_runs(test_case_id);

-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM synthetic_runs WHERE schema_id = 1;
```

### Maintenance

```sql
-- Vacuum database (reclaim space)
VACUUM ANALYZE;

-- Reindex tables
REINDEX TABLE synthetic_runs;

-- Update statistics
ANALYZE synthetic_runs;
```

## Monitoring

### Check Database Size

```sql
-- Database size
SELECT pg_size_pretty(pg_database_size('qea'));

-- Table sizes
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Active Connections

```sql
-- View active connections
SELECT pid, usename, application_name, client_addr, state, query
FROM pg_stat_activity
WHERE datname = 'qea';

-- Kill specific connection
SELECT pg_terminate_backend(pid);
```

### Query Performance

```sql
-- Enable slow query logging
ALTER DATABASE qea SET log_min_duration_statement = 1000; -- Log queries > 1 second

-- View slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

## Troubleshooting

### Connection Refused

```
Error: could not connect to server: Connection refused
```

**Solutions:**
1. Verify PostgreSQL is running:
   ```powershell
   # Windows
   Get-Service -Name postgresql*
   
   # Start if stopped
   Start-Service -Name postgresql-x64-15
   ```

2. Check port 5432 is not blocked:
   ```powershell
   Test-NetConnection -ComputerName localhost -Port 5432
   ```

3. Verify `pg_hba.conf` allows local connections:
   ```
   # Location: C:\Program Files\PostgreSQL\15\data\pg_hba.conf
   # Should have line:
   host    all             all             127.0.0.1/32            md5
   ```

### Authentication Failed

```
Error: password authentication failed for user "postgres"
```

**Solutions:**
1. Verify password in `.env` file matches PostgreSQL
2. Reset password if needed:
   ```powershell
   psql -U postgres
   ALTER USER postgres PASSWORD 'newpassword';
   ```

### Database Does Not Exist

```
Error: database "qea" does not exist
```

**Solution:**
```powershell
# Create database
psql -U postgres -c "CREATE DATABASE qea;"
```

### Migration Failed

```
Error: Target database is not up to date
```

**Solutions:**
```powershell
# Check current version
cd backend
alembic current

# View history
alembic history

# Force stamp to specific version
alembic stamp head

# Or downgrade and retry
alembic downgrade -1
alembic upgrade head
```

### Port Already in Use

```
Error: bind: address already in use
```

**Solutions:**
```powershell
# Find process using port 5432
netstat -ano | findstr :5432

# Kill process (use PID from above)
taskkill /PID <PID> /F

# Or change PostgreSQL port in postgresql.conf
```

## Security Best Practices

1. **Strong Passwords**
   ```sql
   -- Use complex passwords
   ALTER USER postgres PASSWORD 'aB3#xY9$mN2@pQ7!';
   ```

2. **Limited Privileges**
   ```sql
   -- Create app-specific user with limited permissions
   CREATE USER qea_app WITH PASSWORD 'strong_password';
   GRANT CONNECT ON DATABASE qea TO qea_app;
   GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO qea_app;
   
   -- Update DATABASE_URL to use new user
   postgresql://qea_app:strong_password@localhost:5432/qea
   ```

3. **SSL Connections** (for production)
   ```
   DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require
   ```

4. **Firewall Rules**
   - Only allow connections from application server
   - Block external access to port 5432

5. **Regular Backups**
   - Automated daily backups
   - Store backups in secure location
   - Test restore process regularly

## Production Deployment

### Docker Deployment

```yaml
# docker-compose.yml
version: '3.8'
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: qea
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Cloud Deployment

**Azure Database for PostgreSQL:**
1. Create Azure Database for PostgreSQL server
2. Configure firewall rules
3. Update DATABASE_URL with Azure connection string
4. Enable SSL: `?sslmode=require`

**AWS RDS PostgreSQL:**
1. Create RDS PostgreSQL instance
2. Configure security groups
3. Update DATABASE_URL with RDS endpoint
4. Enable automated backups

**Connection String:**
```
postgresql://username:password@server.postgres.database.azure.com:5432/qea?sslmode=require
```

## Further Reading

- [PostgreSQL Official Documentation](https://www.postgresql.org/docs/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Connection Pooling](https://docs.sqlalchemy.org/en/20/core/pooling.html)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
