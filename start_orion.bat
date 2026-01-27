@echo off
:: Orion AI Personal Assistant - Quick Launcher
:: Double-click this file to start Orion

title Orion AI Assistant
echo.
echo ================================================
echo    Starting Orion AI Personal Assistant...
echo ================================================
echo.

:: Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    echo [*] Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [!] No virtual environment found. Using system Python...
)

:: Navigate to project directory
cd /d "%~dp0"

:: Start Orion
echo [*] Launching Orion...
echo.
python app.py

:: Keep window open if there's an error
if errorlevel 1 (
    echo.
    echo ================================================
    echo    Error occurred! Press any key to exit...
    echo ================================================
    pause > nul
)
