# Architecture

```
Browser (React SPA)
  │  HTTPS, same origin, HttpOnly session cookie + CSRF header
  ▼
Reverse proxy (Caddy; Vite proxy in development)
  ├── /            static frontend
  └── /api/*  ──►  FastAPI backend
                     ├── api/v1        routers: auth, users, org, employees, cameras, monitoring,
                     │                 access, violations (+alerts), dashboard, reports
                     ├── security      Argon2id, tokens, permission catalogue, rate limiter, Fernet
                     ├── services      entry_pipeline, compliance (pure), analytics, auth, audit, storage, mailer
                     ├── ai            PPEDetector interface · SimulatedDetector · YoloDetector · registry
                     ├── camera        OpenCV sources (USB/RTSP) · MJPEG stream hub · ONVIF discovery
                     ├── access_control  DoorAdapter interface · simulation · http_relay template · service (interlocks)
                     ├── repositories  query helpers
                     └── models/db     SQLAlchemy models · Alembic migrations · seed
                   PostgreSQL            file storage (evidence, photos)
```

## The entry workflow (`services/entry_pipeline.py`)

1. A frame arrives — uploaded by the browser (webcam/mobile) or grabbed by the server from a USB/RTSP camera.
2. `ai.registry.get_detector()` returns the configured detector; it reports each PPE item with a confidence.
3. `services/compliance.evaluate()` compares detections with the module's PPE requirements and thresholds.
4. Result PASS/FAIL per item and overall; **fail-closed** if a required item has no result.
5. `EntryLog`, `DetectionRecord`s and a `ComplianceRecord` are saved; evidence image stored per policy.
6. On FAIL: a `Violation` (severity, repeat detection) and `Alert`s are created.
7. `access_control.service.apply_entry_decision()` applies the door decision through the adapter.

## Key design decisions

* **Server-side sessions** in HttpOnly cookies (revocable, idle + absolute expiry) rather than JWTs in JavaScript.
* **RBAC in the API**: every route declares its permission (`require("employees.manage")`); the UI only hides things.
* **Factory isolation**: every factory-scoped row has `factory_id`; users may be limited to one factory;
  cross-factory objects answer 404. Tested in `tests/test_rbac.py`.
* **Replaceable AI**: implement `PPEDetector` and register it; nothing else changes. Model and class map are configuration.
* **Replaceable doors**: implement `DoorAdapter`. Interlocks live in one place (`access_control/service.py`).
* **Honest data provenance**: each entry has `source` = `live` | `simulation` | `sample`, shown in the UI.
* **Reports** aggregate entry rows in Python in the factory time zone (portable, simple). For very large
  volumes add daily roll-up tables.
* **Dashboard refresh** is polling (10 s). WebSockets/SSE can be added later without changing the API shape.

## Database (26 tables)

`users`, `roles`, `permissions`, `user_roles`, `role_permissions`, `sessions`, `password_reset_tokens`,
`login_attempts`, `audit_logs`, `factories`, `factory_settings`, `modules`, `departments`, `entry_points`,
`ppe_requirements`, `employees`, `cameras`, `door_controllers`, `entry_logs`, `detection_records`,
`compliance_records`, `access_events`, `violations`, `violation_notes`, `alerts`, `alembic_version`.

Primary keys, foreign keys with delete rules, unique constraints (e.g. employee code per factory, module
code per factory, one door per entry point) and indexes on the time-range queries are defined in
`backend/app/models/` and created by `backend/alembic/versions/…_initial_schema.py`.

## Frontend

`contexts/` (auth, scope = selected factory/module, toasts) · `hooks/` (`useApi` with polling, `useCamera`) ·
`services/api.ts` (fetch wrapper, CSRF) · `routes/` (protected routes) · `layouts/` · `pages/` (one per
navigation item) · `features/` (larger page-specific components) · `components/ui` + `components/charts`.
Styling: Tailwind is configured (theme tokens in `tailwind.config.js`); the design system approved in the
Phase 1 demo is kept as component classes in `src/styles/index.css`, with Tailwind utilities available on top.
