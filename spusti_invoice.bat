@echo off
cd /d "%~dp0"
python invoice.py
if errorlevel 1 (
    echo.
    echo Aplikacia sa nespustila. Skontroluj Python a zavislosti:
    echo   pip install -r requirements.txt
    pause
)
