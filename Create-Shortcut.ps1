# Create Desktop Shortcut for ChessGuard
$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $DesktopPath "ChessGuard.lnk"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-ExecutionPolicy Bypass -File `"$PSScriptRoot\Launch-ChessGuard.ps1`""
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.Description = "Launch ChessGuard - Chess Anti-Cheat Toolkit"
$Shortcut.IconLocation = "$PSScriptRoot\frontend\assets\chessguard.ico"
$Shortcut.Save()

Write-Host "Desktop shortcut created with custom icon: $ShortcutPath" -ForegroundColor Green
