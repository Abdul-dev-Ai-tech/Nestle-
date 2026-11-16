<#
  Share the app from this laptop with a free public https link (Cloudflare quick tunnel; no account, no card).
      powershell -ExecutionPolicy Bypass -File .\start-public.ps1
  Needs a complete backend\.env (run .\setup-database.ps1 first). The link changes on every start and works
  only while this laptop is on and the three windows stay open.
#>
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
if (-not (Test-Path "$root\backend\.venv\Scripts\python.exe")) { throw "Run .\setup.ps1 first." }
if (-not (Test-Path "$root\backend\.env")) { throw "backend\.env missing - run .\setup-database.ps1 first." }

$cf = "$env:LOCALAPPDATA\cloudflared\cloudflared.exe"
if (-not (Test-Path $cf)) {
  New-Item -ItemType Directory -Force (Split-Path $cf) | Out-Null
  Write-Host "Downloading cloudflared..." -ForegroundColor Cyan
  Invoke-WebRequest "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -OutFile $cf -UseBasicParsing
  if ((Get-AuthenticodeSignature $cf).Status -ne "Valid") { Remove-Item $cf; throw "cloudflared download is not validly signed - aborted." }
}

# 1. tunnel -> read its public address from the log
$log = Join-Path $env:TEMP "nec-tunnel.log"; Remove-Item $log -ErrorAction SilentlyContinue
Start-Process $cf -ArgumentList "tunnel", "--no-autoupdate", "--url", "http://localhost:4173", "--logfile", $log -WindowStyle Minimized
$url = $null
for ($i = 0; $i -lt 40 -and -not $url; $i++) {
  Start-Sleep -Seconds 1
  if (Test-Path $log) { $m = Select-String -Path $log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' | Select-Object -First 1; if ($m) { $url = $m.Matches[0].Value } }
}
if (-not $url) { throw "The tunnel did not start - check your internet connection and $log" }

# 2. backend: public-safe overrides (no on-screen reset links, secure cookies, reset e-mails point to the public link)
$backendCmd = "Set-Location '$root\backend'; `$env:DEV_RETURN_RESET_LINK='false'; `$env:COOKIE_SECURE='true'; " +
  "`$env:FRONTEND_URL='$url'; `$env:CORS_ORIGINS='$url,http://localhost:4173'; " +
  ".\.venv\Scripts\python.exe -m alembic upgrade head; if (`$LASTEXITCODE -eq 0) { .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --host 127.0.0.1 }"
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $backendCmd

# 3. frontend: production build served by vite preview (proxies /api to the backend)
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", "Set-Location '$root\frontend'; npm run build; if (`$LASTEXITCODE -eq 0) { npx vite preview --port 4173 --strictPort }"

Write-Host "`nPublic link (share this):  $url" -ForegroundColor Green
Write-Host "Give it ~30 seconds to finish building. Close the windows to stop sharing." -ForegroundColor Yellow
