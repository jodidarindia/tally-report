@echo off
REM ============================================================
REM   FLOWRA Tally Sync Agent — Windows One-Click Build Script
REM   Double-click this file on a Windows machine that has
REM   Python 3.10+ installed. It will:
REM     1. Create a clean local virtual environment (.venv)
REM     2. Install the build + runtime dependencies
REM     3. Run PyInstaller to produce dist\FlowraTallyAgent.exe
REM     4. Copy the .exe next to this script for convenience
REM ============================================================

setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo   FLOWRA Tally Sync Agent — Build Kit (v9.8.9)
echo ============================================================
echo.

REM --- 1. Locate Python -------------------------------------------------
set PYEXE=
for %%P in (py python python3) do (
    %%P -V >nul 2>&1 && set PYEXE=%%P && goto :have_python
)
:have_python
if not defined PYEXE (
    echo [ERROR] Python is not installed or not on PATH.
    echo         Download Python 3.10+ from https://www.python.org/downloads/
    echo         Make sure to tick "Add Python to PATH" during install.
    pause
    exit /b 1
)
echo [1/5] Using Python: %PYEXE%
%PYEXE% -V

REM --- 2. Create / refresh virtualenv -----------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [2/5] Creating virtual environment in .venv...
    %PYEXE% -m venv .venv || goto :err
) else (
    echo [2/5] Re-using existing .venv
)

REM --- 3. Install dependencies ------------------------------------------
echo [3/5] Installing build dependencies (this may take a couple of minutes)...
".venv\Scripts\python.exe" -m pip install --upgrade pip setuptools wheel >nul || goto :err
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :err

REM --- 4. Build the executable ------------------------------------------
echo [4/5] Building executable with PyInstaller...
if exist build  rmdir /s /q build
if exist dist   rmdir /s /q dist
".venv\Scripts\python.exe" -m PyInstaller agent.spec --clean --noconfirm || goto :err

REM --- 5. Copy artifact -------------------------------------------------
if exist "dist\FlowraTallyAgent.exe" (
    copy /Y "dist\FlowraTallyAgent.exe" "FlowraTallyAgent_v9.8.9.exe" >nul
    echo.
    echo ============================================================
    echo   BUILD SUCCESSFUL
    echo ============================================================
    echo.
    echo   Output:  %~dp0FlowraTallyAgent_v9.8.9.exe
    for %%I in ("FlowraTallyAgent_v9.8.9.exe") do echo   Size:    %%~zI bytes
    echo.
    echo   You can now distribute the .exe to your Tally machines.
    echo   First launch on a new machine may show a Windows SmartScreen
    echo   warning ("Unknown publisher") — click "More info" then
    echo   "Run anyway". Code-signing the binary will remove this.
    echo.
) else (
    echo [ERROR] Build did not produce dist\FlowraTallyAgent.exe
    goto :err
)

pause
exit /b 0

:err
echo.
echo ============================================================
echo   BUILD FAILED — see the errors above
echo ============================================================
echo.
pause
exit /b 1
