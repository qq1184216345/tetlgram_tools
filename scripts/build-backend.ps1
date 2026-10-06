# Build Python backend with PyInstaller for Tauri bundle
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
Remove-Item Env:PAPERWING_DATA -ErrorAction SilentlyContinue
Remove-Item Env:TELEGRAM_TOOLS_DATA -ErrorAction SilentlyContinue

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Run npm run setup:python first"
    exit 1
}

& .\.venv\Scripts\pip.exe install pyinstaller -q

$DistDir = Join-Path $Root "src-tauri\bin"
$SpecFile = Join-Path $Root "build\pyinstaller\telegram-backend.spec"
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null

& .\.venv\Scripts\pyinstaller.exe `
    --noconfirm `
    --clean `
    --distpath $DistDir `
    --workpath (Join-Path $Root "build\pyinstaller\work") `
    $SpecFile

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller failed with exit code $LASTEXITCODE"
}

$ExePath = Join-Path $DistDir "telegram-backend\telegram-backend.exe"
if (-not (Test-Path $ExePath)) {
    Write-Error "Backend executable not found: $ExePath"
}

Write-Host "Backend built to $DistDir\telegram-backend"
