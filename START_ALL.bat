@echo off
setlocal
cd /d "%~dp0"

echo Stopping existing ARCHIVE processes on ports 5173 and 8765...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":5173 .*LISTENING"') do taskkill /PID %%P /F >nul 2>&1
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8765 .*LISTENING"') do taskkill /PID %%P /F >nul 2>&1

echo Starting ARCHIVE backend...
set "DATABASE_URL=postgresql://archive_app:gayojalelprince21@localhost:5432/archive"
start "ARCHIVE API" /D "%~dp0arcHIVe-main" "%~dp0.venv-1\Scripts\python.exe" -m src.phase2_runtime_api --host 127.0.0.1 --port 8765 --cors-origin http://127.0.0.1:5173

echo Starting ARCHIVE frontend...
start "ARCHIVE Frontend" cmd /k "cd /d "%~dp0archive-frontend" && npm run dev -- --host 127.0.0.1 --port 5173"

echo.
echo ARCHIVE services starting in separate windows.
echo Frontend: http://127.0.0.1:5173
echo Backend:  http://127.0.0.1:8765/api/health
exit /b 0
