@echo off
REM BestWork Application Run Script
REM Kurulum olmadan direkt başlat (venv gerekli)

setlocal enabledelayedexpansion

set BASE_DIR=%~dp0
cd /d "%BASE_DIR%"

REM Check if venv exists
if not exist ".venv" (
    echo [ERROR] Virtual environment not found!
    echo Please run setup.bat first
    pause
    exit /b 1
)

REM Activate venv
call .venv\Scripts\activate.bat

REM Run the app
python app.py
pause
