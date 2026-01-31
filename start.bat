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

REM Check if frontend is built
if not exist frontend\dist (
    echo [*] Frontend not built. Building React SPA...
    cd frontend
    call npm install
    call npm run build
    cd ..
    if not exist frontend\dist (
        echo WARNING: Frontend build failed!
        echo Falling back to legacy templates...
    ) else (
        echo [+] Frontend built successfully!
    )
) else (
    echo [+] React SPA found in frontend\dist
)

REM Start the backend
echo [*] Starting FastAPI server...
echo.
echo ========================================
echo   CSFloat Bot is running!
echo   Open: http://localhost:8000
echo   Press Ctrl+C to stop
echo ========================================
echo.

REM Start frontend dev server in background (optional)
REM Uncomment the next line to run frontend in dev mode
REM start /B cmd /c "cd frontend && npm run dev"

python main.py

REM Handle exit
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Bot exited with error
    echo Check logs in logs/ directory
    echo.
)

pause
