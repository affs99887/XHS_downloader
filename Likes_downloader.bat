@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Python virtual environment not found: .venv\Scripts\python.exe
  echo Run the project setup first.
  pause
  exit /b 1
)

if not exist ".env" (
  echo Cookie file not found: .env
  echo Put COOKIES in .env before running.
  pause
  exit /b 1
)

echo Starting Xiaohongshu liked-notes downloader...
echo Output: download_files\likes
echo.
".venv\Scripts\python.exe" -m spider.download_liked_images %*
set EXIT_CODE=%ERRORLEVEL%

echo.
if "%EXIT_CODE%"=="0" (
  echo Done.
) else (
  echo Failed with exit code %EXIT_CODE%.
)
pause
exit /b %EXIT_CODE%
