@echo off
echo ========================================
echo   CSFloat Bot - Initial Setup
echo ========================================
echo.

REM Check Python installation
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python not found! Please install Python 3.10+
    pause
    exit /b 1
)

REM Create virtual environment
echo [1/6] Creating virtual environment...
if not exist venv (
    python -m venv venv
    echo OK: Virtual environment created
) else (
    echo INFO: Virtual environment already exists
)

REM Activate and install dependencies
echo.
echo [2/6] Installing dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip > nul 2>&1
pip install -r requirements.txt
if %errorlevel% equ 0 (
    echo OK: Dependencies installed
) else (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

REM Create logs directory
echo.
echo [3/6] Creating logs directory...
if not exist logs (
    mkdir logs
    echo OK: Logs directory created
) else (
    echo INFO: Logs directory already exists
)

REM Create .env file
echo.
echo [4/6] Checking configuration...
if not exist .env (
    if exist .env.example (
        copy .env.example .env > nul
        echo OK: Created .env from .env.example
    ) else (
        echo # CSFloat Bot Configuration > .env
        echo HOST=0.0.0.0 >> .env
        echo PORT=8000 >> .env
        echo CHECK_INTERVAL=120 >> .env
        echo OUTBID_STEP=0.01 >> .env
        echo MAX_OUTBIDS=10 >> .env
        echo OK: Created .env with default settings
    )
) else (
    echo INFO: .env file already exists
)

REM Run database migration
echo.
echo [5/6] Running database migrations...
python migrate_db.py

REM Create admin user
echo.
echo [6/6] Creating admin user...
python create_admin.py --auto
if %errorlevel% equ 0 (
    echo OK: Admin user ready
) else (
    echo WARNING: Could not create admin user
    echo You can create it manually with: create_admin.bat
)

echo.
echo ========================================
echo   Setup completed successfully!
echo ========================================
echo.
echo Default admin credentials:
echo   Username: admin
echo   Password: admin123
echo.
echo IMPORTANT: Change the password after first login!
echo.
echo Now run start.bat to launch the bot
echo.
pause
