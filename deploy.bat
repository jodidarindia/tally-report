@echo off
REM Tally Reports - Windows Deployment Script
REM Usage: Double-click or run from Command Prompt

echo =========================================
echo   Tally Reports - Self-Hosted Deployment
echo =========================================
echo.

REM Check Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Docker is not installed.
    echo Visit: https://docs.docker.com/get-docker/
    pause
    exit /b 1
)

REM Check .env
if not exist .env (
    echo No .env file found. Creating from template...
    copy .env.example .env
    echo.
    echo IMPORTANT: Edit .env file with your API keys.
    echo   - EMERGENT_LLM_KEY: Required for AI features
    echo   - RESEND_API_KEY: Optional
    echo.
    pause
)

echo.
echo Building and starting services...
echo.

docker compose up -d --build

echo.
echo =========================================
echo   Deployment Complete!
echo =========================================
echo.
echo   Web App:     http://localhost
echo   Backend API: http://localhost:8001
echo.
echo   Login: Enter any email, use OTP 123456 (dev mode)
echo.
echo   To stop:  docker compose down
echo   To logs:  docker compose logs -f
echo =========================================
pause
