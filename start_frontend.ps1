# Start React Frontend (Vite)
# Run from project root. Backend must be running on http://localhost:8000 for API.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  Starting React Frontend (Vite)" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

Set-Location (Join-Path $root "frontend")

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing npm dependencies..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
# If vite not found (e.g. after EPERM), reinstall
if (-not (Test-Path "node_modules\.bin\vite.cmd")) {
    Write-Host "Vite not found; reinstalling dependencies..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force node_modules -ErrorAction SilentlyContinue
    npm install
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Frontend will be at http://localhost:5173" -ForegroundColor Cyan
Write-Host "Ensure backend is running (start_backend.ps1, default port 8001)" -ForegroundColor Yellow
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

npx vite
