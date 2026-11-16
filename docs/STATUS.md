# Implementation status (14 Nov 2026)

Legend: **Tested** = source exists and is covered by automated tests or the browser run ·
**Implemented** = source exists, exercised manually or only partly · **Simulated** = works with a simulator ·
**Needs hardware/data** = code exists but cannot be confirmed without external equipment ·
**Not implemented** = not in this delivery.

## Application

| Feature | Status |
|---|---|
| Branded loading screen, logo reveal, sign-in, forgot/reset password, profile, change password | Tested (browser run; auth API tests) |
| Sidebar navigation (10 pages), breadcrumbs, step navigation, mobile drawer, page transitions | Tested (browser run at 3 sizes) |
| Argon2id passwords, HttpOnly session cookies, CSRF, idle/absolute expiry, lockout, session revocation | Tested |
| Server-side RBAC, permission matrix, custom roles, user management, factory isolation | Tested |
| Factories, modules, departments, entry points, per-module PPE requirements | Tested |
| Employees: add/edit/deactivate/delete, photo, search, filters, sorting, pagination, history | Tested |
| Compliance decision engine | Tested (10 unit tests) |
| Entry pipeline: detection → compliance → records → violation → alerts → door decision | Tested with the simulated detector |
| Violations: filters, status workflow, notes, evidence viewing, severity, repeat detection | Tested |
| Alert center, notification bell | Tested |
| Dashboard from database records (10 s refresh) | Tested |
| Reports: daily/weekly/monthly, shift, employee, module, PPE, repeat violations, entry history, audit log; CSV export | Tested |
| Secure uploads; private evidence storage; retention purge script | Tested (purge script: implemented) |
| Audit logging | Tested |

## Cameras

| Feature | Status |
|---|---|
| Browser cameras: permission, start/stop, switch device, capture, live preview, error and disconnect handling | Tested with Chromium's fake camera; try on your laptop and phone |
| Mobile camera (rear) | Implemented — needs HTTPS and a real phone to confirm |
| USB camera on the server (OpenCV) | Needs hardware |
| RTSP / IP cameras: configuration, encrypted credentials, connection test, online/offline, reconnect, MJPEG relay | Configuration and credential storage tested; streaming needs hardware |
| ONVIF discovery (WS-Discovery) | Needs hardware (same network segment) |
| On-site camera gateway for cloud hosting | Not implemented (described in docs/DEPLOYMENT.md) |

## AI

| Feature | Status |
|---|---|
| Detector interface, registry, configurable thresholds, class map | Tested |
| Simulated detector (development) | Simulated — does not analyse the image |
| YOLO detector integration (Ultralytics) | Implemented, **not run** — no trained weights exist |
| Uniform / hair cap / face mask / beard net / safety shoes detection | **Requires training and on-site validation — none operational** |
| Training and validation scripts, dataset template, guide | Implemented, not run (no dataset) |
| Bounding-box overlay in the UI | Implemented — shows boxes only when a real model returns them |
| Employee identification by face | Not implemented (employee ID is typed/scanned) |

## Doors

| Feature | Status |
|---|---|
| Door status, automatic decision, manual override with reason, event history, fault alerts | Tested in simulation |
| Safety interlocks (simulated AI never drives hardware; approval required; fail-secure) | Tested |
| Adapter architecture; HTTP relay adapter | Template — needs hardware; not verified against any controller |
| Wiegand / OSDP / vendor access-control systems | Not implemented |

## Operations

| Feature | Status |
|---|---|
| Alembic migrations on PostgreSQL 16 | Tested |
| Seed script (roles, demo users, sample data, purge, create admin) | Tested |
| Dockerfiles, docker-compose, Caddy HTTPS proxy | Written, **not built or run** |
| GitHub Actions CI and deploy template | Written, **not executed** |
| Windows scripts (`setup.ps1`, `start-dev.ps1`, `backup.ps1`) | Written, **not run on Windows** |
| Backup / restore scripts | Written, not run |
| Deployment to a server | **Not done** |
| E-mail for password reset | Implemented; needs an SMTP server to confirm |
| E-mail / SMS delivery of alerts | Not implemented (preferences are stored) |
| Multi-factor authentication, single sign-on | Not implemented |

## Needed from you to go further

1. Official high-resolution Nestlé logo (replace `frontend/src/assets/nestle-logo.png`).
2. Labelled PPE images from the real entry points (see docs/AI_MODEL.md).
3. Camera models and network access; door controller make/model and its interface.
4. A server (or on-site PC) with Docker, a domain name, and SMTP details.
5. Decision on how employees are identified at the gate (badge/RFID reader vs typed ID).
