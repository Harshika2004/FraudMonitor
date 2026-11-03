# Banking Transaction Monitoring - One-Click Launcher for PowerShell
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Banking Transaction Monitoring & Fraud Risk Engine   " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir
$env:PYTHONPATH = "."

$PythonExe = Join-Path $ScriptDir "backend\venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] Virtual environment python.exe not found at $PythonExe" -ForegroundColor Red
    Write-Host "Please set up the virtual environment first." -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "[1/2] Verifying database..." -ForegroundColor Green
& $PythonExe database\init_db.py

Write-Host ""
Write-Host "[2/2] Starting FastAPI & Uvicorn Web Server..." -ForegroundColor Green
Write-Host "  Web App:    http://127.0.0.1:8000/" -ForegroundColor Yellow
Write-Host "  API Docs:   http://127.0.0.1:8000/api/docs" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop the server." -ForegroundColor Gray
Write-Host ""

& $PythonExe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
