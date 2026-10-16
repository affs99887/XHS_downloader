@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set XHS_QR_FULL_BLOCK=1

if not exist ".venv\Scripts\python.exe" (
  echo Python virtual environment not found: .venv\Scripts\python.exe
  echo Run Setup.bat first.
  if not defined CI pause
  exit /b 1
)

echo Starting Xiaohongshu liked-notes downloader...
echo If COOKIES is missing or expired, scan the QR code shown in this terminal.
echo If available, a backup PNG is saved under download_files.
echo Output: download_files\likes
echo.
".venv\Scripts\python.exe" -B scripts\launch_windows.py spider.download_liked_images %*
set EXIT_CODE=%ERRORLEVEL%

echo.
if "%EXIT_CODE%"=="0" (
  echo Done.
) else (
  echo Failed with exit code %EXIT_CODE%.
)
if not defined CI pause
exit /b %EXIT_CODE%

