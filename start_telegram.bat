@echo off
:: Start Telegram Integration Server
title Orion Telegram Bot

cd /d "%~dp0"

echo.
echo ================================================
echo    Starting Orion Telegram Bot...
echo ================================================
echo.

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

python telegram_integration.py --port 8000

pause
