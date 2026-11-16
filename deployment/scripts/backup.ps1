# Windows version of backup.sh. Run from the project root in PowerShell.
$ErrorActionPreference = "Stop"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = "backups\$stamp"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
cmd /c "docker compose --env-file .env.docker exec -T db sh -c ""pg_dump -U `$POSTGRES_USER -d `$POSTGRES_DB -Fc"" > $dest\database.dump"
cmd /c "docker compose --env-file .env.docker exec -T backend tar -C /data -czf - storage > $dest\storage.tar.gz"
Write-Host "Backup written to $dest (copy it off this machine and encrypt it)."
