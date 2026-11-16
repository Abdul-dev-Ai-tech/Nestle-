from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select, update

from app.api.deps import DB, client_ip, ensure_factory_access, require, resolve_factory_id
from app.core.time import local_day_bounds, utcnow
from app.models import Alert, Employee, EntryLog, Factory, User, Violation, ViolationNote
from app.schemas.common import alert_out, page, violation_out
from app.schemas.inputs import NoteIn, ViolationUpdate
from app.services import storage
from app.services.audit import audit

router = APIRouter(tags=["violations & alerts"])
VView = Annotated[User, Depends(require("violations.view"))]
VManage = Annotated[User, Depends(require("violations.manage"))]
STATUS_LABEL = {"open": "Open", "under_review": "Under review", "escalated": "Escalated", "resolved": "Resolved"}


def _violation(db, violation_id: int, user: User) -> Violation:
    v = db.get(Violation, violation_id)
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Violation not found")
    ensure_factory_access(user, v.factory_id)
    return v


def violations_query(db, user, factory_id, *, module_id=None, status_=None, item=None, severity=None, q="",
                     date_from=None, date_to=None, repeat_only=False):
    fid = resolve_factory_id(db, user, factory_id)
    tz = db.get(Factory, fid).timezone
    stmt = select(Violation).where(Violation.factory_id == fid)
    if module_id:
        stmt = stmt.where(Violation.module_id == module_id)
    if status_:
        stmt = stmt.where(Violation.status == status_)
    if severity:
        stmt = stmt.where(Violation.severity == severity)
    if repeat_only:
        stmt = stmt.where(Violation.is_repeat.is_(True))
    if date_from:
        stmt = stmt.where(Violation.created_at >= local_day_bounds(date_from, tz)[0])
    if date_to:
        stmt = stmt.where(Violation.created_at < local_day_bounds(date_to, tz)[1])
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.outerjoin(Employee, Employee.id == Violation.employee_id).where(
            or_(func.lower(Employee.full_name).like(like), func.lower(Employee.employee_code).like(like)))
    return stmt, item


@router.get("/violations")
def list_violations(db: DB, user: VView, factory_id: int | None = None, module_id: int | None = None,
                    status_: Annotated[Literal["open", "under_review", "escalated", "resolved"] | None,
                                       Query(alias="status")] = None,
                    item: Literal["uniform", "hair_cap", "face_mask", "beard_net", "safety_shoes"] | None = None,
                    severity: Literal["medium", "high", "critical"] | None = None, q: str = Query("", max_length=80),
                    date_from: date | None = None, date_to: date | None = None, repeat_only: bool = False,
                    page_no: Annotated[int, Query(alias="page", ge=1)] = 1,
                    page_size: Annotated[int, Query(ge=1, le=100)] = 10):
    stmt, item = violations_query(db, user, factory_id, module_id=module_id, status_=status_, item=item,
                                  severity=severity, q=q, date_from=date_from, date_to=date_to, repeat_only=repeat_only)
    ordered = stmt.order_by(Violation.created_at.desc())
    if item:  # JSON list filter done in Python to stay database-portable
        rows = [v for v in db.scalars(ordered.limit(5000)).all() if item in (v.missing_items or [])]
        total, rows = len(rows), rows[(page_no - 1) * page_size: page_no * page_size]
    else:
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = db.scalars(ordered.offset((page_no - 1) * page_size).limit(page_size)).all()
    base, _ = violations_query(db, user, factory_id, module_id=module_id, date_from=date_from, date_to=date_to)
    sub = base.subquery()
    counts = dict(db.execute(select(sub.c.status, func.count()).group_by(sub.c.status)).all())
    return {**page([violation_out(v) for v in rows], total, page_no, page_size),
            "counts": {k: counts.get(k, 0) for k in STATUS_LABEL}}


@router.get("/violations/{violation_id}")
def get_violation(violation_id: int, db: DB, user: VView):
    v = _violation(db, violation_id, user)
    out = violation_out(v, detail=True)
    if v.employee_id:
        out["employee_violation_count"] = db.scalar(select(func.count(Violation.id))
                                                    .where(Violation.employee_id == v.employee_id)) or 0
    return out


@router.patch("/violations/{violation_id}")
def update_violation(violation_id: int, body: ViolationUpdate, request: Request, db: DB, user: VManage):
    v = _violation(db, violation_id, user)
    old = v.status
    v.status = body.status
    v.resolved_at, v.resolved_by = (utcnow(), user.id) if body.status == "resolved" else (None, None)
    text = f"Status changed from {STATUS_LABEL[old]} to {STATUS_LABEL[body.status]}." + (f" {body.note}" if body.note else "")
    db.add(ViolationNote(violation_id=v.id, user_id=user.id, author=user.full_name, text=text[:500]))
    audit(db, user, "violation.update", f"Violation #{v.id}: {old} -> {body.status}", ip=client_ip(request),
          factory_id=v.factory_id)
    db.commit()
    db.refresh(v)
    return violation_out(v, detail=True)


@router.post("/violations/{violation_id}/notes", status_code=201)
def add_note(violation_id: int, body: NoteIn, request: Request, db: DB, user: VManage):
    v = _violation(db, violation_id, user)
    db.add(ViolationNote(violation_id=v.id, user_id=user.id, author=user.full_name, text=body.text))
    audit(db, user, "violation.note", f"Note added to violation #{v.id}", ip=client_ip(request), factory_id=v.factory_id)
    db.commit()
    db.refresh(v)
    return violation_out(v, detail=True)


@router.get("/entries/{entry_id}/evidence")
def evidence(entry_id: int, request: Request, db: DB, user: VView):
    """Evidence frames are private: served only to signed-in users with violations.view, and audited."""
    e = db.get(EntryLog, entry_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entry not found")
    ensure_factory_access(user, e.factory_id)
    path = storage.resolve(e.evidence_path)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No evidence image is stored for this entry")
    audit(db, user, "evidence.view", f"Viewed evidence for entry #{e.id}", ip=client_ip(request), factory_id=e.factory_id)
    db.commit()
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})


# ---------- alerts ----------
AView = Annotated[User, Depends(require("alerts.view"))]


@router.get("/alerts")
def list_alerts(db: DB, user: AView, factory_id: int | None = None,
                filter_: Annotated[Literal["all", "unread", "open", "critical"], Query(alias="filter")] = "all",
                page_no: Annotated[int, Query(alias="page", ge=1)] = 1,
                page_size: Annotated[int, Query(ge=1, le=100)] = 20):
    fid = resolve_factory_id(db, user, factory_id)
    base = select(Alert).where(Alert.factory_id == fid)
    stmt = base
    if filter_ == "unread":
        stmt = stmt.where(Alert.read_at.is_(None))
    elif filter_ == "open":
        stmt = stmt.where(Alert.acknowledged_at.is_(None))
    elif filter_ == "critical":
        stmt = stmt.where(Alert.severity == "critical")
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Alert.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size)).all()
    unread = db.scalar(select(func.count(Alert.id)).where(Alert.factory_id == fid, Alert.read_at.is_(None))) or 0
    unack = db.scalar(select(func.count(Alert.id)).where(Alert.factory_id == fid, Alert.acknowledged_at.is_(None))) or 0
    return {**page([alert_out(a) for a in rows], total, page_no, page_size), "unread": unread, "unacknowledged": unack}


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge(alert_id: int, request: Request, db: DB, user: Annotated[User, Depends(require("alerts.manage"))]):
    a = db.get(Alert, alert_id)
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    ensure_factory_access(user, a.factory_id)
    now = utcnow()
    a.acknowledged_at, a.acknowledged_by, a.read_at = now, user.id, a.read_at or now
    audit(db, user, "alert.acknowledge", f"Acknowledged alert #{a.id}: {a.title}", ip=client_ip(request),
          factory_id=a.factory_id)
    db.commit()
    return alert_out(a)


@router.post("/alerts/read-all")
def read_all(db: DB, user: AView, factory_id: int | None = None):
    fid = resolve_factory_id(db, user, factory_id)
    n = db.execute(update(Alert).where(Alert.factory_id == fid, Alert.read_at.is_(None)).values(read_at=utcnow())).rowcount
    db.commit()
    return {"updated": n or 0}
