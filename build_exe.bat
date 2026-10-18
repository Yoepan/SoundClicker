@echo off
title Build SoundClicker 2.2.0 EXE
cd /d "%~dp0"

echo ===================================================
echo         Building SoundClicker 2.2.0 to .exe
echo ===================================================
pyinstaller --noconfirm --onedir --windowed --icon="icon.ico" --name "SoundClicker" --collect-all customtkinter --collect-all proctap --exclude-module matplotlib --exclude-module pandas --exclude-module lxml main.py
if %errorlevel% neq 0 (
    echo.
    echo Build failed.
    pause
    exit /b %errorlevel%
)

copy /y icon.ico dist\SoundClicker\ >nul 2>&1
copy /y recorded_splash.wav dist\SoundClicker\ >nul 2>&1
copy /y splash_sample.wav dist\SoundClicker\ >nul 2>&1
copy /y test_beep.wav dist\SoundClicker\ >nul 2>&1

echo.
echo Build completed successfully!
echo Output directory: dist\SoundClicker\SoundClicker.exe
pause
