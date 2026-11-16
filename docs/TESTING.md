# Testing

## Run the tests

```powershell
# backend (SQLite by default — no database needed)
cd backend; .venv\Scripts\Activate.ps1
pytest -q
# against PostgreSQL (use an empty test database — tables are dropped and recreated)
$env:TEST_DATABASE_URL = "postgresql+psycopg://nec_user:<password>@localhost:5432/nec_test"; pytest -q

# frontend
cd frontend
npm run typecheck
npm test
npm run build
```

## What is covered

**Backend — 49 tests** (`backend/tests/`)

| File | Covers |
|---|---|
| `test_compliance_engine.py` (10) | PASS/FAIL rules, per-module requirements, thresholds, beard-net applicability, fail-closed, severity |
| `test_auth.py` (13) | Login, Argon2id storage, generic errors, CSRF, logout, lockout, deactivation, idle expiry, reset flow, change password, headers |
| `test_rbac.py` (7) | Each role's limits, export permission, escalation attempts, live permission changes, factory isolation |
| `test_operations.py` (19) | Employees CRUD/search/sort/paging, upload validation, entry pipeline, violations, repeat detection, door interlocks and fail-secure, camera credential encryption, offline camera, dashboard, reports/CSV, injection attempts, settings validation |

**Frontend — 12 tests** (`frontend/src/test/`): login form validation and submission, password visibility,
route protection and the access-restricted screen, CSRF header in the API client, PASS/FAIL result panel.

## Results at delivery (14 Nov 2026)

| Check | Result |
|---|---|
| Backend tests on SQLite | 49 passed |
| Backend tests on PostgreSQL 16 | 49 passed |
| Alembic `upgrade head` and `check` on PostgreSQL 16 | passed (schema matches the models) |
| `ruff check` | passed |
| Frontend type-check, tests, production build | passed (12 tests) |
| Browser run (Chromium, built frontend + backend + PostgreSQL), 1440×900, 1366×768 and 390×844: every page and tab, PPE check with a (fake) camera, add employee, door override, resolve violation, CSV export, add camera, viewer restrictions | no script errors, no server errors, no horizontal overflow |
| `npm audit --omit=dev` | 0 high/critical; 2 moderate in react-router 6 (see `docs/SECURITY.md`) |

## Not tested (needs hardware, data or infrastructure)

* `pip-audit` was not run in the build environment — CI runs it.
* Docker images and `docker compose` were not built or started (no Docker daemon available).
* GitHub Actions workflows were not executed.
* Real USB / RTSP / ONVIF cameras, a real YOLO model, and a real door controller.
* The PowerShell scripts (`setup.ps1`, `start-dev.ps1`, `backup.ps1`) were written for Windows but could not be
  run on Windows here — the same commands were run on Linux. Report any error and it will be fixed.
* Load/performance and penetration testing.

## Manual check list after installing

1. Sign in as each demo role; locked menu items open the *Access restricted* screen.
2. Live AI Monitoring: start the webcam, run a check, see PASS/FAIL, see the entry on the dashboard.
3. Employee: add, edit, upload a photo, open the profile, delete.
4. Access control: unlock a door with a reason; it re-locks after the timer; the event is in the log and audit report.
5. Violations: open one, add a note, mark resolved; alert center: acknowledge.
6. Reports: change dates, switch tabs, export CSV.
7. Users: add a user, change a role, switch a permission in the matrix and confirm the effect.
