@echo off
REM BestWork Application Setup Script for Windows
REM Tüm Windows sürümlerinde çalışacak kurulum

setlocal enabledelayedexpansion

echo.
echo ======================================================
echo BestWork Application Setup - Windows
echo ======================================================
echo.

REM Check Python installation
echo Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

python --version
echo.

REM Get the base directory
set BASE_DIR=%~dp0
cd /d "%BASE_DIR%"

REM Check if venv exists
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment already exists
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo [WARNING] Failed to upgrade pip, continuing...
)

REM Install requirements
echo.
echo Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install requirements
    echo Check requirements.txt and try again
    pause
    exit /b 1
)

REM Create .env file if it doesn't exist
if not exist ".env" (
    echo.
    echo Creating .env file with auto-generated keys...
    python -c "import secrets; print('Creating .env file...')"
    
    REM Use Python to generate .env file
    python setup.py
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create .env file
        pause
        exit /b 1
    )
) else (
    echo [OK] .env file already exists
)

REM Create upload directories
if not exist "static\uploads" (
    echo Creating static\uploads directory...
    mkdir static\uploads
)

if not exist "logs" (
    echo Creating logs directory...
    mkdir logs
)

echo.
echo ======================================================
echo Setup completed successfully!
echo ======================================================
echo.
echo Next steps:
echo   1. Make sure MongoDB and Redis are running
echo   2. Run: python app.py
echo   3. Open browser: http://localhost:5000
echo.
echo To start the application:
echo   .venv\Scripts\python app.py
echo.

pause
