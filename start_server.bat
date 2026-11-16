@echo off
title Banking Transaction Monitoring System
cd /d "%~dp0"
echo ==============================================================
echo  Banking Transaction Monitoring ^& Fraud Risk Analysis System
echo  Running on http://127.0.0.1:8000 (and http://localhost:8000)
echo ==============================================================
echo.
backend\venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
pause
