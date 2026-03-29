@echo off
REM DSS Setup Script for Windows
REM Run this once to install all dependencies before launching the DSS Electron app.

echo.
echo === DSS (Distributed Storage System) - Setup ===
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download it from https://www.python.org/downloads/ and re-run this script.
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed or not in PATH.
    echo Download it from https://nodejs.org/ and re-run this script.
    pause
    exit /b 1
)

echo Installing Python dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
echo   Python dependencies installed.
echo.

echo Installing UI dependencies...
cd ui
call npm install --silent
cd ..
echo   UI dependencies installed.

echo Installing Electron dependencies...
cd electron
call npm install --silent
cd ..
echo   Electron dependencies installed.

echo.
echo === Setup complete! ===
echo.
echo To launch DSS:
echo   1. Start the UI:     cd ui ^&^& npm run dev
echo   2. Launch Electron:  cd electron ^&^& npm start
echo.
pause
