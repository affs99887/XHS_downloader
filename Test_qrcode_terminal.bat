@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
set XHS_QR_FULL_BLOCK=1

if not exist ".venv\Scripts\python.exe" (
  echo Python virtual environment not found: .venv\Scripts\python.exe
  echo Run the project setup first.
  pause
  exit /b 1
)

echo Testing terminal QR code rendering...
echo This does not login, download, or change cookies.
echo.
".venv\Scripts\python.exe" -c "from apis.xhs_pc_login_apis import XHSLoginApi; XHSLoginApi.show_qrcode_terminal('https://www.xiaohongshu.com/login/qrcode?qr_id=test_terminal_qrcode_render_1234567890abcdef&code=test_code_1234567890abcdef'); print('QR render test complete.')"
set EXIT_CODE=%ERRORLEVEL%

echo.
if "%EXIT_CODE%"=="0" (
  echo Done.
) else (
  echo Failed with exit code %EXIT_CODE%.
)
pause
exit /b %EXIT_CODE%
