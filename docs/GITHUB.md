# GitHub

## First push

```powershell
cd C:\Projects\nestle-ai-compliance
git init -b main
git add .
git status          # confirm that NO .env file, node_modules, .venv, storage or model files are listed
git commit -m "Initial commit: full-stack entry compliance application"
git remote add origin https://github.com/<your-account>/nestle-ai-compliance.git
git push -u origin main
```

Create the repository on GitHub first as **Private**, without a README (this project already has one).

## Never commit

`.env` files, passwords, database URLs, `SECRET_KEY`, `CAMERA_CREDENTIALS_KEY`, real camera addresses, model
weights, evidence images. `.gitignore` already excludes them, and CI runs a secret scan. If a secret is ever
committed: **rotate it immediately** — deleting the commit is not enough.

## Branching

* `main` — always deployable; protected (pull request + passing CI required).
* `develop` — integration branch for the next release.
* `feature/<short-name>`, `fix/<short-name>` — one change each, merged by pull request.
* Tag releases: `git tag v1.0.0 && git push --tags`.

Commit messages: short imperative summary, e.g. `Add shift filter to employee list`.

```powershell
git checkout -b feature/shift-filter
# ...work...
git add -A; git commit -m "Add shift filter to employee list"
git push -u origin feature/shift-filter      # then open a pull request on GitHub
```

## Continuous integration (`.github/workflows/ci.yml`)

Runs on every push to `main`/`develop` and every pull request:

* **backend** — ruff, Alembic upgrade/check/downgrade on PostgreSQL 16, pytest, `pip-audit`
* **frontend** — type-check, tests, production build, `npm audit` (high and above)
* **docker** — both images build
* **secrets-scan** — gitleaks

## GitHub Secrets for deployment

*Repository › Settings › Secrets and variables › Actions › New repository secret* (or per environment under
*Settings › Environments › staging / production*, where you can also require an approver):

| Secret | Value |
|---|---|
| `DEPLOY_HOST` | server name or IP |
| `DEPLOY_USER` | SSH user allowed to run Docker |
| `DEPLOY_SSH_KEY` | private key of a dedicated deploy key pair |
| `DEPLOY_PATH` | project folder on the server |

Application secrets (`SECRET_KEY`, database password, …) stay in `.env.docker` **on the server**, not in GitHub.
`.github/workflows/deploy.yml` is a manual-trigger template and has not been run against a real server.
