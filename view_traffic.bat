@echo off
title SehatConnect - Traffic Inspector
color 0B

echo ============================================================
echo    OPENING TRAFFIC DASHBOARDS
echo ============================================================
echo.

echo [1/2] Opening ngrok live traffic inspector...
start "" http://127.0.0.1:4040

timeout /t 2 /nobreak >nul

echo [2/2] Opening your own analytics dashboard...
start "" http://127.0.0.1:5000/admin/analytics

echo.
echo Both dashboards opened in your browser.
echo.
echo NOTE: Make sure Flask + ngrok are running first!
echo       (double-click go_live.bat if not)
echo.
timeout /t 5