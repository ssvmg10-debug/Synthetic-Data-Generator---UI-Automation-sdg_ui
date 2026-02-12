"""
Run Alembic migrations (non-interactive)

This script ensures all existing migrations are applied to the configured database.
Loads .env from project root so DATABASE_URL is available when Alembic runs.
"""
import os
import sys
import subprocess
from pathlib import Path

try:
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parent
    load_dotenv(_root / ".env")
    load_dotenv(_root / "backend" / ".env")
    # Ensure default for DATABASE_URL if not set
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "postgresql://postgres:12345@localhost:5432/qea"
except ImportError:
    pass


def main() -> int:
    root = Path(__file__).resolve().parent
    backend_dir = root / "backend"
    os.chdir(backend_dir)

    print("=" * 50)
    print("Database Migrations")
    print("=" * 50)
    print()

    versions_dir = backend_dir / "alembic" / "versions"
    migration_files = list(versions_dir.glob("*.py")) if versions_dir.exists() else []

    if not migration_files:
        print("No Alembic migration files found in backend/alembic/versions.")
        print("Please generate an initial migration first, for example:")
        print("  python -m alembic revision --autogenerate -m \"Initial migration\"")
        return 1

    print(f"Applying {len(migration_files)} existing migration(s) to the database...")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        shell=False,
        cwd=str(backend_dir),
        env=os.environ.copy(),
    )

    if result.returncode == 0:
        print()
        print("Migrations applied successfully!")
        print("You can now start the backend server with: .\\start_backend.ps1")
        return 0

    print("Migration failed!")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

