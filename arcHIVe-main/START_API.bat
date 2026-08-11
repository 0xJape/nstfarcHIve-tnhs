@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ARCHIVE_ADMIN_USERNAME=archive1hiv"
set "ARCHIVE_ADMIN_PASSWORD=hivprotect"
set "PYTHON_EXE=%LOCALAPPDATA%\arcHIVe\py314\Scripts\python.exe"
if not exist "%PYTHON_EXE%" goto :failed
start "" http://127.0.0.1:8765/map
"%PYTHON_EXE%" -m src.phase2_runtime_api --host 127.0.0.1 --port 8765
if errorlevel 1 goto :failed
exit /b 0
:failed
pause
exit /b 1
