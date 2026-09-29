@echo off
title SehatConnect - GO LIVE
color 0A

echo ============================================================
echo    SEHATCONNECT PESHAWAR - GO LIVE
echo    Starting Flask + ngrok + opening browsers...
echo ============================================================
echo.

REM ---- Check Python ----
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install from python.org
    pause
    exit /b
)
echo [OK] Python detected.

REM ---- Check Flask ----
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing Flask...
    pip install flask
)
echo [OK] Flask ready.

REM ---- Check ngrok.exe ----
if not exist ngrok.exe (
    echo [ERROR] ngrok.exe not found in this folder!
    echo Download from https://ngrok.com/download
    pause
    exit /b
)
echo [OK] ngrok.exe found.

REM ---- Check data files ----
if not exist doctors.json echo [] > doctors.json
if not exist appointments.json echo [] > appointments.json
if not exist analytics.json echo {} > analytics.json
echo [OK] Data files ready.

echo.
echo ============================================================
echo    Starting Flask and ngrok in separate windows...
echo    KEEP BOTH WINDOWS OPEN while using the site.
echo ============================================================
echo.

REM ---- Start Flask in a new window ----
start "SehatConnect - Flask" cmd /k "cd /d %~dp0 && python app.py"

REM ---- Wait 3 seconds for Flask to start ----
timeout /t 3 /nobreak >nul

REM ---- Start ngrok in another window ----
start "SehatConnect - ngrok" cmd /k "cd /d %~dp0 && ngrok http 5000"

REM ---- Wait 4 seconds for ngrok to boot ----
timeout /t 4 /nobreak >nul

REM ---- Open browsers ----
start "" http://127.0.0.1:5000
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:4040

echo.
echo ============================================================
echo    ALL STARTED!
echo.
echo    1. Flask window  - keep open
echo    2. ngrok window  - copy public URL from it
echo    3. Browser tab 1 - your site (local)
echo    4. Browser tab 2 - TRAFFIC INSPECTOR (live requests)
echo.
echo    To view analytics: open
echo    http://127.0.0.1:5000/admin/analytics
echo ============================================================
echo.
echo You may close this launcher window now.
timeout /t 10