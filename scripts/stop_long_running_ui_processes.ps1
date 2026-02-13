# Stop long-running UI automation / crawler / Node / Python processes (e.g. running 24+ hours).
# Run from project root: .\scripts\stop_long_running_ui_processes.ps1
# Optional: -Kill to actually kill; without -Kill only lists.

param(
    [switch]$Kill,
    [int]$HoursOlderThan = 24
)

$cutoff = (Get-Date).AddHours(-$HoursOlderThan)
$names = @("node", "python", "python3", "chromium", "msedge", "chrome")

Write-Host "Processes started before $cutoff (running more than $HoursOlderThan hours):" -ForegroundColor Cyan
$found = @()
Get-Process -Name $names -ErrorAction SilentlyContinue | ForEach-Object {
    $p = $_
    try {
        if ($p.StartTime -and $p.StartTime -lt $cutoff) {
            $found += $p
            $age = [math]::Round(((Get-Date) - $p.StartTime).TotalHours, 1)
            Write-Host "  PID $($p.Id) $($p.ProcessName) (started $($p.StartTime), ~$age h ago)" -ForegroundColor Yellow
        }
    } catch { }
}

if ($found.Count -eq 0) {
    Write-Host "No long-running matching processes found." -ForegroundColor Green
    exit 0
}

if ($Kill) {
    Write-Host ""
    Write-Host "Killing $($found.Count) process(es)..." -ForegroundColor Red
    $found | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "Done." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "To kill these processes, run: .\scripts\stop_long_running_ui_processes.ps1 -Kill" -ForegroundColor Magenta
}
