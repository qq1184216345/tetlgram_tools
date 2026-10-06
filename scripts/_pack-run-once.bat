@echo off
chcp 65001 >nul
set LOG=E:\project\AiProject\TelegramTools\pack-run.log
cd /d E:\project\AiProject\TelegramTools
echo ==== PACK START %DATE% %TIME% > "%LOG%"
call npm run build >> "%LOG%" 2>&1
if errorlevel 1 (
  echo ==== FRONTEND FAIL >> "%LOG%"
  exit /b 1
)
echo ==== FRONTEND OK >> "%LOG%"
call npm run build:backend >> "%LOG%" 2>&1
if errorlevel 1 (
  echo ==== BACKEND FAIL >> "%LOG%"
  exit /b 1
)
echo ==== BACKEND OK >> "%LOG%"
set CARGO_TARGET_DIR=E:\project\AiProject\TelegramTools\src-tauri\target
call npx --yes tauri build >> "%LOG%" 2>&1
if errorlevel 1 (
  echo ==== TAURI FAIL >> "%LOG%"
  exit /b 1
)
echo ==== TAURI OK >> "%LOG%"
if not exist website\downloads mkdir website\downloads
for %%F in (src-tauri\target\release\bundle\nsis\*-setup.exe) do (
  copy /Y "%%F" "website\downloads\PaperWing-0.1.0-x64-setup.exe" >> "%LOG%" 2>&1
  echo ==== COPIED %%F >> "%LOG%"
)
echo ==== PACK DONE %DATE% %TIME% >> "%LOG%"
exit /b 0
