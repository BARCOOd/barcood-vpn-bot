@echo off
title BARCOOD VPN Bot
echo ========================================
echo   BARCOOD VPN Bot - Windows Launcher
echo ========================================
echo.

REM --- Check Python ---
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed!
    echo.
    echo 1. Go to https://www.python.org/downloads/
    echo 2. Download and install Python
    echo 3. IMPORTANT: tick "Add Python to PATH" during install
    echo 4. Run this file again
    echo.
    pause
    exit /b 1
)

REM --- Install libraries ---
echo [1/3] Installing libraries...
python -m pip install -r requirements.txt --quiet --disable-pip-version-warning
if errorlevel 1 (
    echo [ERROR] Library installation failed. Check your internet.
    pause
    exit /b 1
)

REM --- Health check ---
echo.
echo [2/3] Checking setup...
python check_setup.py
if errorlevel 1 (
    echo.
    echo [ERROR] Setup problem found. Read the red lines above.
    pause
    exit /b 1
)

REM --- Run bot ---
echo.
echo [3/3] Starting bot... (press Ctrl+C to stop)
echo.
python main.py

echo.
echo Bot stopped.
pause
