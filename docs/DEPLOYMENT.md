# Deployment

> **Status:** the Docker files and this guide were written and reviewed, but **no deployment has been
> performed or verified** — the build environment had no Docker daemon. Run the staging steps below and
> fix anything that surfaces before production.

## Environments

| | Local development | Staging | Production |
|---|---|---|---|
| How | `setup.ps1` / `start-dev.ps1` | `docker compose` on a test server | `docker compose` on the production server |
| `ENV` | `development` | `staging` | `production` |
| HTTPS | no (localhost) | yes | yes |
| AI | `simulation` | `yolo` (candidate model) or `disabled` | `yolo` (validated model) or `disabled`; `simulation` is refused |
| Doors | simulation | simulation, then one test door | hardware only after approval |
| Data | demo + sample | copy of structure, test data | real; no demo users |

## Architecture

```
Internet / factory network ──► Caddy (ports 80/443, automatic HTTPS, static frontend, /api proxy)
                                  └─► backend (uvicorn, 2+ workers) ──► PostgreSQL (volume pgdata)
                                           └─► volume storage (evidence, photos)
```

### Cameras and doors need to be on site

USB cameras must be plugged into the machine that runs the backend. IP/RTSP cameras and door controllers
sit on the factory network and are normally **not reachable from the cloud**. Choose one:

1. **On-premises server (simplest):** run the whole stack on a server inside the factory network.
2. **Cloud app + on-site gateway:** host the app in the cloud and run a small on-site service that reads
   cameras, runs detection and talks to doors, calling the cloud API. This gateway is **not built yet**.
3. **Site-to-site VPN** between the cloud network and the camera VLAN (latency and security review needed).

For Phase 2 pilots, option 1 is recommended.

## Step by step (staging or production, Linux server with Docker)

```bash
git clone <your-repository-url> nestle-ai-compliance && cd nestle-ai-compliance
cp .env.docker.example .env.docker && nano .env.docker
```

Set in `.env.docker`: `ENV`, `SITE_ADDRESS=compliance.example.com`, `PUBLIC_URL=https://compliance.example.com`,
`COOKIE_SECURE=true`, strong `POSTGRES_PASSWORD`, `SECRET_KEY`, `CAMERA_CREDENTIALS_KEY`, `AI_MODE`.
Point the domain's DNS at the server and open ports 80 and 443 (Caddy obtains the certificate).

```bash
docker compose --env-file .env.docker up -d --build
docker compose ps                                   # all services "healthy"/"running"
curl -fsS https://compliance.example.com/api/health/ready
docker compose exec backend python -m app.db.seed --create-admin you@company.com
```

The backend container applies migrations (`alembic upgrade head`) and creates roles/permissions on each start.
Internal factory networks without public DNS: use your own certificate (Caddy `tls cert.pem key.pem`).

### Updating

```bash
git pull && docker compose --env-file .env.docker up -d --build
```

Take a backup first; migrations run automatically.

## Backup and recovery

```bash
sh deployment/scripts/backup.sh                 # -> backups/<timestamp>/database.dump + storage.tar.gz
sh deployment/scripts/restore.sh backups/<timestamp>
```

Schedule the backup nightly (cron / Task Scheduler), copy it off the server, encrypt it, and **practise a
restore** on staging at least once.

## Logging and monitoring

* `docker compose logs -f backend` — one line per request with a request id; secrets are redacted.
* Health: `/api/health` (process), `/api/health/ready` (database). Point an uptime monitor at the second.
* Error monitoring: set `SENTRY_DSN` and add `sentry-sdk` to `requirements.txt`.

## Go-live checklist

- [ ] HTTPS works; `COOKIE_SECURE=true`; HSTS header present
- [ ] No demo users; first admin created with `--create-admin`; sample data absent
- [ ] `AI_MODE` is `yolo` with a validated model, or `disabled`
- [ ] Doors in simulation until each controller is tested and approved
- [ ] Backups scheduled and a restore rehearsed
- [ ] Evidence purge scheduled; retention agreed
- [ ] Penetration test and data-protection review done
