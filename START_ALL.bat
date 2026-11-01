@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ROOT=%~dp0"
set "BACKEND=%ROOT%arcHIVe-main"
set "FRONTEND=%ROOT%archive-frontend"
set "PYTHON=%ROOT%.venv-1\Scripts\python.exe"

if not exist "%PYTHON%" (
	echo ERROR: Python environment missing: "%PYTHON%"
	pause
	exit /b 1
)
if not exist "%BACKEND%\src\phase2_runtime_api.py" (
	echo ERROR: Backend not found: "%BACKEND%"
	pause
	exit /b 1
)
if not exist "%FRONTEND%\package.json" (
	echo ERROR: Frontend not found: "%FRONTEND%"
	pause
	exit /b 1
)

echo Stopping existing ARCHIVE services...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":5173 .*LISTENING"') do taskkill /PID %%P /F >nul 2>&1
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8765 .*LISTENING"') do taskkill /PID %%P /F >nul 2>&1

echo Starting backend API...
start "ARCHIVE API" /D "%BACKEND%" "%ComSpec%" /D /K ""%PYTHON%" -m src.phase2_runtime_api --host 127.0.0.1 --port 8765 --cors-origin http://127.0.0.1:5173"

echo Waiting for backend health endpoint...
for /l %%N in (1,1,20) do (
	curl.exe -fsS http://127.0.0.1:8765/api/health >nul 2>&1 && goto backend_ready
	timeout /t 1 /nobreak >nul
)
echo ERROR: Backend did not become ready. Check ARCHIVE API window.
echo Frontend will not start until backend is fixed.
pause
exit /b 1

:backend_ready
echo Backend ready: http://127.0.0.1:8765/api/health
echo Starting frontend...
start "ARCHIVE Frontend" /D "%FRONTEND%" "%ComSpec%" /D /K "npm run dev -- --host 127.0.0.1 --port 5173"

timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:5173
echo.
echo ARCHIVE started.
echo Frontend: http://127.0.0.1:5173
echo Backend:  http://127.0.0.1:8765/api/health
exit /b 0
