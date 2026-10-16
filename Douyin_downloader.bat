@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1

if not exist ".venv\Scripts\python.exe" (
  echo Python virtual environment not found: .venv\Scripts\python.exe
  echo Run Setup.bat first.
  if not defined CI pause
  exit /b 1
)

echo Starting Douyin downloader...
echo Output: download_files\douyin
echo Login command: Douyin_downloader.bat login
echo.
".venv\Scripts\python.exe" -B scripts\launch_windows.py spider.douyin_downloader %*
set EXIT_CODE=%ERRORLEVEL%

echo.
if "%EXIT_CODE%"=="0" (
  echo Done.
) else (
  echo Failed with exit code %EXIT_CODE%.
)
if not defined CI pause
exit /b %EXIT_CODE%
