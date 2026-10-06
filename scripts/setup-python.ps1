$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $Root ".venv"
$Python = Join-Path $VenvPath "Scripts\python.exe"

Write-Host "==> Project: $Root"

if (-not (Test-Path $Python)) {
    Write-Host "==> Creating virtual environment (.venv) ..."
    python -m venv $VenvPath
    if (-not (Test-Path $Python)) {
        throw "Failed to create venv. Please install Python 3.10+"
    }
} else {
    Write-Host "==> Virtual environment already exists"
}

Write-Host "==> Upgrading pip ..."
& $Python -m pip install --upgrade pip

Write-Host "==> Installing dependencies ..."
& $Python -m pip install -r (Join-Path $Root "requirements.txt")

Write-Host ""
Write-Host "[SUCCESS] Virtual environment ready: $VenvPath"
Write-Host "Start backend: npm run backend"
Write-Host "Start app:     npm run tauri dev"
