@echo off
echo =============================================
echo   Sales Lead Generator Pro - Windows Setup
echo =============================================
echo.

:: Create virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Python not found.
        echo Please install Python from https://python.org
        echo Make sure to check "Add Python to PATH" during install.
        pause
        exit /b 1
    )
)

:: Activate venv
echo Activating virtual environment...
call venv\Scripts\activate.bat

:: Install dependencies
echo.
echo Installing Python dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

:: Install Playwright browser
echo.
echo Installing Playwright Chromium browser (this may take a minute)...
playwright install chromium
if errorlevel 1 (
    echo ERROR: Failed to install Playwright browser.
    pause
    exit /b 1
)

echo.
echo =============================================
echo   Setup complete!
echo =============================================
echo.
echo To run the scraper, double-click run.bat
echo.
pause
