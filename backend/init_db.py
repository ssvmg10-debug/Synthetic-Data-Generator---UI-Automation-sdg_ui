#!/usr/bin/env python3
"""
Initialize Database
DEPRECATED: Use Alembic migrations for PostgreSQL
Run: alembic upgrade head
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from db import init_db

if __name__ == "__main__":
    print("⚠️  WARNING: Direct database initialization is deprecated for PostgreSQL")
    print("Please use Alembic migrations instead:")
    print("1. Generate migration: alembic revision --autogenerate -m 'Initial migration'")
    print("2. Apply migration: alembic upgrade head")
    print("\nOr use the PowerShell scripts:")
    print("1. .\\generate_migration.ps1 'Initial migration'")
    print("2. .\\migrate_db.ps1")
    print("\nIf you still want to create tables directly (not recommended):")
    response = input("Continue? (yes/no): ")
    if response.lower() == "yes":
        print("Initializing database...")
        init_db()
        print("✅ Database initialized successfully!")
    else:
        print("Cancelled. Please use Alembic migrations.")

