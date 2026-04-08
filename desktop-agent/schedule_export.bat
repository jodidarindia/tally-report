@echo off
REM FLOWRA Scheduled Export Trigger
REM ================================
REM Add this to Windows Task Scheduler to auto-trigger Tally export.
REM
REM Task Scheduler Setup:
REM   1. Open Task Scheduler (taskschd.msc)
REM   2. Create Basic Task > Name: "FLOWRA Tally Export"
REM   3. Trigger: Daily or On a schedule (e.g., every 30 minutes)
REM   4. Action: Start a program > Browse to this .bat file
REM   5. Make sure "Run whether user is logged in or not" is checked
REM
REM This script writes a trigger file that Tally's TDL watches for,
REM or you can manually press 'F' in Tally Gateway after loading the TDL.

echo %DATE% %TIME% > "C:\FlowraExport\_trigger_export.txt"
echo Export trigger written. Tally will pick this up if TDL is loaded.
