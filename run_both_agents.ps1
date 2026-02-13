# Run Synthetic Data and UI Automation workflows with the given test case
# Usage: .\run_both_agents.ps1
# Backend must be running (e.g. .\start_backend.ps1) on port 8001

# Try 8002 first (8001 may be in use)
$port = 8002
try { $null = Invoke-WebRequest -Uri "http://localhost:8002/health" -UseBasicParsing -TimeoutSec 2 } catch { $port = 8001 }
$baseUrl = "http://localhost:$port"
$testCase = @"
1. open this application https://sauce-demo.myshopify.com/
2. Click on grey shirt,don't click on mycart, click on add to cart , 
3. then click on checkout and then checkout
4.click on sign and continue as guest and them in checkout page fill all the required fields and click on paynow
"@

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  1. SYNTHETIC DATA AGENT (generate-from-text)" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
$body1 = @{ user_input = $testCase; model = "GaussianCopula" } | ConvertTo-Json
try {
    $r1 = Invoke-RestMethod -Uri "$baseUrl/synthetic/generate-from-text" -Method POST -Body $body1 -ContentType "application/json" -TimeoutSec 300
    Write-Host "Status: $($r1.status)" -ForegroundColor Green
    if ($r1.generated_data) { Write-Host "Generated rows: $($r1.generated_data.Count)" }
    if ($r1.error) { Write-Host "Error: $($r1.error)" -ForegroundColor Red }
} catch {
    Write-Host "Request failed: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  2. UI AUTOMATION AGENT (run-workflow)" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
$body2 = @{ raw_input = $testCase } | ConvertTo-Json
try {
    $r2 = Invoke-RestMethod -Uri "$baseUrl/ui/run-workflow" -Method POST -Body $body2 -ContentType "application/json" -TimeoutSec 600
    Write-Host "Success: $($r2.success) | Status: $($r2.status)" -ForegroundColor Green
    if ($r2.error) { Write-Host "Error: $($r2.error)" -ForegroundColor Red }
} catch {
    Write-Host "Request failed: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "Done." -ForegroundColor Cyan
