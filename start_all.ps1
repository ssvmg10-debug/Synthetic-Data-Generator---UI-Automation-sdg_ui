# Start Backend + React Frontend
# Run from project root. Opens two windows: backend (FastAPI) and frontend (React/Vite).

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  Enterprise Test Agents - Starting Backend and React UI" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Start Backend in new window
Write-Host "Starting Backend (FastAPI)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-File", (Join-Path $root "start_backend.ps1")
Start-Sleep -Seconds 4

# Start Frontend (React) in new window
Write-Host "Starting Frontend (React/Vite)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-File", (Join-Path $root "start_frontend.ps1")
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  Services started" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  Backend API:  (see backend window for port)" -ForegroundColor Cyan
Write-Host "  API Docs:    (see backend window for port)" -ForegroundColor Cyan
Write-Host "  React UI:    http://localhost:5173" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Open http://localhost:5173 in your browser to use the app." -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press any key to close this window (backend and frontend keep running in other windows)..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
