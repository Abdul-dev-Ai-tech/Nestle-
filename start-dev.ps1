<#
  Start the application for local development (Windows 11, PowerShell):
      powershell -ExecutionPolicy Bypass -File .\start-dev.ps1
  Opens two windows: the FastAPI backend (port 8000) and the React dev server (port 5173).
#>
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
if (-not (Test-Path "$root\backend\.venv\Scripts\python.exe")) { throw "Run .\setup.ps1 first (backend virtual environment missing)." }
if (-not (Test-Path "$root\backend\.env")) { throw "backend\.env is missing. Run .\setup-database.ps1 (local PostgreSQL) or .\setup.ps1." }
if (-not (Test-Path "$root\frontend\node_modules")) { throw "Frontend packages missing. Run:  cd frontend; npm install" }

# Database: Docker container if Docker is installed, otherwise the PostgreSQL Windows service.
if (Get-Command docker -ErrorAction SilentlyContinue) {
  docker compose -f "$root\docker-compose.dev.yml" up -d | Out-Null
} else {
  $svc = Get-Service -Name "postgresql*" -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($svc -and $svc.Status -ne "Running") {
    Write-Host "Starting $($svc.Name)..." -ForegroundColor Yellow
    try { Start-Service $svc.Name } catch { throw "PostgreSQL service '$($svc.Name)' is stopped and could not be started (try an Administrator PowerShell: Start-Service $($svc.Name))." }
  }
}

# Calls the venv's python directly, so no Activate.ps1 / execution-policy change is needed.
$backendCmd = "Set-Location '$root\backend'; .\.venv\Scripts\python.exe -m alembic upgrade head; if (`$LASTEXITCODE -eq 0) { .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000 }"
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $backendCmd
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "Set-Location '$root\frontend'; npm run dev"

# Wait for the API to come up (max ~40 s) before opening the browser.
for ($i = 0; $i -lt 20; $i++) {
  Start-Sleep -Seconds 2
  try { if ((Invoke-WebRequest "http://127.0.0.1:8000/api/health/ready" -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200) { break } } catch { }
}
Start-Process "http://localhost:5173"
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "Backend:  http://localhost:8000      Swagger: http://localhost:8000/api/docs" -ForegroundColor Green
