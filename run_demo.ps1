Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   Starting Sentinel-RTO Autonomous Risk Defense Engine   " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

# Set PYTHONPATH to project root
$env:PYTHONPATH = (Get-Location).Path

# Check Virtual Environment
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    Write-Host "[*] Activating Python Virtual Environment..." -ForegroundColor Yellow
    & ".\.venv\Scripts\Activate.ps1"
}

# 1. Start FastAPI Gateway in a separate terminal process
Write-Host "[*] Spawning FastAPI Gateway on port 8000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '.\.venv\Scripts\Activate.ps1'; `$env:PYTHONPATH='$((Get-Location).Path)'; uvicorn src.services.api:app --reload --port 8000"

Start-Sleep -Seconds 2

# 2. Launch Streamlit Merchant Command Center
Write-Host "[*] Launching Streamlit Command Center on port 8501..." -ForegroundColor Green
streamlit run dashboard/app.py