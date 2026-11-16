"""Factories, modules, PPE requirements, entry points, departments and factory settings."""
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select

from app.api.deps import DB, Config, CurrentUser, client_ip, ensure_factory_access, require, resolve_factory_id
from app.models import (PPE_ITEMS, Department, DoorController, Employee, EntryLog, EntryPoint, Factory, Module,
                        PPERequirement, User)
from app.schemas.common import entry_point_out, factory_out, module_out
from app.schemas.inputs import (DepartmentIn, EntryPointIn, FactoryIn, ModuleIn, ModuleUpdate, PPEUpdate, SettingsIn)
from app.services.audit import audit
from app.services.entry_pipeline import get_factory_settings

router = APIRouter(tags=["organisation"])
MODULE_COLORS = ["#2B68A8", "#B8621B", "#6A4C9C", "#0E9C8A", "#A63D6B", "#6E7B1F"]


def _check_tz(tz: str) -> None:
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Unknown time zone") from None


def get_module(db, module_id: int, user: User) -> Module:
    m = db.get(Module, module_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Module not found")
    ensure_factory_access(user, m.factory_id)
    return m


def get_entry_point(db, entry_point_id: int, user: User) -> EntryPoint:
    ep = db.get(EntryPoint, entry_point_id)
    if ep is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry point not found")
    ensure_factory_access(user, ep.module.factory_id)
    return ep


# ---------- factories ----------
@router.get("/factories")
def list_factories(db: DB, user: CurrentUser):
    q = select(Factory).order_by(Factory.id)
    if user.factory_id is not None:
        q = q.where(Factory.id == user.factory_id)
    return [factory_out(f) for f in db.scalars(q).all()]


@router.post("/factories", status_code=201)
def create_factory(body: FactoryIn, request: Request, db: DB, user: Annotated[User, Depends(require("settings.manage"))]):
    if user.factory_id is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only users with access to all factories can add a factory")
    _check_tz(body.timezone)
    if db.scalar(select(Factory.id).where(func.upper(Factory.code) == body.code.upper())):
        raise HTTPException(status.HTTP_409_CONFLICT, "A factory with this code already exists")
    f = Factory(name=body.name, code=body.code.upper(), address=body.address, timezone=body.timezone)
    if body.shifts:
        f.shifts = [s.model_dump() for s in body.shifts]
    db.add(f)
    db.flush()
    get_factory_settings(db, f.id)
    audit(db, user, "factory.create", f"Created factory {f.name}", ip=client_ip(request), factory_id=f.id)
    db.commit()
    return factory_out(f)


@router.put("/factories/{factory_id}")
def update_factory(factory_id: int, body: FactoryIn, request: Request, db: DB,
                   user: Annotated[User, Depends(require("settings.manage"))]):
    f = db.get(Factory, resolve_factory_id(db, user, factory_id))
    _check_tz(body.timezone)
    dup = db.scalar(select(Factory.id).where(func.upper(Factory.code) == body.code.upper(), Factory.id != f.id))
    if dup:
        raise HTTPException(status.HTTP_409_CONFLICT, "A factory with this code already exists")
    f.name, f.code, f.address, f.timezone = body.name, body.code.upper(), body.address, body.timezone
    if body.shifts:
        f.shifts = [s.model_dump() for s in body.shifts]
    audit(db, user, "factory.update", f"Updated factory {f.name}", ip=client_ip(request), factory_id=f.id)
    db.commit()
    return factory_out(f)


# ---------- settings ----------
def _settings_out(fs, cfg) -> dict:
    return {"factory_id": fs.factory_id, "confidence_threshold": fs.confidence_threshold,
            "evidence_policy": fs.evidence_policy, "retention_days": fs.retention_days,
            "repeat_threshold": fs.repeat_threshold, "repeat_window_days": fs.repeat_window_days,
            "notifications": fs.notifications or {},
            "system": {"environment": cfg.ENV, "ai_mode": cfg.AI_MODE, "door_mode": cfg.DOOR_MODE,
                       "hardware_doors_enabled": cfg.HARDWARE_DOORS_ENABLED,
                       "session_idle_minutes": cfg.SESSION_IDLE_MINUTES,
                       "session_absolute_hours": cfg.SESSION_ABSOLUTE_HOURS, "max_upload_mb": cfg.MAX_UPLOAD_MB,
                       "smtp_configured": bool(cfg.SMTP_HOST)}}


@router.get("/settings")
def read_settings(db: DB, cfg: Config, user: Annotated[User, Depends(require("settings.view"))],
                  factory_id: int | None = None):
    fs = get_factory_settings(db, resolve_factory_id(db, user, factory_id))
    db.commit()
    return _settings_out(fs, cfg)


@router.put("/settings")
def write_settings(body: SettingsIn, request: Request, db: DB, cfg: Config,
                   user: Annotated[User, Depends(require("settings.manage"))], factory_id: int | None = None):
    fid = resolve_factory_id(db, user, factory_id)
    fs = get_factory_settings(db, fid)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(fs, k, v)
    audit(db, user, "settings.update", "Changed: " + ", ".join(data.keys()), ip=client_ip(request), factory_id=fid)
    db.commit()
    return _settings_out(fs, cfg)


# ---------- modules ----------
@router.get("/modules")
def list_modules(db: DB, user: Annotated[User, Depends(require("dashboard.view"))], factory_id: int | None = None):
    fid = resolve_factory_id(db, user, factory_id)
    return [module_out(m) for m in db.scalars(select(Module).where(Module.factory_id == fid).order_by(Module.id)).all()]


@router.post("/modules", status_code=201)
def create_module(body: ModuleIn, request: Request, db: DB, user: Annotated[User, Depends(require("modules.manage"))],
                  factory_id: int | None = None):
    fid = resolve_factory_id(db, user, factory_id)
    code = body.code.upper()
    if db.scalar(select(Module.id).where(Module.factory_id == fid, Module.code == code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "This module code is already used in this factory")
    count = db.scalar(select(func.count(Module.id)).where(Module.factory_id == fid)) or 0
    m = Module(factory_id=fid, name=body.name, code=code, description=body.description, is_active=body.is_active,
               color=body.color if body.color != "#2B68A8" or count == 0 else MODULE_COLORS[count % len(MODULE_COLORS)])
    required = set(body.required_ppe if body.required_ppe is not None else PPE_ITEMS)
    m.ppe_requirements = [PPERequirement(item=i, required=i in required) for i in PPE_ITEMS]
    db.add(m)
    db.flush()
    if body.first_entry_point:
        _add_entry_point(db, m, body.first_entry_point, True)
    audit(db, user, "module.create", f"Created module {m.name}", ip=client_ip(request), factory_id=fid)
    db.commit()
    db.refresh(m)
    return module_out(m)


@router.patch("/modules/{module_id}")
def update_module(module_id: int, body: ModuleUpdate, request: Request, db: DB,
                  user: Annotated[User, Depends(require("modules.manage"))]):
    m = get_module(db, module_id, user)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(m, k, v)
    audit(db, user, "module.update", f"{m.name}: {', '.join(data.keys())}", ip=client_ip(request), factory_id=m.factory_id)
    db.commit()
    return module_out(m)


@router.delete("/modules/{module_id}")
def delete_module(module_id: int, request: Request, db: DB, user: Annotated[User, Depends(require("modules.manage"))]):
    m = get_module(db, module_id, user)
    if db.scalar(select(func.count(EntryLog.id)).where(EntryLog.module_id == m.id)) or \
            db.scalar(select(func.count(Employee.id)).where(Employee.module_id == m.id)):
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "This module has employees or entry history. Deactivate it instead of deleting.")
    db.delete(m)
    audit(db, user, "module.delete", f"Deleted module {m.name}", ip=client_ip(request), factory_id=m.factory_id)
    db.commit()
    return {"ok": True}


@router.put("/modules/{module_id}/ppe")
def set_ppe(module_id: int, body: PPEUpdate, request: Request, db: DB,
            user: Annotated[User, Depends(require("modules.manage"))]):
    m = get_module(db, module_id, user)
    existing = {r.item: r for r in m.ppe_requirements}
    for rule in body.rules:
        r = existing.get(rule.item)
        if r is None:
            r = PPERequirement(module_id=m.id, item=rule.item)
            m.ppe_requirements.append(r)
        r.required, r.min_confidence = rule.required, rule.min_confidence
    audit(db, user, "ppe.update", f"{m.name}: " + ", ".join(f"{r.item}={'on' if r.required else 'off'}" for r in body.rules),
          ip=client_ip(request), factory_id=m.factory_id)
    db.commit()
    return module_out(m)


def _add_entry_point(db, module: Module, name: str, create_door: bool) -> EntryPoint:
    ep = EntryPoint(module_id=module.id, name=name)
    db.add(ep)
    db.flush()
    if create_door:
        db.add(DoorController(factory_id=module.factory_id, entry_point_id=ep.id, name=f"{name} Door",
                              adapter="simulation", config={}))
    return ep


@router.post("/modules/{module_id}/entry-points", status_code=201)
def add_entry_point(module_id: int, body: EntryPointIn, request: Request, db: DB,
                    user: Annotated[User, Depends(require("modules.manage"))]):
    m = get_module(db, module_id, user)
    if db.scalar(select(EntryPoint.id).where(EntryPoint.module_id == m.id, func.lower(EntryPoint.name) == body.name.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "This module already has an entry point with that name")
    ep = _add_entry_point(db, m, body.name, body.create_door)
    audit(db, user, "entry_point.create", f"{m.name}: added {ep.name}", ip=client_ip(request), factory_id=m.factory_id)
    db.commit()
    return entry_point_out(ep)


@router.delete("/entry-points/{entry_point_id}")
def delete_entry_point(entry_point_id: int, request: Request, db: DB,
                       user: Annotated[User, Depends(require("modules.manage"))]):
    ep = get_entry_point(db, entry_point_id, user)
    if db.scalar(select(func.count(EntryLog.id)).where(EntryLog.entry_point_id == ep.id)):
        ep.is_active = False
        msg = "deactivated (has entry history)"
    else:
        for d in db.scalars(select(DoorController).where(DoorController.entry_point_id == ep.id)).all():
            db.delete(d)
        db.delete(ep)
        msg = "deleted"
    audit(db, user, "entry_point.delete", f"{ep.name}: {msg}", ip=client_ip(request), factory_id=ep.module.factory_id)
    db.commit()
    return {"ok": True, "result": msg}


# ---------- departments ----------
@router.get("/departments")
def list_departments(db: DB, user: Annotated[User, Depends(require("dashboard.view"))], factory_id: int | None = None):
    fid = resolve_factory_id(db, user, factory_id)
    return [{"id": d.id, "name": d.name} for d in
            db.scalars(select(Department).where(Department.factory_id == fid).order_by(Department.name)).all()]


@router.post("/departments", status_code=201)
def create_department(body: DepartmentIn, request: Request, db: DB,
                      user: Annotated[User, Depends(require("modules.manage"))], factory_id: int | None = None):
    fid = resolve_factory_id(db, user, factory_id)
    if db.scalar(select(Department.id).where(Department.factory_id == fid, func.lower(Department.name) == body.name.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "This department already exists")
    d = Department(factory_id=fid, name=body.name)
    db.add(d)
    audit(db, user, "department.create", f"Created department {d.name}", ip=client_ip(request), factory_id=fid)
    db.commit()
    return {"id": d.id, "name": d.name}


@router.delete("/departments/{department_id}")
def delete_department(department_id: int, request: Request, db: DB,
                      user: Annotated[User, Depends(require("modules.manage"))]):
    d = db.get(Department, department_id)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found")
    ensure_factory_access(user, d.factory_id)
    if db.scalar(select(func.count(Employee.id)).where(Employee.department_id == d.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Employees are still assigned to this department")
    db.delete(d)
    audit(db, user, "department.delete", f"Deleted department {d.name}", ip=client_ip(request), factory_id=d.factory_id)
    db.commit()
    return {"ok": True}
