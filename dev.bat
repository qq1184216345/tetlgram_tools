@echo off
chcp 65001 >nul
title 纸翼 Dev
echo.
echo ========================================
echo  纸翼 开发启动
echo  详细说明见: 启动说明.txt
echo ========================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev.ps1" %*
if errorlevel 1 (
    echo.
    echo [ERROR] 启动失败，请查看上方错误信息。
    echo 常见原因: 未 npm install / 未 setup:python / 授权云或端口被占用
    pause
)
