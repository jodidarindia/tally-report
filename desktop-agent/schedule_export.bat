@echo off
REM =============================================
REM  FLOWRA Auto Export Trigger (every 20 min)
REM =============================================
REM  This script sends a tiny command to TallyPrime
REM  to trigger the FLOWRA TDL export function.
REM  It does NOT fetch data — just tells Tally to
REM  write files to C:\FlowraExport\
REM
REM  SETUP (Windows Task Scheduler):
REM    1. Win+R > taskschd.msc
REM    2. Action > Create Basic Task
REM    3. Name: "FLOWRA Auto Export"
REM    4. Trigger: Daily > Repeat every 20 minutes for 24 hours
REM    5. Action: Start a program > Browse to this .bat file
REM    6. Finish > check "Open Properties" > check "Run whether user is logged in or not"
REM
REM  NOTE: TallyPrime must be running with flowra_export.tdl loaded.

set TALLY_HOST=localhost
set TALLY_PORT=9000

REM Ensure export directory exists
if not exist "C:\FlowraExport" mkdir "C:\FlowraExport"

REM Send export trigger to Tally
curl -s -X POST "http://%TALLY_HOST%:%TALLY_PORT%" ^
  -H "Content-Type: application/xml" ^
  -d "^<ENVELOPE^>^<HEADER^>^<VERSION^>1^</VERSION^>^<TALLYREQUEST^>Action^</TALLYREQUEST^>^<TYPE^>Function^</TYPE^>^<ID^>FlowraExportAll^</ID^>^</HEADER^>^<BODY^>^<DESC^>^<FUNCTIONNAME^>FlowraExportAll^</FUNCTIONNAME^>^</DESC^>^</BODY^>^</ENVELOPE^>" ^
  --connect-timeout 5 --max-time 60 >nul 2>&1

if %errorlevel% equ 0 (
    echo %DATE% %TIME% - Export triggered successfully >> "C:\FlowraExport\_trigger_log.txt"
) else (
    echo %DATE% %TIME% - Tally not responding (is it running?) >> "C:\FlowraExport\_trigger_log.txt"
)
