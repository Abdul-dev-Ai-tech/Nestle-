# Nestlé AI Personnel Entry Compliance & Smart Access Control

Full-stack application that checks PPE (uniform, hair cap, face mask, beard net, safety shoes) at
factory entry points, decides PASS/FAIL per module rules, records every entry, raises violations
and alerts, and drives door access — with dashboards, reports and an audit trail.

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite 5, Tailwind CSS 3, React Router 6, Recharts, Lucide icons |
| Backend | Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Database | PostgreSQL 16 |
| AI / cameras | OpenCV (USB / RTSP), Ultralytics YOLO (optional), browser MediaDevices API |
| Deployment | Docker, Docker Compose, Caddy (HTTPS), GitHub Actions |

## Read this first — what is real and what is not yet

* **Real and tested:** sign-in, sessions, roles/permissions, factories/modules, employees, cameras
  configuration, entry pipeline, compliance engine, violations, alerts, reports, CSV export, audit log.
* **Simulated by default:** PPE detection (`AI_MODE=simulation`) and door control (`DOOR_MODE=simulation`).
  The app labels simulated results everywhere and a simulated result can never operate real hardware.
* **Needs your input:** a PPE model trained on your own images (none is shipped — see `docs/AI_MODEL.md`),
  real cameras and a real door controller to verify the hardware paths.

The full checklist is in **`docs/STATUS.md`**.

## Quick start on Windows 11

Requirements: [Python 3.12+](https://www.python.org/downloads/), [Node.js LTS](https://nodejs.org/),
[Docker Desktop](https://www.docker.com/products/docker-desktop/) (or a local PostgreSQL 16).

```powershell
# in the project folder
powershell -ExecutionPolicy Bypass -File .\setup.ps1      # once: database, packages, keys, tables, demo data
powershell -ExecutionPolicy Bypass -File .\start-dev.ps1  # every time: starts backend + frontend
```

Open <http://localhost:5173>. `setup.ps1` prints the demo accounts and their password
(for example `super.admin@example.com`). Manual, step-by-step instructions: `docs/INSTALLATION.md`.

## Project layout

```
frontend/      React app (src/pages, components, features, hooks, services, contexts, routes, types)
backend/       FastAPI app (app/api, core, models, schemas, services, repositories, ai, camera,
               access_control, security, db), alembic/ migrations, tests/, ai_training/
deployment/    Dockerfiles, Caddyfile, backup/restore scripts
docs/          Installation, architecture, API, security, deployment, cameras, AI model, testing, GitHub, status
.github/       CI workflow and a manual deploy template
docker-compose.yml       full stack          docker-compose.dev.yml   database only (development)
setup.ps1 / start-dev.ps1   Windows helpers
```

## Everyday commands

```powershell
# backend (from .\backend, with the virtual environment active:  .\.venv\Scripts\Activate.ps1)
uvicorn app.main:app --reload --port 8000     # run the API  -> http://localhost:8000/api/docs
pytest -q                                     # tests
alembic upgrade head                          # apply database migrations
python -m app.db.seed --purge-samples         # remove the seeded sample history

# frontend (from .\frontend)
npm run dev        # development server -> http://localhost:5173
npm test           # UI tests
npm run build      # production build (also type-checks)
```

## Documentation

`docs/INSTALLATION.md` · `docs/ARCHITECTURE.md` · `docs/API.md` · `docs/SECURITY.md` · `docs/DEPLOYMENT.md` ·
`docs/CAMERA_SETUP.md` · `docs/AI_MODEL.md` · `docs/TESTING.md` · `docs/GITHUB.md` · `docs/STATUS.md`

## Licence and branding

Proprietary project; no open-source licence file is included on purpose. The Nestlé name and logo
belong to Société des Produits Nestlé S.A. The logo file in `frontend/src/assets/` was supplied by the
project owner and is low resolution — replace it with the official asset from the brand team.
