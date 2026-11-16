#!/bin/sh
# Container start-up: migrate, ensure roles, optional first admin / demo data, then serve.
# Used by deployment/docker/backend.Dockerfile (Docker Compose, Render, any container host).
#   PORT              port to listen on (Render sets it; default 8000)
#   ADMIN_EMAIL       + ADMIN_PASSWORD: create this Super Admin once if it does not exist yet
#   SEED_DEMO=true    load the demo factory, demo users (password SEED_PASSWORD) and sample history once
set -e
alembic upgrade head
python -m app.db.seed --reference-only
if [ -n "$ADMIN_EMAIL" ]; then
  python -m app.db.seed --ensure-admin "$ADMIN_EMAIL"
fi
if [ "$SEED_DEMO" = "true" ]; then
  python -m app.db.seed
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" \
  --proxy-headers --forwarded-allow-ips='*'
