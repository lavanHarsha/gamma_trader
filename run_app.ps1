Write-Host "=========================================================================" -ForegroundColor Cyan
Write-Host "Starting Gamma_trader-Web: Explainable Low-Risk NSE Intraday Web App" -ForegroundColor Green
Write-Host "=========================================================================" -ForegroundColor Cyan

Write-Host "[1/3] Launching FastAPI Backend Server on port 8000..." -ForegroundColor Yellow
$backendProcess = Start-Process -FilePath "uvicorn" -ArgumentList "backend.api.main:app --host 0.0.0.0 --port 8000" -PassThru

Write-Host "[2/3] Launching Vite Frontend on port 5173..." -ForegroundColor Yellow
Set-Location -Path "frontend"
$frontendProcess = Start-Process -FilePath "npm" -ArgumentList "run dev -- --host" -PassThru
Set-Location -Path ".."

Start-Sleep -Seconds 3

Write-Host "[3/3] Opening Web Application in Default Browser..." -ForegroundColor Green
Start-Process "http://localhost:5173"

Write-Host "Gamma_trader-Web is LIVE at http://localhost:5173" -ForegroundColor Green
Write-Host "Press Ctrl+C or close windows to terminate." -ForegroundColor Gray

