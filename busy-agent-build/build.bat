@echo off
REM ═══════════════════════════════════════════════════════════
REM   FLOWRA Busy Sync Agent — One-click Windows build script
REM   Run this on a Windows 10/11 machine. Produces:
REM     dist\FLOWRA_Busy_Agent.exe       (single-file executable)
REM     installer\FLOWRA_Busy_Agent_Setup.exe (Inno Setup installer)
REM ═══════════════════════════════════════════════════════════

echo.
echo ====================================================
echo   FLOWRA Busy Sync Agent - Windows Build
echo ====================================================
echo.

REM ── 1. Verify Python is installed
where python >nul 2>nul
if errorlevel 1 (
    echo [FAIL] Python is not installed or not in PATH.
    echo        Download Python 3.9+ from https://www.python.org/downloads/
    echo        IMPORTANT: tick "Add Python to PATH" during install.
    pause
    exit /b 1
)
python --version

REM ── 2. Create / activate virtual environment
if not exist .venv (
    echo.
    echo [1/4] Creating Python virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate.bat

REM ── 3. Install dependencies
echo.
echo [2/4] Installing dependencies (pyodbc, requests, pyinstaller)...
python -m pip install --upgrade pip --quiet
python -m pip install pyodbc==5.1.0 requests==2.32.3 pyinstaller==6.10.0 --quiet
if errorlevel 1 (
    echo [FAIL] Failed to install dependencies.
    echo        If pyodbc fails, install Microsoft Access Database Engine 2016 64-bit:
    echo        https://www.microsoft.com/en-us/download/details.aspx?id=54920
    pause
    exit /b 1
)

REM ── 4. Build single-file .exe with PyInstaller
echo.
echo [3/4] Compiling single-file executable...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

pyinstaller flowra-busy-agent.spec --clean --noconfirm
if errorlevel 1 (
    echo [FAIL] PyInstaller build failed.
    pause
    exit /b 1
)

REM ── 5. Optional: build Inno Setup installer if Inno Setup is installed
echo.
echo [4/4] Building Windows installer with Inno Setup...
set INNO_SETUP="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist %INNO_SETUP% (
    %INNO_SETUP% installer.iss
    if errorlevel 1 (
        echo [WARN] Inno Setup compile failed - .exe is still available in dist\
    ) else (
        echo.
        echo ====================================================
        echo   SUCCESS!
        echo ====================================================
        echo   Standalone EXE: dist\FLOWRA_Busy_Agent.exe
        echo   Installer:      installer\FLOWRA_Busy_Agent_Setup.exe
        echo ====================================================
    )
) else (
    echo [INFO] Inno Setup not found - skipping installer build.
    echo        To create a friendly installer, download from:
    echo        https://jrsoftware.org/isdl.php  (free)
    echo        Then re-run build.bat
    echo.
    echo ====================================================
    echo   SUCCESS!  Standalone EXE built.
    echo ====================================================
    echo   Output: dist\FLOWRA_Busy_Agent.exe
    echo ====================================================
)

echo.
pause
