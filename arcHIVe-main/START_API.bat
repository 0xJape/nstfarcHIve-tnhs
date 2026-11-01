@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHON_EXE=%~dp0..\.venv-1\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
	echo ERROR: Run SETUP_LOCAL.bat from repository root first.
	goto :failed
)
if not exist "%~dp0.env" (
	echo ERROR: Missing arcHIVe-main\.env.
	echo Copy .env.example to .env and set ARCHIVE_ADMIN_USERNAME and ARCHIVE_ADMIN_PASSWORD.
	goto :failed
)
start "ARCHIVE API" /D "%~dp0" cmd /k ""%PYTHON_EXE%" -m src.phase2_runtime_api --host 127.0.0.1 --port 8765"
for /l %%N in (1,1,20) do (
	curl.exe -fsS http://127.0.0.1:8765/api/health >nul 2>&1 && goto ready
	timeout /t 1 /nobreak >nul
)
echo ERROR: API did not become ready. Check ARCHIVE API window.
pause
exit /b 1
:ready
start "" http://127.0.0.1:8765/map
exit /b 0
:failed
echo.
echo ARCHIVE API failed to start. Keep this window open and read the error above.
pause
exit /b 1
