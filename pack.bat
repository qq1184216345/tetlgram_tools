@echo off
chcp 65001 >nul
title 纸翼 Windows 打包
echo.
echo ========================================
echo  纸翼 Windows 一键打包
echo  将执行: 前端 + 无窗口后端 + NSIS 安装包
echo ========================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\pack-windows.ps1" %*
set ERR=%ERRORLEVEL%
echo.
if %ERR% neq 0 (
    echo [ERROR] 打包失败，退出码 %ERR%。请查看上方日志。
    echo 常见原因: 未装 Rust/Node、PyInstaller 卡住、杀软锁定文件
) else (
    echo [OK] 打包成功。安装包见上方路径。
)
echo.
pause
exit /b %ERR%
