# Security

## What is implemented

| Control | Where |
|---|---|
| Argon2id password hashing (64 MiB, t=3), automatic re-hash, password policy (10+ chars, 4 classes) | `app/security/passwords.py` |
| Server-side sessions; only a SHA-256 hash of the token is stored; HttpOnly + SameSite cookies; `Secure` enforced outside development | `app/services/auth.py`, `app/api/deps.py` |
| Idle timeout (30 min) and absolute lifetime (12 h); logout, per-session and per-user revocation; all sessions revoked on password reset | same |
| CSRF: session-bound token required in `X-CSRF-Token` on every unsafe request; custom header on login/reset | `app/api/deps.py` |
| Login protection: lock after 5 failures per e-mail for 15 min; identical error for unknown user / wrong password; per-IP rate limits | `app/services/auth.py`, `app/security/ratelimit.py` |
| Password reset: single-use, 30-minute, hashed tokens; no account enumeration | `app/services/auth.py` |
| RBAC on the server for every route; 24 permissions; 5 built-in roles; custom roles; rank check against privilege escalation | `app/security/permissions.py`, `app/api/v1/users.py` |
| Factory data isolation (404 for other factories' objects) | `app/api/deps.py` |
| Input validation with Pydantic (lengths, patterns, enums, unknown fields rejected); ORM-only queries (no string SQL) | `app/schemas/inputs.py` |
| Uploads: size limit, real image verification, re-encoding (metadata stripped), random file names, served only via authorised endpoints | `app/services/storage.py` |
| Camera credentials encrypted at rest (Fernet), never returned by the API, rejected inside URLs, redacted from logs | `app/security/crypto.py`, `app/core/logging.py` |
| Security headers (nosniff, frame deny, referrer, permissions policy, HSTS with HTTPS, CSP) | `app/main.py`, `deployment/docker/Caddyfile` |
| CORS allow-list (no wildcard) | `app/main.py` |
| Audit log of sign-ins, changes, overrides, exports and evidence views | `app/services/audit.py` |
| Unsafe configuration refuses to start in staging/production | `app/core/config.py` |
| CSV exports guarded against spreadsheet formula injection | `app/api/v1/reports.py` |
| CI: tests, `pip-audit`, `npm audit`, secret scanning (gitleaks) | `.github/workflows/ci.yml` |

## Door safety interlocks (`app/access_control/service.py`)

1. Simulation is the default. Real hardware needs `DOOR_MODE=hardware` **and** `HARDWARE_DOORS_ENABLED=true`,
   a hardware adapter on the door, **and** an approval recorded by a user with `access.hardware` (Super Admin).
2. A simulated AI result never actuates real hardware (tested).
3. Doors auto-open only on PASS; everything else keeps them locked.
4. Adapter errors are fail-secure: door marked *fault*, kept locked, critical alert raised.
5. Changing a door's adapter or configuration withdraws its approval.

Physical fail-safe/fail-secure wiring, emergency egress and fire-alarm release are the site's responsibility
and must follow local regulations — software must never be the only way out of a room.

## Secrets

Never commit `.env`, passwords, keys or camera addresses. Only `.env.example` files with placeholders are in
the repository. Generate keys with the commands in `docs/INSTALLATION.md`. Rotating
`CAMERA_CREDENTIALS_KEY` makes stored camera credentials unreadable — re-enter them afterwards.

## Evidence retention

Evidence images live under `STORAGE_DIR/evidence`. Schedule the purge daily:

```powershell
cd backend; .venv\Scripts\Activate.ps1; python -m scripts.purge_evidence
```

## Known limitations — address before production

* The rate limiter is in-memory per process. With several workers/replicas, also rate-limit at the proxy or use Redis.
* No multi-factor authentication and no single sign-on yet (recommended for administrators).
* `react-router` 6 has two *moderate* advisories reported by `npm audit` (open redirect via crafted link targets;
  an SSR issue that does not apply to this client-only app). Post-login redirects are restricted to same-site
  paths in `Login.tsx`. Plan an upgrade to React Router 7.
* Evidence files are not encrypted on disk — use an encrypted volume.
* E-mail alert delivery is not implemented (password-reset e-mail is).
* No penetration test has been performed. Arrange one before go-live.
* Images of employees are personal data: agree retention, access and notice with HR / the data-protection owner.
