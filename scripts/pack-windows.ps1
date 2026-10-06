# 纸翼 — Windows 一键打包（NSIS 安装包）
# 用法:
#   .\pack.bat
#   powershell -ExecutionPolicy Bypass -File scripts/pack-windows.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/pack-windows.ps1 -SkipSetup
#   powershell -ExecutionPolicy Bypass -File scripts/pack-windows.ps1 -SkipBackend   # 仅重打 Tauri（后端 exe 已存在时）
#
# 产物:
#   src-tauri\target\release\bundle\nsis\纸翼_x.y.z_x64-setup.exe
#   website\downloads\PaperWing-x.y.z-x64-setup.exe  （ASCII 文件名，便于官网挂载）

param(
    [switch]$SkipSetup,
    [switch]$SkipBackend,
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

# 避免本机刚跑过 dev.bat 时 PAPERWING_DATA 指到源码 data，污染发版/冒烟
Remove-Item Env:PAPERWING_DATA -ErrorAction SilentlyContinue
Remove-Item Env:TELEGRAM_TOOLS_DATA -ErrorAction SilentlyContinue

function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "==> $msg" -ForegroundColor Cyan
}

function Assert-Command([string]$name) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "未找到命令: $name。请先安装并加入 PATH。"
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " 纸翼 Windows 一键打包" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "项目目录: $Root"

Assert-Command "node"
Assert-Command "npm"
Assert-Command "rustc"
Assert-Command "cargo"

$pkg = Get-Content (Join-Path $Root "package.json") -Raw | ConvertFrom-Json
$version = [string]$pkg.version
if (-not $version) { $version = "0.0.0" }
Write-Host "版本: $version"

$envProd = Join-Path $Root ".env.production"
if (-not (Test-Path $envProd)) {
    throw "缺少 .env.production，请先配置 VITE_LICENSE_API_BASE=https://你的域名"
}
$licenseBase = (Get-Content $envProd | Where-Object { $_ -match '^\s*VITE_LICENSE_API_BASE\s*=' } | Select-Object -First 1)
if (-not $licenseBase -or $licenseBase -match 'example\.com|127\.0\.0\.1|localhost') {
    Write-Host "[WARN] .env.production 中的授权地址可能不是生产域名:" -ForegroundColor Yellow
    Write-Host "       $licenseBase" -ForegroundColor Yellow
} else {
    Write-Host "授权云: $licenseBase"
}

# 固定本地 target，避免沙箱/临时目录导致打包异常
$env:CARGO_TARGET_DIR = Join-Path $Root "src-tauri\target"
Write-Host "CARGO_TARGET_DIR=$($env:CARGO_TARGET_DIR)"

if (-not (Test-Path (Join-Path $Root "node_modules"))) {
    Write-Step "npm install"
    npm install
    if ($LASTEXITCODE -ne 0) { throw "npm install 失败" }
}

if (-not $SkipSetup) {
    Write-Step "准备 Python 虚拟环境"
    npm run setup:python
    if ($LASTEXITCODE -ne 0) { throw "setup:python 失败" }
}

if (-not $SkipFrontend) {
    Write-Step "构建前端 (vite production)"
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "前端 build 失败" }
}

if (-not $SkipBackend) {
    Write-Step "打包本地后端 (PyInstaller，无控制台窗口)"
    npm run build:backend
    if ($LASTEXITCODE -ne 0) { throw "build:backend 失败" }
} else {
    $backendExe = Join-Path $Root "src-tauri\bin\telegram-backend\telegram-backend.exe"
    if (-not (Test-Path $backendExe)) {
        throw "未找到内嵌后端: $backendExe 。请去掉 -SkipBackend 重新打包。"
    }
    Write-Host "跳过后端打包，使用已有: $backendExe"
}

Write-Step "Tauri NSIS 打包（beforeBuildCommand 会再跑一次前端，属正常）"
# 不经 npm 传参，避免 --bundles 被 npm 吞掉
npx --yes tauri build
if ($LASTEXITCODE -ne 0) { throw "tauri build 失败" }

$nsisDir = Join-Path $env:CARGO_TARGET_DIR "release\bundle\nsis"
$setup = Get-ChildItem -LiteralPath $nsisDir -Filter "*-setup.exe" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1

if (-not $setup) {
    throw "未找到 NSIS 安装包，请检查: $nsisDir"
}

$downloads = Join-Path $Root "website\downloads"
New-Item -ItemType Directory -Force -Path $downloads | Out-Null
$asciiName = "PaperWing-$version-x64-setup.exe"
$asciiPath = Join-Path $downloads $asciiName
Copy-Item -LiteralPath $setup.FullName -Destination $asciiPath -Force

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " 打包完成" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ("安装包: {0}  ({1:N1} MB)" -f $setup.FullName, ($setup.Length / 1MB))
Write-Host ("官网用: {0}" -f $asciiPath)
Write-Host ""
Write-Host "下一步（可选）:"
Write-Host "  1. 本机安装冒烟：登录授权云、连 Telegram"
Write-Host "  2. 上传到服务器 /opt/paperwing/website/downloads/"
Write-Host "  3. 更新 website/assets/config.js 的 downloadUrl"
Write-Host "  4. 管理后台「版本」Tab 同步版本号与下载地址"
Write-Host ""
