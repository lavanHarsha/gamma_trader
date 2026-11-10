@echo off
echo =========================================================================
echo Starting Gamma_trader-Web: Explainable Low-Risk NSE Intraday Signal Web App
echo =========================================================================

echo [1/3] Verifying and Starting FastAPI Backend Server on port 8000...
start "Gamma_trader Backend" cmd /k "uvicorn backend.api.main:app --host 0.0.0.0 --port 8000"

echo [2/3] Starting Vite React Frontend on port 5173...
cd frontend
start "Gamma_trader Frontend" cmd /k "npm run dev -- --host"
cd ..

timeout /t 3 /nobreak >nul

echo [3/3] Opening Web Application in Browser...
start http://localhost:5173

echo =========================================================================
echo Gamma_trader-Web is now live at http://localhost:5173
echo Backend API available at http://localhost:8000
echo =========================================================================

