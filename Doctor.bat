@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
  echo Run Setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -B scripts\launch_windows.py --doctor
set EXIT_CODE=%ERRORLEVEL%
if /i not "%~1"=="--no-pause" pause
exit /b %EXIT_CODE%
