@echo off
title SehatConnect - Doctor Appointment System
color 0A

echo ============================================================
echo           SEHATCONNECT PESHAWAR
echo        Doctor Appointment System
echo ============================================================
echo.

REM ---- Check Python ----
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python from https://python.org
    pause
    exit /b
)
echo [OK] Python detected.

REM ---- Check Flask ----
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Flask not found. Installing...
    pip install flask
    if errorlevel 1 (
        echo [ERROR] Failed to install Flask.
        pause
        exit /b
    )
)
echo [OK] Flask ready.

REM ---- Check data files ----
if not exist doctors.json echo [] > doctors.json
if not exist appointments.json echo [] > appointments.json
echo [OK] Data files ready.

echo.
echo ============================================================
echo   Starting server at: http://127.0.0.1:5000
echo   Press Ctrl+C in this window to STOP the server.
echo ============================================================
echo.

REM ---- Open browser after 2 seconds ----
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:5000"

REM ---- Start Flask ----
python app.py

pause