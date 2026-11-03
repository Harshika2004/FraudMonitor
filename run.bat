@echo off
title Banking Transaction Monitoring System
echo ==========================================================
echo   Banking Transaction Monitoring ^& Fraud Risk Engine
echo ==========================================================
echo.

cd /d "%~dp0"
set PYTHONPATH=.

set PYTHON_EXE=backend\venv\Scripts\python.exe

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python executable not found at %PYTHON_EXE%
    echo Please create the virtual environment first.
    pause
    exit /b 1
)

:: Free port 8000 if a previous instance is still lingering
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING 2^>nul') do (
    echo [INFO] Stopping old process (PID %%a) on port 8000...
    taskkill /F /PID %%a >nul 2>&1
)

echo [1/2] Verifying database...
"%PYTHON_EXE%" database\init_db.py

echo.
echo [2/2] Launching server on http://127.0.0.1:8000 ...
echo Opening web dashboard in default browser...

:: Open browser automatically after a 2-second delay in background
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:8000/"

echo.
echo ==========================================================
echo   Web Dashboard:  http://127.0.0.1:8000/
echo   Swagger Docs:   http://127.0.0.1:8000/api/docs
echo ==========================================================
echo.
echo Server is running. Press Ctrl+C in this window to stop.
echo.

"%PYTHON_EXE%" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
pause
