# Setup Script for Enterprise Test Automation Platform
# Run this script once to set up the environment

Write-Host "🔧 Setting up Enterprise Test Automation Platform" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& "C:\Users\gparavasthu\Workspace\Truvelocity\code_export\agentic-sdlc-platform\venv\Scripts\Activate.ps1"

# Install Python dependencies
Write-Host "`nInstalling Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# Create necessary directories
Write-Host "`nCreating directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "backend\test_outputs" | Out-Null
New-Item -ItemType Directory -Force -Path "backend\logs" | Out-Null

# Initialize database
Write-Host "`nInitializing database..." -ForegroundColor Yellow
Set-Location backend
python -c "from db import init_db; init_db()"
Set-Location ..

# Install Playwright (optional)
Write-Host "`nDo you want to install Playwright for UI automation? (Y/N)" -ForegroundColor Yellow
$installPlaywright = Read-Host

if ($installPlaywright -eq "Y" -or $installPlaywright -eq "y") {
    Write-Host "Installing Playwright..." -ForegroundColor Yellow
    npm install @playwright/test
    npx playwright install
    Write-Host "✅ Playwright installed successfully!" -ForegroundColor Green
}

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "✅ Setup completed successfully!" -ForegroundColor Green
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Start backend: .\start_backend.ps1" -ForegroundColor White
Write-Host "2. Start frontend (in new terminal): .\start_frontend.ps1" -ForegroundColor White
Write-Host "`nBackend will run on: http://localhost:8000" -ForegroundColor Cyan
Write-Host "Frontend will run on: http://localhost:5173" -ForegroundColor Cyan
