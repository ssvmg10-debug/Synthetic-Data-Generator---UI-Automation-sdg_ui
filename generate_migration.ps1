# PowerShell script to generate Alembic migration

Write-Host "Generating database migration..." -ForegroundColor Green

# Change to backend directory
Set-Location -Path "$PSScriptRoot\backend"

# Generate migration
$message = $args[0]
if (-not $message) {
    $message = "Auto-generated migration"
}

alembic revision --autogenerate -m "$message"

if ($LASTEXITCODE -eq 0) {
    Write-Host "Migration generated successfully!" -ForegroundColor Green
    Write-Host "Review the migration file in backend/alembic/versions/" -ForegroundColor Yellow
    Write-Host "Then run: .\migrate_db.ps1 to apply the migration" -ForegroundColor Yellow
} else {
    Write-Host "Migration generation failed!" -ForegroundColor Red
    exit 1
}
