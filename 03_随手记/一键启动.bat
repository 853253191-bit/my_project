@echo off
chcp 65001 >nul
cd /d "%~dp0runtime"
echo === 知识点采集 + 每日整理：一键启动 ===
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0runtime\bootstrap.ps1"
echo.
echo 窗口可关闭。若热键未生效，请确认 AutoHotkey 已安装。
pause
