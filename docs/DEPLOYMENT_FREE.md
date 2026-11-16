# Free online demo: Vercel (frontend) + Render (backend) + Neon (PostgreSQL)

Good for showing the app. Limits of the free plans:

* The Render backend **sleeps after 15 minutes** without traffic; the first request afterwards takes ~1 minute.
* Render's free disk is **temporary**: uploaded employee photos / evidence images disappear on every restart or deploy.
  Database records (in Neon) are kept.
* AI detection and doors run in **simulation** (`ENV=staging`) and are labelled as such.

```
Browser ──> https://<app>.vercel.app ──(/api/* rewrite)──> https://nestle-ai-backend.onrender.com ──> Neon PostgreSQL
```

The `/api` rewrite in `frontend/vercel.json` keeps everything on one address, so the login cookie works without CORS.

## 1. Database — Neon

1. Sign up at <https://neon.tech> (free), **Create project** (region close to you, e.g. Singapore / Frankfurt).
2. **Connect** → copy the connection string `postgresql://...neon.tech/neondb?sslmode=require...`.
   Keep it private; it goes into Render in step 2.

## 2. Backend — Render

1. Sign up at <https://render.com> with **GitHub** and allow access to the repository.
2. **New → Blueprint** → choose the repository → Render reads `render.yaml`.
3. Fill the values it asks for:

| Key | Value |
|---|---|
| `DATABASE_URL` | the Neon connection string |
| `FRONTEND_URL`, `CORS_ORIGINS` | your Vercel address, e.g. `https://nestle-xyz.vercel.app` (no trailing `/`) |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | your own Super Admin login (12+ chars, upper/lower/digit/symbol, not containing the e-mail name) |
| `SEED_PASSWORD` | password for the demo accounts (same rules) |
| `SMTP_USERNAME`, `SMTP_FROM` | your Gmail address |
| `SMTP_PASSWORD` | Gmail App Password, 16 letters, no spaces |

4. **Apply**. The first build takes ~5–10 minutes. When the log shows `Uvicorn running`, open
   `https://nestle-ai-backend.onrender.com/api/health/ready` → `{"status":"ready"}`.
5. If Render gave the service a different address (name already taken), put that address into
   `frontend/vercel.json` and push.

## 3. Frontend — Vercel

1. Vercel project → **Settings → General → Root Directory** = `frontend` (Framework preset: Vite).
2. **Deployments → Redeploy** (or push to GitHub).
3. Open the Vercel address and sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Login says "Cannot reach the server" / 502 / 504 right after a pause | Backend was asleep — wait a minute and retry |
| 404 on page refresh | Root Directory is not `frontend`, so `vercel.json` is ignored |
| Render log: `Unsafe configuration for staging` | One of `COOKIE_SECURE`, `DEV_RETURN_RESET_LINK`, `CAMERA_CREDENTIALS_KEY` was changed |
| Render log: `Password needs: ...` | `ADMIN_PASSWORD` / `SEED_PASSWORD` too weak — change it in Render → Environment |
| Signed out immediately after login | `FRONTEND_URL`/`CORS_ORIGINS` don't match the Vercel address exactly |
| No reset e-mail | `SMTP_*` values; check the Render log for `SMTP login rejected` |
