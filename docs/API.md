# API reference (summary)

Base path `/api/v1`. Interactive documentation with every field: `http://localhost:8000/api/docs`
(disabled when `ENV=production`). JSON in, JSON out; errors are `{"detail": "message"}`.

**Authentication:** cookie `nec_session` (HttpOnly). Unsafe methods need header `X-CSRF-Token` = value of
cookie `nec_csrf`. Login/forgot/reset need `X-Requested-With: XMLHttpRequest`.
Most list endpoints accept `factory_id` and `module_id`; paged ones accept `page`, `page_size`.

| Area | Endpoint | Permission |
|---|---|---|
| Auth | `POST /auth/login`, `POST /auth/logout`, `GET/PATCH /auth/me` | — / signed in |
| | `POST /auth/forgot-password`, `POST /auth/reset-password`, `POST /auth/change-password` | — / signed in |
| | `GET /auth/sessions`, `DELETE /auth/sessions/{id}` | signed in |
| Users | `GET /users`, `POST /users`, `PATCH /users/{id}`, `POST /users/{id}/revoke-sessions` | `users.view` / `users.manage` |
| Roles | `GET /roles`, `GET /permissions`, `POST /roles`, `PUT /roles/{id}/permissions`, `DELETE /roles/{id}` | `users.view` / `roles.manage` |
| Factories | `GET /factories`, `POST /factories`, `PUT /factories/{id}` | signed in / `settings.manage` |
| Settings | `GET /settings`, `PUT /settings` | `settings.view` / `settings.manage` |
| Modules | `GET /modules`, `POST /modules`, `PATCH/DELETE /modules/{id}`, `PUT /modules/{id}/ppe` | `dashboard.view` / `modules.manage` |
| Entry points | `POST /modules/{id}/entry-points`, `DELETE /entry-points/{id}` | `modules.manage` |
| Departments | `GET /departments`, `POST /departments`, `DELETE /departments/{id}` | `dashboard.view` / `modules.manage` |
| Employees | `GET /employees` (q, status, department_id, shift, sort, order), `POST`, `GET/PATCH/DELETE /employees/{id}` | `employees.view` / `employees.manage` |
| | `GET /employees/lookup?code=`, `POST/GET /employees/{id}/photo`, `GET /employees/{id}/entries`, `/violations` | see docs |
| Cameras | `GET /cameras`, `POST`, `PUT/DELETE /cameras/{id}` | `dashboard.view` / `cameras.manage` |
| | `POST /cameras/{id}/test`, `GET /cameras/{id}/snapshot`, `GET /cameras/{id}/stream` (MJPEG), `POST /cameras/discover` | `cameras.manage` / `cameras.view` |
| Monitoring | `GET /monitoring/status`, `POST /monitoring/check` (multipart: `entry_point_id`, `frame` or `camera_id`, `employee_code`) | `monitoring.view` / `monitoring.operate` |
| Access | `GET /access/doors`, `PATCH /access/doors/{id}`, `POST /access/doors/{id}/command`, `POST …/hardware-approval` | `dashboard.view` / `settings.manage` / `access.override` / `access.hardware` |
| | `GET /access/entries`, `GET /access/events` | `access.view` |
| Violations | `GET /violations`, `GET/PATCH /violations/{id}`, `POST /violations/{id}/notes`, `GET /entries/{id}/evidence` | `violations.view` / `violations.manage` |
| Alerts | `GET /alerts`, `POST /alerts/{id}/acknowledge`, `POST /alerts/read-all` | `alerts.view` / `alerts.manage` |
| Dashboard | `GET /dashboard/summary` | `dashboard.view` |
| Reports | `GET /reports/compliance` (granularity day/week/month), `/shifts`, `/employees`, `/modules`, `/ppe`, `/repeat-violations`, `/entries` | `reports.view`; add `format=csv` → `reports.export` |
| | `GET /reports/audit` | `audit.view` |
| Health | `GET /api/health`, `GET /api/health/ready` | public |

Example — run a check with a browser frame:

```
POST /api/v1/monitoring/check        (multipart/form-data)
  entry_point_id=1   employee_code=NPK-10231   frame=<jpeg>
→ { "passed": false, "decision": "denied", "missing_labels": ["Beard Net"],
    "items": [{ "item": "uniform", "status": "pass", "confidence": 0.95, … }, …],
    "detector": { "simulated": true, … }, "door_result": { "action": "kept_locked", … }, "violation_id": 12 }
```
