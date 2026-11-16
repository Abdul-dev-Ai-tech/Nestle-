"""Seed reference data (roles, permissions) and optional demo data.

    python -m app.db.seed                    # reference data + demo factory, users and sample history
    python -m app.db.seed --reference-only   # only roles and permissions (safe for production)
    python -m app.db.seed --no-samples       # demo factory and users, no sample entry history
    python -m app.db.seed --purge-samples    # delete all records created as sample data
    python -m app.db.seed --create-admin you@company.com   # first Super Admin (password from ADMIN_PASSWORD or prompt)

Demo users and sample records are refused when ENV=production.
"""
import argparse
import getpass
import os
import random
import secrets
import string
import sys
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import shift_for, to_zone, utcnow
from app.db.session import SessionLocal
from app.models import (PPE_ITEMS, PPE_LABELS, Alert, Camera, Department, DoorController, Employee, EntryLog,
                        EntryPoint, Factory, FactorySetting, Module, Permission, PPERequirement, Role, User, Violation)
from app.security.passwords import hash_password, password_policy_errors
from app.security.permissions import DEFAULT_ROLES, PERMISSIONS

MODULES = [
    ("Production", "PRD", "Wet mix, filling and forming lines", "#2B68A8", PPE_ITEMS, ["Production Gate A", "Production Gate B"], 22, 1.0),
    ("Processing", "PRC", "Evaporation, drying and CIP zones", "#B8621B", PPE_ITEMS, ["Processing Airlock 1", "Processing Airlock 2"], 16, 0.8),
    ("Packaging", "PKG", "Primary and secondary packing halls", "#6A4C9C", ("uniform", "hair_cap", "face_mask", "safety_shoes"), ["Packaging Hall Entry", "Packaging Mezzanine"], 16, 1.2),
    ("Storage", "STG", "Raw material and finished goods warehouse", "#0E9C8A", ("uniform", "hair_cap", "safety_shoes"), ["Warehouse Dock Door", "Cold Store Entry"], 10, 1.6),
]
DEPARTMENTS = ["Production", "Processing", "Packaging", "Warehouse & Logistics", "Quality Assurance", "Maintenance", "Sanitation"]
DESIGNATIONS = {"PRD": [("Production", "Line Operator"), ("Production", "Machine Operator"), ("Production", "Shift Supervisor"), ("Quality Assurance", "QA Inspector"), ("Maintenance", "Maintenance Technician")],
                "PRC": [("Processing", "Process Operator"), ("Processing", "Dryer Operator"), ("Processing", "CIP Technician"), ("Quality Assurance", "Lab Analyst"), ("Maintenance", "Electrician")],
                "PKG": [("Packaging", "Packing Operator"), ("Packaging", "Filler Operator"), ("Packaging", "Line Lead"), ("Sanitation", "Hygiene Operator")],
                "STG": [("Warehouse & Logistics", "Forklift Operator"), ("Warehouse & Logistics", "Store Keeper"), ("Warehouse & Logistics", "Dispatch Clerk"), ("Warehouse & Logistics", "Inventory Controller")]}
FIRST = ["Ahmed", "Bilal", "Usman", "Hamza", "Imran", "Kashif", "Naveed", "Faisal", "Zubair", "Tariq", "Adnan", "Waqas", "Shahid", "Rizwan", "Asif", "Junaid", "Salman", "Farhan", "Noman", "Irfan",
         "Ayesha", "Fatima", "Sana", "Hina", "Maryam", "Nadia", "Rabia", "Saima", "Zainab", "Amna", "Kiran", "Sadia"]
LAST = ["Khan", "Ahmed", "Malik", "Hussain", "Raza", "Iqbal", "Butt", "Chaudhry", "Sheikh", "Qureshi", "Javed", "Aslam", "Siddiqui", "Akhtar", "Mirza", "Farooq"]
DEMO_USERS = [("Sara Mahmood", "super.admin@example.com", "Super Admin", False), ("Omar Farooqi", "factory.admin@example.com", "Factory Admin", True),
              ("Nida Rehman", "security.manager@example.com", "Security Manager", True), ("Hassan Ali", "security.operator@example.com", "Security Operator", True),
              ("Mehwish Tariq", "viewer@example.com", "Viewer", True)]


def seed_reference(db: Session) -> None:
    """Idempotent: creates missing permissions and built-in roles; never removes custom changes."""
    existing = {p.code: p for p in db.scalars(select(Permission)).all()}
    for code, category, description in PERMISSIONS:
        if code not in existing:
            existing[code] = Permission(code=code, category=category, description=description)
            db.add(existing[code])
    db.flush()
    roles = {r.name: r for r in db.scalars(select(Role)).all()}
    for spec in DEFAULT_ROLES:
        r = roles.get(spec["name"])
        if r is None:
            r = Role(name=spec["name"], description=spec["description"], is_system=True, rank=spec["rank"],
                     is_superuser=spec.get("is_superuser", False), permissions=[existing[c] for c in spec["permissions"]])
            db.add(r)
        elif r.is_superuser:  # Super Admin always holds everything, including newly added permissions
            r.permissions = list(existing.values())
    db.commit()


def _random_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(14)) + secrets.choice("!@#%*") + secrets.choice(string.digits) + "aZ"


def create_admin(db: Session, email: str, password: str, name: str = "Administrator") -> User:
    errors = password_policy_errors(password, email=email)
    if errors:
        raise SystemExit("Password needs: " + ", ".join(errors))
    if db.scalar(select(User.id).where(User.email == email.lower())):
        raise SystemExit("A user with this e-mail already exists")
    role = db.scalar(select(Role).where(Role.is_superuser.is_(True)))
    u = User(email=email.lower(), full_name=name, password_hash=hash_password(password), roles=[role], factory_id=None)
    db.add(u)
    db.commit()
    return u


def seed_demo(db: Session, *, samples: bool = True, password: str | None = None, quiet: bool = False,
              days: int = 30, rng_seed: int = 20261113) -> dict:
    if get_settings().is_production:
        raise SystemExit("Refusing to create demo users or sample data when ENV=production.")
    if db.scalar(select(Factory.id).where(Factory.code == "PK-SKP")):
        if not quiet:
            print("Demo factory already exists — nothing to do.")
        return {}
    rng = random.Random(rng_seed)
    factory = Factory(name="Sheikhupura Factory", code="PK-SKP", timezone="Asia/Karachi",
                      address="29 km Lahore–Sheikhupura Road, Sheikhupura, Punjab")
    db.add(factory)
    db.flush()
    db.add(FactorySetting(factory_id=factory.id, confidence_threshold=0.6, retention_days=365, notifications={
        "ppe_violation": {"app": True, "email": False}, "repeat_violation": {"app": True, "email": False},
        "camera_offline": {"app": True, "email": False}, "door_fault": {"app": True, "email": False},
        "manual_override": {"app": True, "email": False}}))
    depts = {n: Department(factory_id=factory.id, name=n) for n in DEPARTMENTS}
    db.add_all(depts.values())
    modules, eps = {}, {}
    for name, code, desc, color, required, points, _, _ in MODULES:
        m = Module(factory_id=factory.id, name=name, code=code, description=desc, color=color)
        m.ppe_requirements = [PPERequirement(item=i, required=i in required) for i in PPE_ITEMS]
        db.add(m)
        db.flush()
        modules[code] = m
        eps[code] = []
        for p in points:
            ep = EntryPoint(module_id=m.id, name=p)
            db.add(ep)
            db.flush()
            eps[code].append(ep)
            db.add(DoorController(factory_id=factory.id, entry_point_id=ep.id, name=f"{p} Door", adapter="simulation", config={}))
    # Cameras: one browser camera, one server-side USB webcam, and two inactive RTSP examples to edit.
    db.add_all([
        Camera(factory_id=factory.id, entry_point_id=eps["PRD"][0].id, name="Gate A operator camera", type="browser"),
        Camera(factory_id=factory.id, entry_point_id=eps["PRD"][1].id, name="USB webcam (server)", type="usb", source="0"),
        Camera(factory_id=factory.id, entry_point_id=eps["PRC"][0].id, name="Example IP camera 1 (edit address)", type="rtsp",
               source="rtsp://192.0.2.21:554/stream1", is_active=False),
        Camera(factory_id=factory.id, entry_point_id=eps["PKG"][0].id, name="Example IP camera 2 (edit address)", type="rtsp",
               source="rtsp://192.0.2.22:554/stream1", is_active=False)])
    # Demo users
    password = password or os.environ.get("SEED_PASSWORD") or _random_password()
    errors = password_policy_errors(password)
    if errors:
        raise SystemExit("SEED_PASSWORD needs: " + ", ".join(errors))
    pw_hash = hash_password(password)
    roles = {r.name: r for r in db.scalars(select(Role)).all()}
    for name, email, role, scoped in DEMO_USERS:
        db.add(User(full_name=name, email=email, password_hash=pw_hash, roles=[roles[role]],
                    factory_id=factory.id if scoped else None))
    # Employees
    employees, used, code_no = [], set(), 10231
    for name, code, *_rest, headcount, factor in MODULES:
        for _ in range(headcount):
            while True:
                fi = rng.randrange(len(FIRST))
                full = f"{FIRST[fi]} {rng.choice(LAST)}"
                if full not in used:
                    used.add(full)
                    break
            dept, desig = rng.choice(DESIGNATIONS[code])
            code_no += rng.randint(1, 7)
            e = Employee(factory_id=factory.id, module_id=modules[code].id, department_id=depts[dept].id,
                         employee_code=f"NPK-{code_no}", full_name=full, designation=desig,
                         shift=rng.choice(["A", "A", "B", "B", "C"]), beard_net_applicable=fi < 20 and rng.random() < 0.45,
                         status="active" if rng.random() > 0.06 else "inactive")
            e._risk, e._factor, e._code = (6.0 if rng.random() < 0.09 else 0.5 + rng.random()), factor, code  # type: ignore[attr-defined]
            employees.append(e)
    db.add_all(employees)
    db.flush()
    n_entries = _seed_samples(db, factory, modules, eps, employees, rng, days) if samples else 0
    db.commit()
    if not quiet:
        print("\nDemo data created." + (f" {n_entries} sample entries (flagged source='sample')." if samples else ""))
        print("Demo sign-in accounts (development only — never use in production):")
        for name, email, role, _ in DEMO_USERS:
            print(f"  {role:<18} {email}")
        print(f"  Password for all demo accounts: {password}\n")
    return {"factory_id": factory.id, "password": password, "entries": n_entries}


def _seed_samples(db, factory, modules, eps, employees, rng, days) -> int:
    """Generated history so dashboards and reports have something to show. Every row is source='sample'."""
    now = utcnow()
    local_midnight = to_zone(now, factory.timezone).replace(hour=0, minute=0, second=0, microsecond=0)
    req = {code: {r.item for r in m.ppe_requirements if r.required} for code, m in modules.items()}
    entries = []
    for d in range(days - 1, -1, -1):
        day = local_midnight - timedelta(days=d)
        day_factor = 0.75 + rng.random() * 0.7
        for e in employees:
            if e.status != "active" or rng.random() < 0.14:
                continue
            start = {"A": 6, "B": 14, "C": 22}[e.shift]
            for i, off in enumerate((0, 2.6, 5.2)):
                if i and rng.random() < 0.25:
                    continue
                t = day + timedelta(hours=start + off, minutes=(rng.random() - 0.3) * 30)
                if t > now:
                    continue
                required = [i for i in PPE_ITEMS if i in req[e._code] and (i != "beard_net" or e.beard_net_applicable)]
                missing = [i for i in required if rng.random() < 0.0065 * e._factor * e._risk * day_factor]
                ep = rng.choice(eps[e._code])
                entries.append(EntryLog(factory_id=factory.id, module_id=e.module_id, entry_point_id=ep.id, employee_id=e.id,
                                        occurred_at=t.astimezone(now.tzinfo), passed=not missing,
                                        decision="denied" if missing else "granted", missing_items=missing,
                                        shift=shift_for(t, factory.shifts), source="sample"))
    entries.sort(key=lambda x: x.occurred_at)
    db.add_all(entries)
    db.flush()
    recent_by_emp: dict[int, list] = {}
    emp_by_id = {e.id: e for e in employees}
    ep_names = {p.id: p.name for pts in eps.values() for p in pts}
    for en in entries:
        if en.passed:
            continue
        hist = [t for t in recent_by_emp.get(en.employee_id, []) if en.occurred_at - t <= timedelta(days=7)]
        is_repeat = len(hist) + 1 >= 3
        recent_by_emp[en.employee_id] = hist + [en.occurred_at]
        age = (now - en.occurred_at).total_seconds() / 86400
        x = rng.random()
        status = ("open" if x < 0.7 else "under_review") if age < 1 else \
            ("resolved" if x < 0.76 else "escalated" if x < 0.86 else "under_review" if x < 0.95 else "open")
        sev = "critical" if is_repeat else ("high" if len(en.missing_items) >= 2 or "uniform" in en.missing_items else "medium")
        v = Violation(factory_id=factory.id, module_id=en.module_id, entry_log_id=en.id, employee_id=en.employee_id,
                      missing_items=en.missing_items, severity=sev, status=status, is_repeat=is_repeat, created_at=en.occurred_at,
                      resolved_at=en.occurred_at + timedelta(hours=6) if status == "resolved" else None)
        db.add(v)
        if age < 0.6:
            db.flush()
            who = emp_by_id[en.employee_id].full_name
            db.add(Alert(factory_id=factory.id, type="ppe_violation", severity="high" if sev != "medium" else "medium",
                         title=f"{who} — entry denied", created_at=en.occurred_at, ref_type="violation", ref_id=v.id,
                         detail="Missing " + ", ".join(PPE_LABELS[i] for i in en.missing_items) + f" at {ep_names[en.entry_point_id]} (sample data)"))
    return len(entries)


def purge_samples(db: Session) -> int:
    ids = list(db.scalars(select(EntryLog.id).where(EntryLog.source == "sample")).all())
    if ids:
        vids = list(db.scalars(select(Violation.id).where(Violation.entry_log_id.in_(ids))).all())
        if vids:
            db.execute(delete(Alert).where(Alert.ref_type == "violation", Alert.ref_id.in_(vids)))
            db.execute(delete(Violation).where(Violation.id.in_(vids)))
        db.execute(delete(EntryLog).where(EntryLog.id.in_(ids)))
    db.commit()
    return len(ids)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reference-only", action="store_true")
    ap.add_argument("--no-samples", action="store_true")
    ap.add_argument("--purge-samples", action="store_true")
    ap.add_argument("--create-admin", metavar="EMAIL")
    ap.add_argument("--ensure-admin", metavar="EMAIL",
                    help="create this Super Admin (password from ADMIN_PASSWORD) unless the account already exists")
    args = ap.parse_args(argv)
    with SessionLocal() as db:
        seed_reference(db)
        print("Roles and permissions are in place.")
        if args.purge_samples:
            print(f"Removed {purge_samples(db)} sample entries.")
        elif args.ensure_admin:
            if db.scalar(select(User.id).where(User.email == args.ensure_admin.lower().strip())):
                print(f"Admin {args.ensure_admin} already exists - unchanged.")
            elif not os.environ.get("ADMIN_PASSWORD"):
                raise SystemExit("--ensure-admin needs the ADMIN_PASSWORD environment variable")
            else:
                create_admin(db, args.ensure_admin.strip(), os.environ["ADMIN_PASSWORD"])
                print(f"Super Admin {args.ensure_admin} created.")
        elif args.create_admin:
            pw = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password for the new Super Admin: ")
            create_admin(db, args.create_admin, pw)
            print(f"Super Admin {args.create_admin} created.")
        elif not args.reference_only:
            seed_demo(db, samples=not args.no_samples)


if __name__ == "__main__":
    sys.exit(main())
