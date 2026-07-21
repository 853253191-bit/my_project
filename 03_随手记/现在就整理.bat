@echo off
chcp 65001 >nul
cd /d "%~dp0runtime"
echo === 现在就整理暂存 ===
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0runtime\run_digest_wrapper.ps1"
set EXITCODE=%ERRORLEVEL%
echo.
if %EXITCODE%==0 (
  echo 完成。已整理知识点并归档其余暂存 txt；若无内容则已跳过。
) else (
  echo 失败，退出码 %EXITCODE%。失败项不会被删除，请查看 runtime\logs 日志。
)
echo.
pause
exit /b %EXITCODE%
