# Start Backend Server (FastAPI)
# Run from project root:  .\start_backend.ps1   (or  start_backend.cmd  if path has spaces)
# Optionally activate venv if path exists.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Activate project .venv if present; else use VENV_ACTIVATE or existing env
$venvPath = $env:VENV_ACTIVATE
if (-not $venvPath -and (Test-Path (Join-Path $root ".venv\Scripts\Activate.ps1"))) {
  $venvPath = Join-Path $root ".venv\Scripts\Activate.ps1"
}
if (-not $venvPath -and (Test-Path "C:\Users\gparavasthu\Workspace\Truvelocity\code_export\agentic-sdlc-platform\venv\Scripts\Activate.ps1")) {
  $venvPath = "C:\Users\gparavasthu\Workspace\Truvelocity\code_export\agentic-sdlc-platform\venv\Scripts\Activate.ps1"
}
if ($venvPath -and (Test-Path $venvPath)) {
  Write-Host "Activating venv: $venvPath" -ForegroundColor Yellow
  & $venvPath
}

# On Windows, Python 3.12 is recommended so pip can use pre-built wheels (no C++ Build Tools needed).
$pyVer = python -c "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}')" 2>$null
if ($pyVer -and [version]$pyVer -ge [version]"3.13") {
  Write-Host "Note: Python $pyVer detected. On Windows, Python 3.12 is recommended for pip install -r requirements.txt (avoids building numpy/pandas)." -ForegroundColor Yellow
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  Starting FastAPI Backend" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

Set-Location (Join-Path $root "backend")

# Load .env from project root and backend first (so BACKEND_PORT can be used if set)
$rootEnv = Join-Path $root ".env"
if (Test-Path $rootEnv) { Get-Content $rootEnv | ForEach-Object { if ($_ -match '^([^#=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process") } } }
if (Test-Path ".env") { Get-Content ".env" | ForEach-Object { if ($_ -match '^([^#=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process") } } }

# Choose an available backend port (default: 8001) to avoid collisions. Override via .env or BACKEND_PORT.
$port = $env:BACKEND_PORT
if (-not $port) {
  $candidatePorts = @(8001, 8002, 8003, 8004, 8005, 8010)
  foreach ($p in $candidatePorts) {
    $inUse = $false
    try {
      $inUse = Test-NetConnection -ComputerName 127.0.0.1 -Port $p -InformationLevel Quiet -WarningAction SilentlyContinue
    } catch {
      $inUse = $false
    }
    if (-not $inUse) { $port = $p; break }
  }
}
if (-not $port) {
  throw "No free port found in 8001-8010. Set BACKEND_PORT to an open port and rerun."
}
$env:BACKEND_PORT = "$port"

# Write BACKEND_PORT to project .env and frontend/.env so UI and Vite proxy use the same port
$envLines = @()
if (Test-Path $rootEnv) {
  $found = $false
  Get-Content $rootEnv | ForEach-Object {
    if ($_ -match '^\s*BACKEND_PORT\s*=') { $envLines += "BACKEND_PORT=$port"; $found = $true } else { $envLines += $_ }
  }
  if (-not $found) { $envLines += "BACKEND_PORT=$port" }
} else { $envLines += "BACKEND_PORT=$port" }
Set-Content -Path $rootEnv -Value $envLines -Encoding UTF8

$frontendEnv = Join-Path $root "frontend\.env"
$feLines = @("BACKEND_PORT=$port", "VITE_BACKEND_PORT=$port")
Set-Content -Path $frontendEnv -Value $feLines -Encoding UTF8
Write-Host "Backend port $port written to .env and frontend/.env (restart frontend if already running)" -ForegroundColor Gray

Write-Host "Initializing database..." -ForegroundColor Yellow
python -c "from db import init_db; init_db()"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Ensure backend has Playwright for crawl/UI automation (optional)
if (Test-Path "node_modules") {
  if (-not (Test-Path "node_modules\playwright")) {
    Write-Host "Installing Playwright in backend for UI crawl..." -ForegroundColor Yellow
    npm install playwright@^1.49.0 --save-dev 2>$null
  }
}

Write-Host ""
Write-Host "Server: http://localhost:$port" -ForegroundColor Cyan
Write-Host "Docs:   http://localhost:$port/docs" -ForegroundColor Cyan
$logPath = Join-Path $root "backend\logs\uvicorn.log"
Write-Host "Logs:   $logPath" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Use run_uvicorn.py so Windows gets ProactorEventLoop before uvicorn (fixes Playwright subprocess)
python run_uvicorn.py

