@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ENV_DIR=%LOCALAPPDATA%\arcHIVe\py314"
set "PYTHON_EXE=%ENV_DIR%\Scripts\python.exe"
set "TEMP=%LOCALAPPDATA%\arcHIVe\tmp"
set "TMP=%TEMP%"
set "PYTHONUTF8=1"
if not exist "%TEMP%" mkdir "%TEMP%"
if not exist "%PYTHON_EXE%" (
    py -3.14 -c "import sys,struct; assert sys.version_info[:2]==(3,14); assert sys.version_info[:3]>=(3,14,5); assert struct.calcsize('P')*8==64" >nul 2>&1
    if errorlevel 1 goto :failed
    if not exist "%LOCALAPPDATA%\arcHIVe" mkdir "%LOCALAPPDATA%\arcHIVe"
    py -3.14 -m venv "%ENV_DIR%"
    if errorlevel 1 goto :failed
)
"%PYTHON_EXE%" -m pip install --disable-pip-version-check --no-cache-dir --upgrade pip setuptools wheel
if errorlevel 1 goto :failed
"%PYTHON_EXE%" -m pip install --disable-pip-version-check --no-cache-dir --only-binary=:all: -r requirements.txt
if errorlevel 1 goto :failed
"%PYTHON_EXE%" scripts\verify_package.py
if errorlevel 1 goto :failed
exit /b 0
:failed
pause
exit /b 1
