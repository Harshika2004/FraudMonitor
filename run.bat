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

echo [1/2] Verifying database...
"%PYTHON_EXE%" database\init_db.py

echo.
echo [2/2] Starting server on http://127.0.0.1:8000 ...
echo   Web Dashboard:  http://127.0.0.1:8000/
echo   Swagger Docs:   http://127.0.0.1:8000/api/docs
echo.

"%PYTHON_EXE%" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
pause
