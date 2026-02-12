# PowerShell script for complete database setup with Alembic

Write-Host "=== Database Setup with Alembic ===" -ForegroundColor Cyan
Write-Host ""

# Change to backend directory
Set-Location -Path "$PSScriptRoot\backend"

# Step 1: Check if .env file exists
if (-not (Test-Path "../.env")) {
    Write-Host "❌ Error: .env file not found!" -ForegroundColor Red
    Write-Host "Please create a .env file with DATABASE_URL and Azure OpenAI credentials" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ .env file found" -ForegroundColor Green

# Step 2: Test database connection
Write-Host ""
Write-Host "Testing PostgreSQL connection..." -ForegroundColor Yellow
python -c "from dotenv import load_dotenv; import os; from sqlalchemy import create_engine; load_dotenv('../.env'); engine = create_engine(os.getenv('DATABASE_URL')); connection = engine.connect(); print('✅ Database connection successful!'); connection.close()"

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Database connection failed!" -ForegroundColor Red
    Write-Host "Please check your DATABASE_URL in .env file" -ForegroundColor Yellow
    Write-Host "Expected format: postgresql://user:password@host:port/database" -ForegroundColor Yellow
    exit 1
}

# Step 3: Check if migrations already exist
$migrationFiles = Get-ChildItem -Path "alembic\versions\*.py" -ErrorAction SilentlyContinue
if ($migrationFiles.Count -gt 0) {
    Write-Host ""
    Write-Host "⚠️  Migration files already exist!" -ForegroundColor Yellow
    Write-Host "Found $($migrationFiles.Count) migration file(s)" -ForegroundColor Yellow
    $response = Read-Host "Do you want to skip migration generation and just apply existing migrations? (yes/no)"
    if ($response -eq "yes") {
        Write-Host ""
        Write-Host "Applying existing migrations..." -ForegroundColor Green
        alembic upgrade head
        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "✅ Database setup completed successfully!" -ForegroundColor Green
            exit 0
        } else {
            Write-Host "❌ Migration failed!" -ForegroundColor Red
            exit 1
        }
    }
}

# Step 4: Generate initial migration
Write-Host ""
Write-Host "Generating initial migration..." -ForegroundColor Yellow
alembic revision --autogenerate -m "Initial migration - create all tables"

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Migration generation failed!" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Migration generated successfully!" -ForegroundColor Green

# Step 5: Apply migrations
Write-Host ""
Write-Host "Applying migrations to database..." -ForegroundColor Yellow
alembic upgrade head

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Database setup completed successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Database tables created:" -ForegroundColor Cyan
    Write-Host "  • schemas" -ForegroundColor White
    Write-Host "  • synthetic_runs" -ForegroundColor White
    Write-Host "  • synthetic_data" -ForegroundColor White
    Write-Host "  • ui_test_cases" -ForegroundColor White
    Write-Host "  • locator_registry" -ForegroundColor White
    Write-Host "  • ui_execution_runs" -ForegroundColor White
    Write-Host "  • api_test_cases" -ForegroundColor White
    Write-Host "  • api_schema_cache" -ForegroundColor White
    Write-Host "  • api_execution_runs" -ForegroundColor White
    Write-Host ""
    Write-Host "You can now start the backend server with: .\start_backend.ps1" -ForegroundColor Green
} else {
    Write-Host "❌ Migration failed!" -ForegroundColor Red
    exit 1
}
