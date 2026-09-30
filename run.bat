@echo off
title Beat Strobe - Audio Color Strober
cd /d "%~dp0"
python main.py
if errorlevel 1 (
    echo.
    echo An error occurred. Make sure dependencies are installed:
    echo python -m pip install numpy pygame soundcard
    pause
)
