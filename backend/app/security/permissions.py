"""Permission catalogue and the default role matrix (seeded into the database)."""

PERMISSIONS: list[tuple[str, str, str]] = [
    # code, category, description
    ("dashboard.view", "Dashboard", "View the overview dashboard"),
    ("monitoring.view", "Live monitoring", "View live AI monitoring"),
    ("monitoring.operate", "Live monitoring", "Run PPE checks and operate cameras"),
    ("employees.view", "Employees", "View employees and their history"),
    ("employees.manage", "Employees", "Add, edit, deactivate and delete employees"),
    ("modules.view", "Factory modules", "View factory modules and entry points"),
    ("modules.manage", "Factory modules", "Manage modules, entry points and PPE requirements"),
    ("cameras.view", "Cameras", "View cameras and their status"),
    ("cameras.manage", "Cameras", "Add, edit, test and remove cameras"),
    ("access.view", "Access control", "View doors, entry history and access events"),
    ("access.override", "Access control", "Manually lock, unlock or hold doors"),
    ("access.hardware", "Access control", "Approve a door controller for real hardware operation"),
    ("violations.view", "Violations", "View violations and evidence"),
    ("violations.manage", "Violations", "Update violation status and add notes"),
    ("alerts.view", "Alerts", "View alerts"),
    ("alerts.manage", "Alerts", "Acknowledge alerts"),
    ("reports.view", "Reports", "View reports and analytics"),
    ("reports.export", "Reports", "Export reports as CSV"),
    ("audit.view", "Reports", "View audit logs"),
    ("users.view", "Users", "View users and roles"),
    ("users.manage", "Users", "Create, edit and deactivate users"),
    ("roles.manage", "Users", "Edit roles and the permission matrix"),
    ("settings.view", "Settings", "View system settings"),
    ("settings.manage", "Settings", "Change factory and system settings"),
]
ALL_CODES = [p[0] for p in PERMISSIONS]

_VIEW_ALL = [c for c in ALL_CODES if c.endswith(".view")]

DEFAULT_ROLES: list[dict] = [
    {"name": "Super Admin", "rank": 1, "is_superuser": True,
     "description": "Full control of every factory, module and security setting.", "permissions": ALL_CODES},
    {"name": "Factory Admin", "rank": 2,
     "description": "Manages one factory: modules, cameras, doors, employees and users.",
     "permissions": [c for c in ALL_CODES if c not in ("roles.manage", "access.hardware")]},
    {"name": "Security Manager", "rank": 3,
     "description": "Supervises entry compliance, reviews violations, can override doors.",
     "permissions": ["dashboard.view", "monitoring.view", "monitoring.operate", "employees.view", "modules.view",
                     "cameras.view", "access.view", "access.override", "violations.view", "violations.manage",
                     "alerts.view", "alerts.manage", "reports.view", "reports.export", "audit.view"]},
    {"name": "Security Operator", "rank": 4,
     "description": "Monitors live cameras and entry points during a shift.",
     "permissions": ["dashboard.view", "monitoring.view", "monitoring.operate", "cameras.view", "access.view",
                     "violations.view", "alerts.view", "alerts.manage"]},
    {"name": "Viewer", "rank": 5, "description": "Read-only access to dashboards and reports.",
     "permissions": ["dashboard.view", "modules.view", "violations.view", "alerts.view", "reports.view"]},
]
