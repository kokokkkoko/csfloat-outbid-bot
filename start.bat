@echo off
echo ========================================
echo      CSFloat Bot - Starting
echo ========================================
echo.

REM Check virtual environment
if not exist venv (
    echo ERROR: Virtual environment not found!
    echo.
    echo Please run setup.bat first
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment
echo [*] Activating virtual environment...
call venv\Scripts\activate.bat

REM Check dependencies
python -c "import fastapi" > nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Dependencies not installed!
    echo.
    echo Please run setup.bat to install dependencies
    echo.
    pause
    exit /b 1
)

REM Start the bot
echo [*] Starting the bot...
echo.
echo ========================================
echo   Bot is running!
echo   Web interface: http://localhost:8000
echo   Login page:    http://localhost:8000/login
echo   Admin panel:   http://localhost:8000/admin
echo   Press Ctrl+C to stop
echo ========================================
echo.

python main.py

REM Handle exit
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Bot exited with error
    echo Check logs in logs/ directory
    echo.
)

pause
