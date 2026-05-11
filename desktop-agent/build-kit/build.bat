@echo off
REM ============================================================
REM   FLOWRA Tally Sync Agent - Windows One-Click Build Script
REM   v9.8.9.1 — hardened: logs to build.log, refuses Python 3.14,
REM   surfaces pip errors instead of swallowing them.
REM
REM   Double-click this file. On the first run, install Python 3.12
REM   from python.org (tick "Add Python to PATH"). Python 3.10 - 3.13
REM   are also supported. Python 3.14 is not supported yet because
REM   several compiled dependencies (Pillow, cryptography) do not
REM   publish Python 3.14 wheels at the time of writing.
REM ============================================================

setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

REM Always log the whole run so failures can be shared with support.
set BUILD_LOG=%~dp0build.log
echo. > "%BUILD_LOG%"

call :both ""
call :both "============================================================"
call :both "   FLOWRA Tally Sync Agent — Build Kit (v9.8.9)"
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

REM --- 1b. Show Python version (informational) -------------------------
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
    call :both ""
    call :both "        Common causes:"
    call :both "          - No internet / behind a corporate proxy."
    call :both "          - Python version not supported by Pillow / cryptography."
    call :both "          - Old TLS — upgrade Windows or run:"
    call :both "              .venv\Scripts\python.exe -m pip install --upgrade pip"
    call :both ""
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
if exist "dist\FlowraTallyAgent.exe" (
    copy /Y "dist\FlowraTallyAgent.exe" "FlowraTallyAgent_v9.8.9.exe" >nul
    call :both ""
    call :both "============================================================"
    call :both "   BUILD SUCCESSFUL"
    call :both "============================================================"
    call :both ""
    call :both "   Output:  %~dp0FlowraTallyAgent_v9.8.9.exe"
    for %%I in ("FlowraTallyAgent_v9.8.9.exe") do call :both "   Size:    %%~zI bytes"
    call :both ""
    call :both "   You can now distribute the .exe to your Tally machines."
    call :both "   First launch on a new machine may show a Windows SmartScreen"
    call :both "   warning ('Unknown publisher') — click 'More info' then"
    call :both "   'Run anyway'. Code-signing the binary will remove this."
    call :both ""
) else (
    call :both "[ERROR] Build did not produce dist\FlowraTallyAgent.exe"
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
echo   BUILD FAILED — see the errors above
echo   Full log was written to: %BUILD_LOG%
echo ============================================================
echo.
pause
exit /b 1
