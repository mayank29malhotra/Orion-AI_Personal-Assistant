@echo off
:: Orion AI Personal Assistant - Background Launcher
:: Starts Orion in the background without showing a window

:: Navigate to project directory
cd /d "%~dp0"

:: Start Orion in background (hidden window)
if exist "venv\Scripts\python.exe" (
    start /B "" venv\Scripts\pythonw.exe app.py
) else (
    start /B "" pythonw.exe app.py
)

echo Orion AI Assistant started in background.
timeout /t 2 > nul
