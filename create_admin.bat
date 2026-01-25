@echo off
echo ========================================
echo   CSFloat Bot - Create Admin User
echo ========================================
echo.

REM Check virtual environment
if not exist venv (
    echo ERROR: Virtual environment not found!
    echo Please run setup.bat first
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run admin creation script
python create_admin.py

pause
