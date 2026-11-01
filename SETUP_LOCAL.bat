@echo off
setlocal EnableExtensions

cd /d "%~dp0"
title ARCHIVE Local Setup

echo ========================================
echo ARCHIVE local setup
echo ========================================
echo.

where py >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python launcher ^(py^) not found.
  echo Install Python 3.12 x64 from https://www.python.org/downloads/windows/
  goto :fail
)

where npm >nul 2>&1
if errorlevel 1 (
  echo ERROR: npm not found.
  echo Install Node.js LTS from https://nodejs.org/en/download
  goto :fail
)

echo [1/5] Creating Python virtual environment...
if not exist ".venv-1\Scripts\python.exe" (
  py -3.12 -m venv ".venv-1"
  if errorlevel 1 (
    echo ERROR: Python 3.12 is not installed or unavailable.
    echo Install Python 3.12 x64, enable Python Launcher, then retry.
    goto :fail
  )
) else (
  echo Existing .venv-1 found. Reusing it.
)

set "PYTHON=.venv-1\Scripts\python.exe"
set "PIP=.venv-1\Scripts\python.exe -m pip"

if not exist "%PYTHON%" (
  echo ERROR: Virtual environment was not created: "%PYTHON%"
  goto :fail
)

echo [2/5] Updating pip tooling...
%PIP% install --upgrade pip setuptools wheel
if errorlevel 1 goto :fail

echo [3/5] Installing all backend dependencies...
%PIP% install -r "arcHIVe-main\requirements.txt"
if errorlevel 1 goto :fail

echo Backend dependencies installed.

echo [4/5] Installing all frontend dependencies...
cd /d "%~dp0archive-frontend"
call npm install
if errorlevel 1 (
  echo ERROR: Frontend dependency installation failed.
  goto :fail
)
cd /d "%~dp0"

echo [5/5] Checking local environment files...
if not exist "arcHIVe-main\.env" (
  if exist "arcHIVe-main\.env.example" (
    copy /Y "arcHIVe-main\.env.example" "arcHIVe-main\.env" >nul
    echo Created arcHIVe-main\.env from .env.example.
    echo Add local values before starting the app.
  ) else (
    echo WARNING: arcHIVe-main\.env.example not found.
  )
) else (
  echo Existing arcHIVe-main\.env preserved.
)

echo.
echo ========================================
echo SETUP COMPLETE
echo ========================================
echo Run START_ALL.bat to launch backend and frontend.
echo This window stays open so logs remain visible.
echo.
pause
exit /b 0

:fail
cd /d "%~dp0"
echo.
echo ========================================
echo SETUP FAILED
echo Check error above. Fix it, then run SETUP_LOCAL.bat again.
echo ========================================
pause
exit /b 1
