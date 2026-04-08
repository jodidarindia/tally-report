@echo off
title FLOWRA Tally Sync Agent
echo.
echo  ====================================================
echo   FLOWRA Tally Sync Agent v4 (Batch Mode)
echo   Organize. Automate. Accelerate.
echo  ====================================================
echo.

cd /d %~dp0

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python is not installed or not in PATH.
    echo  Download from: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: Check/install dependencies
echo  Checking dependencies...
pip install -q -r requirements.txt >nul 2>&1

:: Start the sync agent
echo  Starting sync agent...
echo.
python tally_sync_agent.py

if errorlevel 1 (
    echo.
    echo  [ERROR] Agent stopped with an error.
    echo  Check tally_sync_agent.log for details.
    echo.
    pause
)
