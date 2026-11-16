#!/usr/bin/env sh
# Back up the database and stored files from the Docker deployment. Run from the project root.
#   sh deployment/scripts/backup.sh            -> ./backups/<timestamp>/
set -eu
STAMP=$(date +%Y%m%d-%H%M%S)
DEST="backups/$STAMP"
mkdir -p "$DEST"
docker compose --env-file .env.docker exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$DEST/database.dump"
docker compose --env-file .env.docker exec -T backend tar -C /data -czf - storage > "$DEST/storage.tar.gz"
echo "Backup written to $DEST (copy it off this server and encrypt it)."
