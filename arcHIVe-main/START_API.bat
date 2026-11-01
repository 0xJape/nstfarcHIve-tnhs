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
start "" http://127.0.0.1:8765/map
"%PYTHON_EXE%" -m src.phase2_runtime_api --host 127.0.0.1 --port 8765
if errorlevel 1 goto :failed
exit /b 0
:failed
pause
exit /b 1
