@echo off
title Virtual Whiteboard Using Hand Gestures
echo Starting Virtual Whiteboard...
python main.py
if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)
