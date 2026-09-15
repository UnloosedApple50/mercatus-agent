# Mercatus Agent — Windows Installer
$ErrorActionPreference = "Stop"

Write-Host "Mercatus Agent — Windows Installer" -ForegroundColor Cyan

# Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "Error: Python not found. Install from python.org" -ForegroundColor Red
    exit 1
}

# Clone
$installDir = "$env:USERPROFILE\mercatus-agent"
if (Test-Path $installDir) {
    Set-Location $installDir
    git pull
} else {
    git clone https://github.com/UnloosedApple50/mercatus-agent.git $installDir
    Set-Location $installDir
}

# Setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .

Write-Host "Installation complete!" -ForegroundColor Green
Write-Host "Start with: .\.venv\Scripts\Activate.ps1; python -m mercatus run"
