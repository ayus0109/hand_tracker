# PowerShell launcher for Virtual Whiteboard
Write-Host "Starting Virtual Whiteboard Using Hand Gestures..." -ForegroundColor Cyan
python main.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "`nApplication exited with an error code: $LASTEXITCODE" -ForegroundColor Red
    Read-Host "Press Enter to exit..."
}
