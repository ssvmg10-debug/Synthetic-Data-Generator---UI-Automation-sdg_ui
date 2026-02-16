# Start React Frontend (Vite)
# Run from project root:  .\start_frontend.ps1   (or  start_frontend.cmd  if path has spaces)
# Backend must be running first (start_backend.ps1, default port 8001).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Load .env from project root and frontend so VITE_BACKEND_PORT / BACKEND_PORT match the backend port
foreach ($envPath in @((Join-Path $root ".env"), (Join-Path $root "frontend\.env"))) {
  if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
      if ($_ -match '^\s*([^#=]+)=(.*)$') {
        $key = $matches[1].Trim(); $val = $matches[2].Trim()
        if ($key -eq "BACKEND_PORT" -or $key -eq "VITE_BACKEND_PORT") {
          [Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
      }
    }
  }
}
# Keep VITE_BACKEND_PORT in sync with BACKEND_PORT so Vite proxy always uses current backend port
if ($env:BACKEND_PORT -and -not $env:VITE_BACKEND_PORT) { $env:VITE_BACKEND_PORT = $env:BACKEND_PORT }
# Default proxy to 8001 if not set (must match start_backend.ps1 default)
if (-not $env:BACKEND_PORT -and -not $env:VITE_BACKEND_PORT) {
  $env:VITE_BACKEND_PORT = "8001"
}

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

$bePort = if ($env:VITE_BACKEND_PORT) { $env:VITE_BACKEND_PORT } elseif ($env:BACKEND_PORT) { $env:BACKEND_PORT } else { "8001" }
Write-Host "Frontend will be at http://localhost:5173" -ForegroundColor Cyan
Write-Host "API proxy -> http://localhost:$bePort (start backend with start_backend.ps1 if needed)" -ForegroundColor Yellow
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

npx vite
