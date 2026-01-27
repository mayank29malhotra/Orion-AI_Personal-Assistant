@echo off
:: Start WhatsApp Integration Server
title Orion WhatsApp Server

cd /d "%~dp0"

echo.
echo ================================================
echo    Starting Orion WhatsApp Integration...
echo ================================================
echo.

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

python whatsapp_integration.py

pause
