from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.deps import DB, Config, require, resolve_factory_id
from app.core.time import local_day_bounds, to_zone, utcnow
from app.models import Alert, Camera, DoorController, EntryLog, EntryPoint, Factory, Module, User, Violation
from app.schemas.common import alert_out, camera_out, door_out, entry_out, factory_out, violation_out
from app.services import analytics as an

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(db: DB, cfg: Config, user: Annotated[User, Depends(require("dashboard.view"))],
            factory_id: int | None = None, module_id: int | None = None):
    fid = resolve_factory_id(db, user, factory_id)
    factory = db.get(Factory, fid)
    now = utcnow()
    today = to_zone(now, factory.timezone).date()
    day_start, _ = local_day_bounds(today, factory.timezone)
    start30 = local_day_bounds(today - timedelta(days=29), factory.timezone)[0]
    rows = an.fetch(db, fid, start30, now + timedelta(seconds=1), module_id)
    today_rows = [r for r in rows if r.occurred_at >= day_start]
    yday_rows = [r for r in rows if day_start - timedelta(days=1) <= r.occurred_at <= now - timedelta(days=1)]
    week_start = local_day_bounds(today - timedelta(days=6), factory.timezone)[0]
    week_rows = [r for r in rows if r.occurred_at >= week_start]

    modules = db.scalars(select(Module).where(Module.factory_id == fid, Module.is_active.is_(True)).order_by(Module.id)).all()
    if module_id:
        modules = [m for m in modules if m.id == module_id]
    per_module = an.by_key(week_rows, lambda r: r.module_id)

    vq = select(func.count(Violation.id)).where(Violation.factory_id == fid, Violation.status == "open")
    cq = select(Camera).where(Camera.factory_id == fid).order_by(Camera.id)
    dq = select(DoorController).where(DoorController.factory_id == fid).order_by(DoorController.id)
    eq = select(EntryLog).where(EntryLog.factory_id == fid)
    rvq = select(Violation).where(Violation.factory_id == fid)
    if module_id:
        vq = vq.where(Violation.module_id == module_id)
        cq = cq.join(EntryPoint, EntryPoint.id == Camera.entry_point_id).where(EntryPoint.module_id == module_id)
        dq = dq.join(EntryPoint, EntryPoint.id == DoorController.entry_point_id).where(EntryPoint.module_id == module_id)
        eq = eq.where(EntryLog.module_id == module_id)
        rvq = rvq.where(Violation.module_id == module_id)
    cameras = [camera_out(c) for c in db.scalars(cq).all()]
    doors = [door_out(d) for d in db.scalars(dq).all()]
    alerts_q = select(Alert).where(Alert.factory_id == fid, Alert.acknowledged_at.is_(None))
    active_alerts = db.scalars(alerts_q.order_by(Alert.created_at.desc()).limit(5)).all()
    out = {
        "factory": factory_out(factory), "generated_at": now.isoformat(),
        "today": an.totals(today_rows), "yesterday_same_time": an.totals(yday_rows),
        "open_violations": db.scalar(vq) or 0,
        "alerts": {"unacknowledged": db.scalar(select(func.count()).select_from(alerts_q.subquery())) or 0,
                   "critical": db.scalar(select(func.count()).select_from(
                       alerts_q.where(Alert.severity == "critical").subquery())) or 0,
                   "unread": db.scalar(select(func.count(Alert.id)).where(Alert.factory_id == fid,
                                                                          Alert.read_at.is_(None))) or 0,
                   "items": [alert_out(a) for a in active_alerts]},
        "daily": an.series(rows, factory.timezone, "day", fill=(today - timedelta(days=29), today)),
        "by_module": [{"module_id": m.id, "name": m.name, "color": m.color, "entries": per_module[m.id][0],
                       "failed": per_module[m.id][0] - per_module[m.id][1],
                       "compliance": an.pct(per_module[m.id][1], per_module[m.id][0])} for m in modules],
        "missing_ppe": an.missing_counts(week_rows),
        "cameras": cameras, "doors": doors,
        "recent_entries": [entry_out(e) for e in db.scalars(eq.order_by(EntryLog.occurred_at.desc()).limit(7)).all()],
        "recent_violations": [violation_out(v) for v in db.scalars(rvq.order_by(Violation.created_at.desc()).limit(5)).all()],
        "data_sources": an.sources(rows), "ai_mode": cfg.AI_MODE, "door_mode": cfg.DOOR_MODE,
    }
    db.commit()
    return out
