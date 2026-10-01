@echo off
REM ============================================================
REM  SehatConnect - Auto Backup Script
REM  Creates a timestamped backup of the entire project
REM ============================================================

setlocal

REM Project folder
set PROJECT=%USERPROFILE%\Desktop\sehatconnect
set BACKUP_DIR=%PROJECT%\backups

REM Create backups folder if missing
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"

REM Timestamp
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set dt=%%a
set STAMP=%dt:~0,4%%dt:~4,2%%dt:~6,2%_%dt:~8,2%%dt:~10,2%%dt:~12,2%

REM Backup folder for this run
set RUN_DIR=%BACKUP_DIR%\backup_%STAMP%
mkdir "%RUN_DIR%" 2>nul

REM Copy important files
xcopy "%PROJECT%\*.py"            "%RUN_DIR%\" /Y /Q >nul
xcopy "%PROJECT%\*.json"          "%RUN_DIR%\" /Y /Q >nul
xcopy "%PROJECT%\*.txt"           "%RUN_DIR%\" /Y /Q >nul
xcopy "%PROJECT%\*.md"            "%RUN_DIR%\" /Y /Q >nul
xcopy "%PROJECT%\*.bat"           "%RUN_DIR%\" /Y /Q >nul
xcopy "%PROJECT%\templates"       "%RUN_DIR%\templates\" /E /I /Y /Q >nul
xcopy "%PROJECT%\static"          "%RUN_DIR%\static\"    /E /I /Y /Q >nul

REM Write timestamp
echo Backup created: %date% %time% > "%RUN_DIR%\_backup_info.txt"

REM Log
echo [%date% %time%] Backup created: %RUN_DIR% >> "%BACKUP_DIR%\_backup_log.txt"

REM Keep only last 20 backups (delete older)
for /f "skip=20 delims=" %%d in ('dir "%BACKUP_DIR%\backup_*" /b /ad /o-d 2^>nul') do (
    rd /s /q "%BACKUP_DIR%\%%d"
)

endlocal
exit /b 0