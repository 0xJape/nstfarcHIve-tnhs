@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ENV_DIR=%~dp0..\.venv-1"
set "PYTHON_EXE=%ENV_DIR%\Scripts\python.exe"
set "TEMP=%LOCALAPPDATA%\arcHIVe\tmp"
set "TMP=%TEMP%"
set "PYTHONUTF8=1"
if not exist "%TEMP%" mkdir "%TEMP%"
if not exist "%PYTHON_EXE%" (
    echo ERROR: Missing .venv-1. Run SETUP_LOCAL.bat from repository root first.
    goto :failed
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
echo.
echo RUN_SYSTEM failed. Read error above.
pause
exit /b 1
