#!/usr/bin/env sh
# Restore a backup made by backup.sh. THIS OVERWRITES THE CURRENT DATABASE.
#   sh deployment/scripts/restore.sh backups/20261114-020000
set -eu
SRC="${1:?usage: restore.sh <backup-folder>}"
printf "This will overwrite the current database. Type RESTORE to continue: "
read -r answer
[ "$answer" = "RESTORE" ] || { echo "Cancelled."; exit 1; }
docker compose --env-file .env.docker stop backend
docker compose --env-file .env.docker exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < "$SRC/database.dump"
docker compose --env-file .env.docker start backend
docker compose --env-file .env.docker exec -T backend tar -C /data -xzf - < "$SRC/storage.tar.gz"
echo "Restore finished."
