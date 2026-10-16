@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
  echo Run Setup.bat first.
  if not defined CI pause
  exit /b 1
)
".venv\Scripts\python.exe" -B scripts\launch_windows.py spider.weibo_downloader %*
set EXIT_CODE=%ERRORLEVEL%
if not "%EXIT_CODE%"=="0" if not defined CI pause
exit /b %EXIT_CODE%
