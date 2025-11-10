@echo off
REM ============================================================================
REM Smart Confidant - Local Development Runner (using uv)
REM Run the app directly on Windows for fast iteration
REM ============================================================================

echo ========================================
echo Smart Confidant - Local Development
echo ========================================
echo.

REM Check if uv is installed
where uv >nul 2>nul
if errorlevel 1 (
    echo ERROR: uv is not installed
    echo Install it with: pip install uv
    echo Or visit: https://docs.astral.sh/uv/
    pause
    exit /b 1
)

echo [1/2] Installing dependencies with uv...
uv pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    echo Make sure requirements.txt is present
    pause
    exit /b 1
)

echo.
echo [2/2] Starting Smart Confidant application...
echo.
echo ========================================
echo Application Starting
echo ========================================
echo.
echo Access the app at: http://localhost:8012
echo Metrics available at: http://localhost:8000/metrics
echo.
echo Press Ctrl+C to stop the application
echo ========================================
echo.

REM Check if .env file exists
if not exist ".env" (
    echo WARNING: .env file not found
    echo API models will not work without HF_TOKEN
    echo Copy .env.example to .env and add your token
    echo.
)

REM Run the application with uv
uv run --no-project python app.py

REM Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo ========================================
    echo Application stopped with error
    echo ========================================
    pause
)
