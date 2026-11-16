<#
  Creates the application's PostgreSQL role and databases on a PostgreSQL server installed natively on
  Windows (no Docker needed). Run from the project root:
      powershell -ExecutionPolicy Bypass -File .\setup-database.ps1

  What it does:
    * asks (masked) for the password of the PostgreSQL superuser you chose when installing PostgreSQL
    * creates the login role nec_user with a freshly generated random password
    * creates the database nec (application) and nec_test (automated tests only), owned by nec_user
    * writes DATABASE_URL into backend\.env  (creates the file with new random keys if it does not exist;
      asks before changing an existing file)
  Nothing secret is printed. Existing databases are never dropped or modified.
#>
param(
  [string]$DbName = "nec",
  [string]$TestDbName = "nec_test",
  [string]$DbUser = "nec_user",
  [string]$PgHost = "localhost",
  [int]$Port = 5432,
  [string]$SuperUser = "postgres"
)
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$envFile = Join-Path $root "backend\.env"
$envExample = Join-Path $root "backend\.env.example"

function Find-Psql {
  $cmd = Get-Command psql -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $found = Get-ChildItem "$env:ProgramFiles\PostgreSQL\*\bin\psql.exe" -ErrorAction SilentlyContinue |
    Sort-Object { try { [int]$_.Directory.Parent.Name } catch { 0 } } -Descending | Select-Object -First 1
  if (-not $found) { throw "psql.exe not found. Install PostgreSQL from https://www.postgresql.org/download/windows/ or use Docker (docker-compose.dev.yml)." }
  return $found.FullName
}

function New-RandomString([int]$Length) {
  $alphabet = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
  $bytes = New-Object byte[] $Length
  [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  return -join ($bytes | ForEach-Object { $alphabet[$_ % $alphabet.Length] })
}

function New-FernetKey {
  $bytes = New-Object byte[] 32
  [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  return [Convert]::ToBase64String($bytes).Replace('+', '-').Replace('/', '_')
}

function Write-Utf8NoBom([string]$Path, [string[]]$Lines) {
  [IO.File]::WriteAllLines($Path, $Lines, (New-Object Text.UTF8Encoding($false)))
}

function Invoke-Psql([string]$Sql, [string]$Database = "postgres") {
  # SQL goes through stdin so passwords never appear on a process command line.
  # 'Continue' locally: Windows PowerShell 5.1 turns native stderr into errors that would abort under 'Stop'.
  $ErrorActionPreference = "Continue"
  $out =$Sql | & $script:psql -h $PgHost -p $Port -U $SuperUser -d $Database -w -v ON_ERROR_STOP=1 -X -q -tA -f - 2>&1
  if ($LASTEXITCODE -ne 0) { throw "psql failed: $out" }
  return ($out | Out-String).Trim()
}

$script:psql = Find-Psql
Write-Host "Using $script:psql" -ForegroundColor DarkGray

$secure = Read-Host "Password of the PostgreSQL superuser '$SuperUser' (set when PostgreSQL was installed)" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  [void](Invoke-Psql "SELECT 1;")
  Write-Host "Connected to PostgreSQL as $SuperUser." -ForegroundColor Green

  $newPassword = $null
  $roleExists = (Invoke-Psql "SELECT 1 FROM pg_roles WHERE rolname = '$DbUser';") -eq "1"
  if (-not $roleExists) {
    $newPassword = New-RandomString 32
    [void](Invoke-Psql "CREATE ROLE $DbUser LOGIN PASSWORD '$newPassword';")
    Write-Host "Created role $DbUser." -ForegroundColor Green
  } else {
    $answer = Read-Host "Role $DbUser already exists. Give it a NEW random password and store it in backend\.env? (y/N)"
    if ($answer -match '^(y|yes)$') {
      $newPassword = New-RandomString 32
      [void](Invoke-Psql "ALTER ROLE $DbUser WITH LOGIN PASSWORD '$newPassword';")
      Write-Host "Password of $DbUser was reset." -ForegroundColor Green
    } else {
      Write-Host "Role left unchanged; backend\.env will not be modified." -ForegroundColor Yellow
    }
  }

  foreach ($db in @($DbName, $TestDbName)) {
    if ((Invoke-Psql "SELECT 1 FROM pg_database WHERE datname = '$db';") -eq "1") {
      Write-Host "Database $db already exists - left unchanged." -ForegroundColor Yellow
    } else {
      [void](Invoke-Psql "CREATE DATABASE $db OWNER $DbUser ENCODING 'UTF8' TEMPLATE template0;")
      Write-Host "Created database $db (owner $DbUser)." -ForegroundColor Green
    }
  }
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
  Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}

if ($newPassword) {
  $url = "postgresql+psycopg://${DbUser}:$newPassword@${PgHost}:$Port/$DbName"
  if (-not (Test-Path $envFile)) {
    $lines = Get-Content $envExample | ForEach-Object {
      if ($_ -match '^SECRET_KEY=') { "SECRET_KEY=" + (New-RandomString 64) }
      elseif ($_ -match '^DATABASE_URL=') { "DATABASE_URL=$url" }
      elseif ($_ -match '^CAMERA_CREDENTIALS_KEY=') { "CAMERA_CREDENTIALS_KEY=" + (New-FernetKey) }
      else { $_ }
    }
    Write-Utf8NoBom $envFile $lines
    Write-Host "Created backend\.env with the database URL and freshly generated keys." -ForegroundColor Green
  } else {
    $answer = Read-Host "backend\.env exists. Replace only its DATABASE_URL line with the new connection? (y/N)"
    if ($answer -match '^(y|yes)$') {
      Copy-Item $envFile "$envFile.bak" -Force
      $lines = @(Get-Content $envFile | ForEach-Object { if ($_ -match '^DATABASE_URL=') { "DATABASE_URL=$url" } else { $_ } })
      if (-not ($lines -match '^DATABASE_URL=')) { $lines += "DATABASE_URL=$url" }
      foreach ($key in "SECRET_KEY", "CAMERA_CREDENTIALS_KEY") {   # a hand-made .env (e.g. only SMTP lines) gets the missing keys
        if (-not ($lines -match "^$key=.+")) {
          $lines = @($lines | Where-Object { $_ -notmatch "^$key=" })
          $lines += if ($key -eq "SECRET_KEY") { "SECRET_KEY=" + (New-RandomString 64) } else { "CAMERA_CREDENTIALS_KEY=" + (New-FernetKey) }
        }
      }
      Write-Utf8NoBom $envFile $lines
      Write-Host "Updated DATABASE_URL in backend\.env (previous file saved as backend\.env.bak)." -ForegroundColor Green
    } else {
      Write-Host "backend\.env not changed. The new $DbUser password was NOT saved anywhere - re-run this script to reset it." -ForegroundColor Yellow
    }
  }
}

Write-Host "`nDone. Next:  cd backend; .\.venv\Scripts\python.exe -m alembic upgrade head; .\.venv\Scripts\python.exe -m app.db.seed" -ForegroundColor Cyan
