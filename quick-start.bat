@echo off

REM Quick start without checks (for advanced users)

if not exist venv\Scripts\activate.bat (
    echo Please run setup.bat first
    timeout /t 3
    exit /b 1
)

call venv\Scripts\activate.bat
python main.py
