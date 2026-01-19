@echo off
title ChessGuard Launcher
color 0A

echo.
echo  ╔═══════════════════════════════════════════╗
echo  ║        ChessGuard Launcher v1.0           ║
echo  ╚═══════════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: Check if virtual environment exists
if exist ".venv\Scripts\activate.bat" (
    echo [*] Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo [!] No virtual environment found. Using system Python.
)

:: Check if server directory exists
if not exist "server" (
    echo [X] Error: 'server' directory not found!
    echo     Make sure you're running this from the ChessGuard root directory.
    pause
    exit /b 1
)

echo [*] Starting ChessGuard server...
echo.
echo     Access the application at: http://localhost:8000
echo.
echo     Press Ctrl+C to stop the server.
echo.
echo ────────────────────────────────────────────────
echo.

:: Open browser after a short delay
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"

:: Start the server
python -m uvicorn server.main:app --reload --host 0.0.0.0 --port 8000

pause
