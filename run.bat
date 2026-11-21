@echo off
title colors - Audio Visualizer & Strobe System
cd /d "%~dp0"
python main.py
if errorlevel 1 (
    echo.
    echo An error occurred. Make sure dependencies are installed:
    echo python -m pip install numpy pygame soundcard
    pause
)
