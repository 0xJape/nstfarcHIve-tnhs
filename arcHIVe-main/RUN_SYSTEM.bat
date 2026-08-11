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
"%PYTHON_EXE%" -m src.run_phase2_system --config spatiotemporal_config.json
if errorlevel 1 goto :failed
set "RUN_DIR="
for /f "usebackq delims=" %%I in ("outputs\latest_phase2_run.txt") do set "RUN_DIR=%%I"
if defined RUN_DIR (
    if exist "%RUN_DIR%\arcHIVe_Phase2_SpatioTemporal_GIS_Report.html" start "" "%RUN_DIR%\arcHIVe_Phase2_SpatioTemporal_GIS_Report.html"
    if exist "%RUN_DIR%\maps\arcHIVe_Region_XII_Interactive_Forecast_Map.html" start "" "%RUN_DIR%\maps\arcHIVe_Region_XII_Interactive_Forecast_Map.html"
    start "" "%RUN_DIR%"
)
exit /b 0
:failed
pause
exit /b 1
