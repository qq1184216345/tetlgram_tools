@echo off
cd /d "%~dp0"
set PYTHONPATH=%CD%
if exist "%~dp0..\.venv\Scripts\python.exe" (
  "%~dp0..\.venv\Scripts\python.exe" -m license_server
) else if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" -m license_server
) else (
  python -m license_server
)
pause
