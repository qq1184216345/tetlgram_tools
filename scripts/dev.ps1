# 纸翼 (PaperWing) 开发启动 (Windows PowerShell)
# Usage: .\scripts\dev.ps1
#        .\scripts\dev.ps1 -BackendOnly
#        .\scripts\dev.ps1 -SkipSetup

param(
    [switch]$BackendOnly,
    [switch]$SkipSetup
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Write-Step([string]$msg) { Write-Host "" ; Write-Host "==> $msg" -ForegroundColor Cyan }
function Write-Ok([string]$msg)   { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn([string]$msg) { Write-Host "[!] $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "  纸翼 Dev" -ForegroundColor White
Write-Host "  Root: $Root" -ForegroundColor DarkGray
Write-Host ""

Write-Step "Check Node.js"
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js not found. Install Node.js 20+ from https://nodejs.org"
}
Write-Ok ("Node " + (node -v))

Write-Step "Check Python"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python not found. Install Python 3.10+ from https://python.org"
}
Write-Ok ("Python " + (python --version 2>&1))

if (-not $SkipSetup) {
    Write-Step "Check npm dependencies"
    if (-not (Test-Path (Join-Path $Root "node_modules"))) {
        Write-Warn "node_modules missing, running npm install ..."
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install failed" }
    }
    Write-Ok "npm dependencies ready"

    Write-Step "Check Python venv"
    $VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        Write-Warn "venv missing, running setup:python ..."
        & (Join-Path $Root "scripts\setup-python.ps1")
        if (-not (Test-Path $VenvPython)) { throw "Failed to create venv" }
    }
    Write-Ok "Python venv ready (.venv)"
}

$PortsFile = Join-Path $Root "config\ports.json"
$BackendPort = 28147
$FrontendPort = 28182
$LicensePort = 28180
$LicenseHost = "127.0.0.1"
if (Test-Path $PortsFile) {
    try {
        $ports = Get-Content $PortsFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $BackendPort = [int]$ports.backend.port
        $FrontendPort = [int]$ports.frontend.port
        if ($ports.license.port) { $LicensePort = [int]$ports.license.port }
        if ($ports.license.host) { $LicenseHost = [string]$ports.license.host }
    }
    catch {
        Write-Warn "Could not parse config/ports.json, using defaults"
    }
}

$BackendHost = "127.0.0.1"
$HealthUrl = "$BackendHost`:$BackendPort/health"
$BackendUrl = "http://$HealthUrl"
$FrontendUrl = "http://localhost:$FrontendPort"
$LicenseUrl = "http://$LicenseHost`:$LicensePort"
$script:LicenseProc = $null

function Stop-PortListener([int]$Port) {
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $connections) {
        $procId = $conn.OwningProcess
        if ($procId -and $procId -gt 0) {
            Write-Warn "Port $Port in use by PID $procId, stopping ..."
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
}

function Start-LicenseServer {
    Write-Step "Start license server ($LicenseHost`:$LicensePort)"
    $LicenseDir = Join-Path $Root "license-server"
    $VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $VenvPython)) {
        throw "venv python missing: $VenvPython"
    }

    # PostgreSQL（可选：有 Docker 则拉起）
    if (Get-Command docker -ErrorAction SilentlyContinue) {
        try {
            Push-Location $LicenseDir
            docker compose up -d 2>$null | Out-Null
            Pop-Location
            Write-Ok "PostgreSQL compose checked"
        }
        catch {
            Pop-Location -ErrorAction SilentlyContinue
            Write-Warn "docker compose skipped: $($_.Exception.Message)"
        }
    }
    else {
        Write-Warn "Docker not found; ensure PostgreSQL is reachable per license-server/.env"
    }

    # 安装授权云依赖（轻量，已装会很快）
    & $VenvPython -m pip install -q -r (Join-Path $LicenseDir "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "license-server pip install returned $LASTEXITCODE"
    }

    Stop-PortListener -Port $LicensePort
    Start-Sleep -Milliseconds 400

    $env:PYTHONPATH = $LicenseDir
    $script:LicenseProc = Start-Process -FilePath $VenvPython `
        -ArgumentList "-m", "license_server" `
        -WorkingDirectory $LicenseDir `
        -PassThru `
        -WindowStyle Minimized

    # 等待健康检查
    $ok = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $resp = Invoke-WebRequest -Uri "$LicenseUrl/health" -UseBasicParsing -TimeoutSec 1
            if ($resp.StatusCode -eq 200) { $ok = $true; break }
        }
        catch { }
    }
    if ($ok) {
        Write-Ok "License server ready  $LicenseUrl"
        Write-Host "  Admin     $LicenseUrl/admin/" -ForegroundColor DarkGray
    }
    else {
        Write-Warn "License server did not become healthy in time; login may fail until it starts"
        Write-Host "  Check: $LicenseUrl/health" -ForegroundColor DarkGray
    }
}

function Stop-LicenseServer {
    if ($script:LicenseProc -and -not $script:LicenseProc.HasExited) {
        Write-Step "Stop license server (PID $($script:LicenseProc.Id))"
        Stop-Process -Id $script:LicenseProc.Id -Force -ErrorAction SilentlyContinue
    }
}

if ($BackendOnly) {
    Stop-PortListener -Port $BackendPort
    Start-Sleep -Milliseconds 500
    Write-Step "Start Python backend only ($BackendHost`:$BackendPort)"
    Write-Host "Health: $BackendUrl" -ForegroundColor DarkGray
    Write-Host "Press Ctrl+C to stop" -ForegroundColor DarkGray
    Write-Host ""
    $env:PAPERWING_DATA = Join-Path $Root "data"
    $env:TELEGRAM_TOOLS_DATA = $env:PAPERWING_DATA
    npm run backend
    exit $LASTEXITCODE
}

try {
    Start-LicenseServer

    Write-Step "Start dev (Tauri + Vite + Python backend)"
    Stop-PortListener -Port $BackendPort
    Start-Sleep -Milliseconds 500
    $env:PAPERWING_DATA = Join-Path $Root "data"
    $env:TELEGRAM_TOOLS_DATA = $env:PAPERWING_DATA
    Write-Host ""
    Write-Host "  License  $LicenseUrl" -ForegroundColor DarkGray
    Write-Host "  Backend  $BackendUrl" -ForegroundColor DarkGray
    Write-Host "  Frontend $FrontendUrl" -ForegroundColor DarkGray
    Write-Host "  Data     $env:PAPERWING_DATA" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Tauri will spawn the Python backend. Press Ctrl+C to exit." -ForegroundColor DarkGray
    Write-Host ""

    npm run tauri dev
    exit $LASTEXITCODE
}
finally {
    Stop-LicenseServer
}
