@echo off
REM Build script for VibeToText on Windows
REM Run this from the project root directory

echo === Building VibeToText for Windows ===

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.10+ and add to PATH.
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

REM Download whisper model if needed
echo Checking whisper model...
python -c "from pywhispercpp.model import Model; Model('base')"

REM Build main engine
echo Building main engine...
pyinstaller vibetotext-win.spec --noconfirm

REM Build UI
echo Building UI...
pyinstaller vibetotext-ui-win.spec --noconfirm

REM Copy both to dist folder
echo.
echo === Build complete! ===
echo Executables are in the dist/ folder:
echo   - dist\vibetotext-engine.exe
echo   - dist\vibetotext-ui.exe
echo.
echo To run: dist\vibetotext-engine.exe
echo.

pause
