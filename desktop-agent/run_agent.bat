@echo off
echo Starting Tally Desktop Sync Agent...
echo.

cd /d %~dp0
python tally_sync_agent.py

if errorlevel 1 (
    echo.
    echo Error: Failed to start agent
    echo Press any key to exit...
    pause > nul
)
