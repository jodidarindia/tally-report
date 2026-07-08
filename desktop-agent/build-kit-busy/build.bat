@echo off
REM ============================================================
REM   FLOWRA Busy Sync Agent - Windows One-Click Build Script
REM   Version is read automatically from flowra_busy_gui.py
REM ============================================================

setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set BUILD_LOG=%~dp0build.log
echo. > "%BUILD_LOG%"

REM --- Read APP_VERSION from flowra_busy_gui.py ---------
set APP_VER=v1.2
for /f "tokens=2 delims==" %%V in ('findstr /B "APP_VERSION" flowra_busy_gui.py') do (
    set "_LINE=%%V"
)
if defined _LINE (
    set "_LINE=!_LINE: =!"
    set "_LINE=!_LINE:"=!"
    set APP_VER=!_LINE!
)

call :both ""
call :both "============================================================"
call :both "   FLOWRA Busy Sync Agent - Build Kit (!APP_VER!)"
call :both "   Log file: %BUILD_LOG%"
call :both "============================================================"
call :both ""

REM --- 1. Locate Python -------------------------------------------------
set PYEXE=
for %%P in (py python python3) do (
    %%P -V >nul 2>&1 && set PYEXE=%%P && goto :have_python
)
:have_python
if not defined PYEXE (
    call :both "[ERROR] Python is not installed or not on PATH."
    call :both "        Install Python 3.12 from https://www.python.org/downloads/"
    call :both "        Tick 'Add Python to PATH' during install."
    goto :err
)

for /f "tokens=2 delims= " %%V in ('%PYEXE% -V 2^>^&1') do set PYVER=%%V
call :both "[1/5] Using Python: %PYEXE% (%PYVER%)"

REM --- 2. Create / refresh virtualenv -----------------------------------
if not exist ".venv\Scripts\python.exe" (
    call :both "[2/5] Creating virtual environment in .venv..."
    %PYEXE% -m venv .venv >> "%BUILD_LOG%" 2>&1 || goto :err
) else (
    call :both "[2/5] Re-using existing .venv (delete it if you switched Python versions)."
)

REM --- 3. Install dependencies ------------------------------------------
call :both "[3/5] Installing build dependencies (this may take a couple of minutes)..."
".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel >> "%BUILD_LOG%" 2>&1
if errorlevel 1 (
    call :both "[ERROR] Failed to upgrade pip / setuptools / wheel."
    call :both "        Check %BUILD_LOG% for full output."
    goto :err
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt >> "%BUILD_LOG%" 2>&1
if errorlevel 1 (
    call :both ""
    call :both "[ERROR] Pip failed to install dependencies."
    call :both "        FULL pip output is saved at %BUILD_LOG%"
    call :both "        Send that file to support@flowra.in and we'll debug it."
    call :both ""
    goto :err
)

REM --- 4. Build the executable ------------------------------------------
call :both "[4/5] Building executable with PyInstaller..."
if exist build  rmdir /s /q build  >nul 2>&1
if exist dist   rmdir /s /q dist   >nul 2>&1
".venv\Scripts\python.exe" -m PyInstaller agent.spec --clean --noconfirm >> "%BUILD_LOG%" 2>&1
if errorlevel 1 (
    call :both "[ERROR] PyInstaller failed. Full log: %BUILD_LOG%"
    goto :err
)

REM --- 5. Copy artifact -------------------------------------------------
if exist "dist\FlowraBusyAgent.exe" (
    copy /Y "dist\FlowraBusyAgent.exe" "FlowraBusyAgent_!APP_VER!.exe" >nul
    call :both ""
    call :both "============================================================"
    call :both "   BUILD SUCCESSFUL"
    call :both "============================================================"
    call :both ""
    call :both "   Output:  %~dp0FlowraBusyAgent_!APP_VER!.exe"
    for %%I in ("FlowraBusyAgent_!APP_VER!.exe") do call :both "   Size:    %%~zI bytes"
    call :both ""
    call :both "   Upload this .exe to the FLOWRA Setup page (busy channel):"
    call :both "     backend/agent_release.json         (update sha256 + size_bytes)"
    call :both "     frontend/public/agent-latest.json  (update sha256 + size_bytes)"
    call :both ""
    call :both "   First launch on a new machine may show a Windows SmartScreen"
    call :both "   warning ('Unknown publisher') - click 'More info' then"
    call :both "   'Run anyway'. Code-signing the binary will remove this."
    call :both ""
) else (
    call :both "[ERROR] Build did not produce dist\FlowraBusyAgent.exe"
    goto :err
)

pause
exit /b 0

:both
echo %~1
echo %~1>> "%BUILD_LOG%"
exit /b 0

:err
echo.
echo ============================================================
echo   BUILD FAILED - see the errors above
echo   Full log was written to: %BUILD_LOG%
echo ============================================================
echo.
pause
exit /b 1
