# PowerShell script to run Alembic migrations

Write-Host "Running database migrations..." -ForegroundColor Green

# Change to backend directory
Set-Location -Path "$PSScriptRoot\backend"

# Run Alembic upgrade
alembic upgrade head

if ($LASTEXITCODE -eq 0) {
    Write-Host "Database migrations completed successfully!" -ForegroundColor Green
} else {
    Write-Host "Database migration failed!" -ForegroundColor Red
    exit 1
}
