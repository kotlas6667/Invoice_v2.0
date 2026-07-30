@echo off
cd /d "%~dp0"
python invoice.py
if errorlevel 1 (
    echo.
    echo The application failed to start. Check Python and dependencies:
    echo   pip install -r requirements.txt
    pause
)
