@echo off
setlocal
pushd "%~dp0.."

if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else (
    set "PY=python"
)

%PY% -c "import sys; print('[tw-road-carbon] Local Engine Launcher'); sys.exit(0)"
%PY% -c "import fastapi, uvicorn, openpyxl, playwright" 2>nul
if errorlevel 1 (
    echo [Setup] Installing Python dependencies and Chromium...
    if not exist ".venv\Scripts\python.exe" (
        python -m venv .venv
        set "PY=.venv\Scripts\python.exe"
    )
    %PY% -m pip install -r engine\requirements.txt
    %PY% -m playwright install chromium
)

if not "%~1"=="" (
    echo [CLI Batch Mode] Processing: "%~1"
    %PY% -m engine.batch_cli "%~1"
    popd
    pause
    exit /b 0
)

echo.
echo [Ready] Local server starting at http://127.0.0.1:8787
echo Keep this window open while using the web calculator.
echo Press Ctrl+C to stop.
echo.
%PY% -m uvicorn engine.local_server:app --host 127.0.0.1 --port 8787
popd
pause
