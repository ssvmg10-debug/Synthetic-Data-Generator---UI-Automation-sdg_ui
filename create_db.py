"""
Create PostgreSQL Database using Python
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

# Load .env from project root (and backend as fallback)
_root = Path(__file__).resolve().parent
load_dotenv(_root / ".env")
load_dotenv(_root / "backend" / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:12345@localhost:5432/qea")
if not DATABASE_URL:
    print("DATABASE_URL not found. Set it in .env or use default.")
    sys.exit(1)

# Parse database name from URL
# Format: postgresql://user:password@host:port/database
try:
    db_name = DATABASE_URL.split("/")[-1]
    base_url = "/".join(DATABASE_URL.split("/")[:-1]) + "/postgres"  # Connect to default database
    
    print("=" * 50)
    print("PostgreSQL Database Creation")
    print("=" * 50)
    print(f"Database to create: {db_name}")
    print()
    
    # Try to connect to PostgreSQL
    print("Testing PostgreSQL connection...")
    engine = create_engine(base_url)
    
    with engine.connect() as conn:
        conn.execute(text("COMMIT"))  # End any transaction
        
        # Check if database exists
        result = conn.execute(
            text(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'")
        )
        exists = result.fetchone() is not None
        
        if exists:
            print(f"Database '{db_name}' already exists!")
            response = input("Drop and recreate? (yes/no) [CAUTION: This will delete all data!]: ")
            
            if response.lower() == "yes":
                print(f"\nDropping database '{db_name}'...")
                
                # Terminate connections
                conn.execute(text(f"""
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = '{db_name}'
                    AND pid <> pg_backend_pid()
                """))
                conn.execute(text("COMMIT"))
                
                # Drop database
                conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
                conn.execute(text("COMMIT"))
                print("Database dropped successfully")
                exists = False
            else:
                print("\nUsing existing database")
                print("You can now run: python backend/run_migrations.py")
                sys.exit(0)
        
        if not exists:
            # Create database
            print(f"\nCreating database '{db_name}'...")
            conn.execute(text("COMMIT"))
            conn.execute(text(f"CREATE DATABASE {db_name}"))
            conn.execute(text("COMMIT"))
            print(f"Database '{db_name}' created successfully!")
            print()
            print("Next steps:")
            print("1. Run: python backend/run_migrations.py  (to create tables)")
            print("2. Run: .\\start_backend.ps1   (to start the server)")
    
except OperationalError as e:
    print("Cannot connect to PostgreSQL!")
    print()
    print("Possible issues:")
    print("1. PostgreSQL is not running - Start it from Services (services.msc)")
    print("2. Wrong password - Check DATABASE_URL in .env file")
    print("3. PostgreSQL not installed - Download from https://www.postgresql.org/download/")
    print()
    print(f"Error details: {e}")
    sys.exit(1)
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
