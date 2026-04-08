@echo off
title FLOWRA + TallyPrime Auto-Start
echo.
echo  ====================================================
echo   FLOWRA + TallyPrime Auto-Launcher
echo  ====================================================
echo.
echo  Starting TallyPrime...

:: Adjust this path to match your TallyPrime installation
set TALLY_PATH="C:\TallyPrime\tally.exe"

if not exist %TALLY_PATH% (
    echo  [WARNING] TallyPrime not found at %TALLY_PATH%
    echo  Edit this file and set TALLY_PATH to your Tally installation.
    echo  Continuing without launching Tally...
) else (
    start "" %TALLY_PATH%
    echo  TallyPrime launched. Waiting 15 seconds for it to initialize...
    timeout /t 15 /nobreak >nul
)

echo.
echo  Starting FLOWRA Sync Agent...
cd /d %~dp0
python tally_sync_agent.py

pause
