@echo off
REM ============================================================
REM  SehatConnect - Start Auto Backup (every 20 minutes)
REM ============================================================

title SehatConnect Auto-Backup (Running)
color 0E

cd /d %~dp0

echo ============================================================
echo   SEHATCONNECT AUTO-BACKUP
echo   Runs every 20 minutes in this window
echo   KEEP THIS WINDOW OPEN while you work
echo   Press Ctrl+C to stop
echo ============================================================
echo.

:loop
echo [%date% %time%] Running backup...
call auto_backup.bat

echo [%date% %time%] Next backup in 20 minutes.
echo.

REM 1200 seconds = 20 minutes
timeout /t 1200 /nobreak >nul

goto loop