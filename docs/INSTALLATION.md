# Installation on Windows 11 (Visual Studio Code)

All commands are for **PowerShell**. Paths are relative to the project folder, e.g. `C:\Projects\nestle-ai-compliance`.

## 1. Install the tools (once)

| Tool | Where | Check |
|---|---|---|
| Python **3.13** (or 3.12) — *not* 3.14, the pinned packages have no 3.14 wheels | `py install 3.13` (Python install manager) or <https://www.python.org/downloads/> | `py -V:3.13 --version` |
| Node.js LTS (20 or 22) | <https://nodejs.org/> | `node --version` |
| Git | <https://git-scm.com/download/win> | `git --version` |
| Docker Desktop *(easiest database)* | <https://www.docker.com/products/docker-desktop/> | `docker --version` |
| VS Code | <https://code.visualstudio.com/> | — |

Open the folder in VS Code (**File › Open Folder**) and accept the recommended extensions.

If PowerShell refuses to run scripts, allow them for your user once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 2. Fast path

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
powershell -ExecutionPolicy Bypass -File .\start-dev.ps1
```

`setup.ps1` starts PostgreSQL in Docker, creates `backend\.venv`, installs packages, writes
`backend\.env` with freshly generated keys, creates the tables, loads demo data and installs the
frontend packages. Write down the demo password it prints.

## 3. Manual path (what the script does)

### 3a. Database

**Option A — Docker (recommended):**

```powershell
docker compose -f docker-compose.dev.yml up -d
```

Database `nec`, user `nec_user`, password `dev_password_change_me`, on `localhost:5432`.

**Option B — PostgreSQL installed on Windows** (<https://www.postgresql.org/download/windows/>). Easiest:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup-database.ps1
```

It asks (masked) for the `postgres` superuser password, creates `nec_user` with a random password, creates the
databases `nec` and `nec_test`, and writes `backend\.env` with fresh keys. Nothing secret is printed.
Or by hand in *SQL Shell (psql)*:

```sql
CREATE USER nec_user WITH PASSWORD 'choose-a-password';
CREATE DATABASE nec OWNER nec_user;
```

### 3b. Backend

```powershell
cd backend
py -V:3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Edit `backend\.env`:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"                               # -> SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # -> CAMERA_CREDENTIALS_KEY
```

Set `DATABASE_URL=postgresql+psycopg://nec_user:<password>@localhost:5432/nec`. Then:

```powershell
alembic upgrade head          # create the tables
python -m app.db.seed         # roles, permissions, demo factory, demo users, 30 days of sample entries
uvicorn app.main:app --reload --port 8000
```

API documentation: <http://localhost:8000/api/docs>.

### 3c. Frontend (second PowerShell window)

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Open <http://localhost:5173>. The dev server forwards `/api` to the backend, so the browser sees one address.

## 4. Demo accounts and sample data

`python -m app.db.seed` prints five demo accounts (one per role) and one shared password — set your own
with `SEED_PASSWORD` in `.env` before seeding, otherwise a random one is generated and shown once.

* Sample entries are stored with `source = 'sample'` and are labelled in the UI.
* Remove them: `python -m app.db.seed --purge-samples`.
* The seed refuses to create demo users when `ENV=production`.
* Real first administrator: `python -m app.db.seed --create-admin you@company.com` (asks for a password).

## 5. Using the camera

Open **Live AI Monitoring › Start camera** and allow the browser prompt. `localhost` counts as secure;
from another device (e.g. a phone on the same Wi-Fi) the page must be served over **HTTPS** or the browser
will refuse camera access. See `docs/CAMERA_SETUP.md`.

## 6. Optional: real AI detection

```powershell
pip install -r requirements-ai.txt     # large download (PyTorch)
```

Put trained weights at `backend\models\ppe.pt`, set `AI_MODE=yolo` in `.env`, restart. See `docs/AI_MODEL.md`.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `SECRET_KEY must be a random string…` | Fill `SECRET_KEY` in `backend\.env` (32+ characters) |
| `connection refused` on port 5432 | Start Docker Desktop, then `docker compose -f docker-compose.dev.yml up -d` |
| Port 5432 already used | A local PostgreSQL is running — use it (Option B) or stop it |
| Login says “Cannot reach the server” | The backend window is not running, or not on port 8000 |
| Signed out immediately after login | You opened the frontend by IP over plain HTTP with `COOKIE_SECURE=true`; use `localhost` in development |
| Camera “permission was blocked” | Click the camera icon in the address bar › Allow |
| `pip install` hangs or tries to compile pydantic-core / psycopg / pillow | You are on Python 3.14: `py install 3.13`, delete `backend\.venv`, recreate it with `py -V:3.13 -m venv .venv` |
| Tests against PostgreSQL | `$env:TEST_DATABASE_URL="postgresql+psycopg://nec_user:<pw>@localhost:5432/nec_test"; pytest -q` — **never** point it at `nec`, the tests drop all tables |
