# Start Backend Server (FastAPI)
# Run from project root. Uses Python from PATH (no venv required).

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  Starting FastAPI Backend" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

Set-Location (Join-Path $root "backend")

# Choose an available backend port (default: 8001) to avoid collisions with other local services.
# You can override by setting BACKEND_PORT in your shell environment.
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

# Load .env from project root and backend
if (Test-Path (Join-Path $root ".env")) { Get-Content (Join-Path $root ".env") | ForEach-Object { if ($_ -match '^([^#=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process") } } }
if (Test-Path ".env") { Get-Content ".env" | ForEach-Object { if ($_ -match '^([^#=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process") } } }

Write-Host "Initializing database..." -ForegroundColor Yellow
python -c "from db import init_db; init_db()"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Server: http://localhost:$port" -ForegroundColor Cyan
Write-Host "Docs:   http://localhost:$port/docs" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

python -m uvicorn main:app --host 0.0.0.0 --port $port --reload --log-level info

