@echo off
title SoundClicker 2.0 - By Evanonymous
cd /d "%~dp0"

echo ===================================================
echo           SoundClicker 2.0 - By Evanonymous
echo        (Background Window & GS Position Macro)
echo ===================================================
echo Launching application...
python main.py
if %errorlevel% neq 0 (
    echo.
    echo An error occurred while running the application.
    pause
)
