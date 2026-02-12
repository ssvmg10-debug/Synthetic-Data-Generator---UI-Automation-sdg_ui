# Push main branch to GitHub (private repo)
# Run this in PowerShell. You will be prompted to sign in to GitHub if not already authenticated.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$remote = "https://github.com/ssvmg10-debug/Synthetic-Data-Generator---UI-Automation-sdg_ui.git"

# Ensure remote origin is correct
$current = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0 -or $current -ne $remote) {
    if ($current) { git remote remove origin }
    git remote add origin $remote
    Write-Host "Set remote origin to: $remote"
}

# Ensure we're on main
git branch -M main 2>$null

Write-Host ""
Write-Host "Pushing main to origin (GitHub may prompt for sign-in or PAT)..." -ForegroundColor Cyan
git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "Push succeeded." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "If you see 'Repository not found', the repo is private and you must authenticate:" -ForegroundColor Yellow
    Write-Host "  1. Run this script in a terminal (not background) so you can sign in."
    Write-Host "  2. Or use a Personal Access Token: GitHub -> Settings -> Developer settings -> PAT."
    Write-Host "     When prompted for password, paste the PAT."
    Write-Host "  3. Or use SSH: git remote set-url origin git@github.com:ssvmg10-debug/Synthetic-Data-Generator---UI-Automation-sdg_ui.git"
    Write-Host "     Then run: git push -u origin main"
}
