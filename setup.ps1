<#
  One-time local setup on Windows 11 (PowerShell). Run from the project root:
      powershell -ExecutionPolicy Bypass -File .\setup.ps1
  Requires: Python 3.12+, Node.js 20+, and either Docker Desktop or a local PostgreSQL 16.
#>
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Need($cmd, $hint) { if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd was not found. $hint" } }
Need node "Install Node.js LTS from https://nodejs.org/"

# The pinned packages ship Windows wheels for Python 3.12 / 3.13. Newer versions (e.g. 3.14) would try to
# compile pydantic-core, pillow and psycopg from source and fail. Prefer 3.13 / 3.12 via the py launcher.
$pyCmd = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
  foreach ($v in "3.13", "3.12") {
    & py "-V:$v" -c "import sys" 2>$null
    if ($LASTEXITCODE -eq 0) { $pyCmd = @("py", "-V:$v"); break }
  }
}
if (-not $pyCmd -and (Get-Command python -ErrorAction SilentlyContinue)) {
  $ver = & python -c "import sys; print('%d.%d' % sys.version_info[:2])"
  if ($ver -in "3.12", "3.13") { $pyCmd = @("python") }
}
if (-not $pyCmd) {
  throw "Python 3.13 or 3.12 is required. Install it with:  py install 3.13   (or from https://www.python.org/downloads/)"
}
Write-Host "Using Python: $($pyCmd -join ' ')" -ForegroundColor DarkGray

Write-Host "`n[1/5] Database" -ForegroundColor Cyan
$dbUrl = $null
if (Get-Command docker -ErrorAction SilentlyContinue) {
  docker compose -f "$root\docker-compose.dev.yml" up -d
  $dbUrl = "postgresql+psycopg://nec_user:dev_password_change_me@localhost:5432/nec"
} elseif (-not (Test-Path "$root\backend\.env")) {
  Write-Host "Docker not found - using the PostgreSQL server installed on Windows." -ForegroundColor Yellow
  & "$root\setup-database.ps1"   # creates nec_user / nec / nec_test and writes backend\.env
} else {
  Write-Host "Docker not found and backend\.env exists - using its DATABASE_URL (run .\setup-database.ps1 to recreate the database user)." -ForegroundColor Yellow
}

Write-Host "`n[2/5] Backend virtual environment and packages" -ForegroundColor Cyan
Set-Location "$root\backend"
$pyExe = $pyCmd[0]; $pyArgs = @($pyCmd | Select-Object -Skip 1)
if (-not (Test-Path .venv)) { & $pyExe @pyArgs -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip | Out-Null
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

Write-Host "`n[3/5] backend\.env" -ForegroundColor Cyan
if (-not (Test-Path .env)) {
  $secret = & .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
  $camKey = & .\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  (Get-Content .env.example) `
    -replace '^SECRET_KEY=.*', "SECRET_KEY=$secret" `
    -replace '^DATABASE_URL=.*', "DATABASE_URL=$dbUrl" `
    -replace '^CAMERA_CREDENTIALS_KEY=.*', "CAMERA_CREDENTIALS_KEY=$camKey" | Set-Content .env -Encoding utf8
  if (-not $dbUrl) { throw "No database URL - run .\setup-database.ps1 first." }
  Write-Host "Created backend\.env with freshly generated keys."
} else { Write-Host "backend\.env already exists - left unchanged." }

Write-Host "`n[4/5] Database tables and demo data" -ForegroundColor Cyan
Start-Sleep -Seconds 4
& .\.venv\Scripts\python.exe -m alembic upgrade head
& .\.venv\Scripts\python.exe -m app.db.seed

Write-Host "`n[5/5] Frontend packages" -ForegroundColor Cyan
Set-Location "$root\frontend"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
npm install

Set-Location $root
Write-Host "`nSetup complete. Note the demo password printed above, then run:  .\start-dev.ps1" -ForegroundColor Green
