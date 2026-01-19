# ChessGuard Launcher
# Double-click this script to start the server

$Host.UI.RawUI.WindowTitle = "ChessGuard"

Write-Host ""
Write-Host "  =============================================" -ForegroundColor Cyan
Write-Host "  |        ChessGuard Launcher v1.0           |" -ForegroundColor Cyan
Write-Host "  =============================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $PSScriptRoot

# Activate virtual environment if exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "[*] Activating virtual environment..." -ForegroundColor Yellow
    & ".venv\Scripts\Activate.ps1"
}
else {
    Write-Host "[!] No virtual environment found. Using system Python." -ForegroundColor Yellow
}

# Verify server directory
if (-not (Test-Path "server")) {
    Write-Host "[X] Error: server directory not found!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[*] Starting ChessGuard server..." -ForegroundColor Green
Write-Host ""
Write-Host "    Access the application at: http://localhost:8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "    Press Ctrl+C to stop the server." -ForegroundColor DarkGray
Write-Host ""
Write-Host "---------------------------------------------" -ForegroundColor DarkGray
Write-Host ""

# Open browser after delay
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process 'http://localhost:8000'
} | Out-Null

# Start the server
python -m uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
