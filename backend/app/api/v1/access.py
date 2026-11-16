from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select

from app.access_control.service import DoorActionRefused, manual_command
from app.api.deps import DB, Config, client_ip, ensure_factory_access, require, resolve_factory_id
from app.core.time import local_day_bounds, utcnow
from app.models import AccessEvent, Alert, DoorController, Employee, EntryLog, EntryPoint, Factory, User
from app.schemas.common import access_event_out, door_out, entry_out, page
from app.schemas.inputs import DoorCommand, DoorUpdate, HardwareApproval
from app.services.audit import audit

router = APIRouter(prefix="/access", tags=["access control"])
View = Annotated[User, Depends(require("access.view"))]


def _door(db, door_id: int, user: User) -> DoorController:
    d = db.get(DoorController, door_id)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Door not found")
    ensure_factory_access(user, d.factory_id)
    return d


@router.get("/doors")
def list_doors(db: DB, user: Annotated[User, Depends(require("dashboard.view"))], factory_id: int | None = None,
               module_id: int | None = None):
    fid = resolve_factory_id(db, user, factory_id)
    q = select(DoorController).where(DoorController.factory_id == fid).order_by(DoorController.id)
    if module_id:
        q = q.join(EntryPoint, EntryPoint.id == DoorController.entry_point_id).where(EntryPoint.module_id == module_id)
    doors = db.scalars(q).all()
    out = [door_out(d) for d in doors]
    db.commit()  # persist timed re-locks
    return out


@router.patch("/doors/{door_id}")
def update_door(door_id: int, body: DoorUpdate, request: Request, db: DB,
                user: Annotated[User, Depends(require("settings.manage"))]):
    d = _door(db, door_id, user)
    data = body.model_dump(exclude_unset=True)
    if "adapter" in data and data["adapter"] != d.adapter:
        d.hardware_approved_at = d.hardware_approved_by = None  # a new adapter always needs a new approval
    if "config" in data:
        d.hardware_approved_at = d.hardware_approved_by = None
        if any(k for k in (data["config"] or {}) if "pass" in k.lower() or "secret" in k.lower() or "token" in k.lower()):
            raise HTTPException(422, "Do not store secrets in the door configuration")
    for k, v in data.items():
        setattr(d, k, v)
    audit(db, user, "door.config", f"{d.name}: {', '.join(data.keys())}", ip=client_ip(request), factory_id=d.factory_id)
    db.commit()
    return door_out(d)


@router.post("/doors/{door_id}/command")
def door_command(door_id: int, body: DoorCommand, request: Request, db: DB,
                 user: Annotated[User, Depends(require("access.override"))]):
    d = _door(db, door_id, user)
    try:
        ev = manual_command(db, d, body.command, actor=user, reason=body.reason)
    except DoorActionRefused as exc:
        db.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    if body.command in ("unlock", "hold"):
        db.add(Alert(factory_id=d.factory_id, type="manual_override", severity="medium",
                     title=f"Manual {'unlock' if body.command == 'unlock' else 'hold open'}: {d.name}",
                     detail=f"By {user.full_name}. Reason: {body.reason}"[:400], ref_type="door", ref_id=d.id))
    audit(db, user, "door.override", f"{d.name}: {ev.type} — {body.reason}" + (" (simulated)" if ev.simulated else ""),
          ip=client_ip(request), factory_id=d.factory_id)
    db.commit()
    return {"door": door_out(d), "event": access_event_out(ev)}


@router.post("/doors/{door_id}/hardware-approval")
def hardware_approval(door_id: int, body: HardwareApproval, request: Request, db: DB, cfg: Config,
                      user: Annotated[User, Depends(require("access.hardware"))]):
    """Record (or withdraw) the explicit approval required before a real controller is driven."""
    d = _door(db, door_id, user)
    if body.approve:
        if d.adapter == "simulation":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Select a hardware adapter for this door first")
        if not (cfg.DOOR_MODE == "hardware" and cfg.HARDWARE_DOORS_ENABLED):
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "Hardware door control is disabled on this server (DOOR_MODE / HARDWARE_DOORS_ENABLED)")
        if body.confirmation.strip() != d.name:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Type the door name exactly to confirm")
        d.hardware_approved_by, d.hardware_approved_at = user.id, utcnow()
    else:
        d.hardware_approved_by = d.hardware_approved_at = None
    audit(db, user, "door.hardware_approval", f"{d.name}: {'approved' if body.approve else 'withdrawn'}",
          ip=client_ip(request), factory_id=d.factory_id)
    db.commit()
    return door_out(d)


@router.get("/events")
def list_events(db: DB, user: View, factory_id: int | None = None, module_id: int | None = None,
                page_no: Annotated[int, Query(alias="page", ge=1)] = 1,
                page_size: Annotated[int, Query(ge=1, le=100)] = 20, manual_only: bool = False):
    fid = resolve_factory_id(db, user, factory_id)
    q = select(AccessEvent).where(AccessEvent.factory_id == fid)
    if manual_only:
        q = q.where(AccessEvent.type.notin_(["auto_unlock", "denied"]))
    if module_id:
        q = q.join(DoorController, DoorController.id == AccessEvent.door_id) \
             .join(EntryPoint, EntryPoint.id == DoorController.entry_point_id).where(EntryPoint.module_id == module_id)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(AccessEvent.occurred_at.desc()).offset((page_no - 1) * page_size).limit(page_size)).all()
    return page([access_event_out(r) for r in rows], total, page_no, page_size)


def entries_query(db, user: User, factory_id: int | None, *, module_id=None, result=None, q="", date_from=None,
                  date_to=None, employee_id=None):
    fid = resolve_factory_id(db, user, factory_id)
    tz = db.get(Factory, fid).timezone
    stmt = select(EntryLog).where(EntryLog.factory_id == fid)
    if module_id:
        stmt = stmt.where(EntryLog.module_id == module_id)
    if result == "granted":
        stmt = stmt.where(EntryLog.passed.is_(True))
    elif result == "denied":
        stmt = stmt.where(EntryLog.passed.is_(False))
    if employee_id:
        stmt = stmt.where(EntryLog.employee_id == employee_id)
    if date_from:
        stmt = stmt.where(EntryLog.occurred_at >= local_day_bounds(date_from, tz)[0])
    if date_to:
        stmt = stmt.where(EntryLog.occurred_at < local_day_bounds(date_to, tz)[1])
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.outerjoin(Employee, Employee.id == EntryLog.employee_id).where(
            or_(func.lower(Employee.full_name).like(like), func.lower(Employee.employee_code).like(like)))
    return stmt


@router.get("/entries")
def list_entries(db: DB, user: View, factory_id: int | None = None, module_id: int | None = None,
                 result: Literal["granted", "denied"] | None = None, q: str = Query("", max_length=80),
                 date_from: date | None = None, date_to: date | None = None,
                 page_no: Annotated[int, Query(alias="page", ge=1)] = 1,
                 page_size: Annotated[int, Query(ge=1, le=100)] = 20):
    stmt = entries_query(db, user, factory_id, module_id=module_id, result=result, q=q, date_from=date_from,
                         date_to=date_to)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(EntryLog.occurred_at.desc()).offset((page_no - 1) * page_size).limit(page_size)).all()
    return page([entry_out(r) for r in rows], total, page_no, page_size)
