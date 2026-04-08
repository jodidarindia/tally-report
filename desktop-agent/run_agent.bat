@echo off
title FLOWRA Sync Agent v6 (File-Based)
echo =============================================
echo   FLOWRA Tally Sync Agent v6 - Zero Freeze
echo =============================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download from https://python.org
    pause
    exit /b 1
)

REM Install dependencies
echo Installing dependencies...
pip install requests xmltodict python-dotenv schedule watchdog websockets -q

REM Check .env
if not exist .env (
    echo ERROR: .env file not found!
    echo Copy .env.example to .env and fill in your settings.
    pause
    exit /b 1
)

REM Create export directory
if not exist "C:\FlowraExport" mkdir "C:\FlowraExport"

echo.
echo Starting FLOWRA File-Based Sync Agent...
echo (Reads exported files from C:\FlowraExport)
echo.
python tally_sync_agent_v6.py
pause
