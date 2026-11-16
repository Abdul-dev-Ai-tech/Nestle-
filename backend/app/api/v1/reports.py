import csv
import io
from collections import Counter, defaultdict
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import func, select

from app.api.deps import DB, client_ip, require, resolve_factory_id
from app.api.v1.access import entries_query
from app.core.time import to_zone
from app.models import PPE_ITEMS, PPE_LABELS, AuditLog, Employee, EntryLog, Factory, Module, PPERequirement, User
from app.schemas.common import entry_out, iso, page
from app.services import analytics as an
from app.services.audit import audit

router = APIRouter(prefix="/reports", tags=["reports"])
View = Annotated[User, Depends(require("reports.view"))]
Fmt = Annotated[Literal["json", "csv"], Query(alias="format")]


def _safe(v) -> str:
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s  # CSV formula-injection guard


def _csv(db, request: Request, user: User, name: str, header: list[str], rows: list[list], factory_id: int) -> Response:
    if not user.is_superuser and "reports.export" not in user.permission_codes:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have permission to export reports")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows([[_safe(c) for c in r] for r in rows])
    audit(db, user, "report.export", f"{name} ({len(rows)} rows, CSV)", ip=client_ip(request), factory_id=factory_id)
    db.commit()
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}_{date.today().isoformat()}.csv"'})


def _ctx(db, user, factory_id, date_from, date_to, module_id):
    fid = resolve_factory_id(db, user, factory_id)
    factory = db.get(Factory, fid)
    d1, d2, start, end = an.date_range(factory, date_from, date_to)
    return fid, factory, d1, d2, an.fetch(db, fid, start, end, module_id)


@router.get("/compliance")
def compliance(request: Request, db: DB, user: View, factory_id: int | None = None, module_id: int | None = None,
               date_from: date | None = None, date_to: date | None = None,
               granularity: Literal["day", "week", "month"] = "day", fmt: Fmt = "json"):
    fid, factory, d1, d2, rows = _ctx(db, user, factory_id, date_from, date_to, module_id)
    data = an.series(rows, factory.timezone, granularity, fill=(d1, d2))
    if fmt == "csv":
        return _csv(db, request, user, f"{granularity}_compliance", ["Period", "Entries", "Successful", "Failed", "Compliance %"],
                    [[r["label"], r["entries"], r["passed"], r["failed"], r["compliance"]] for r in data], fid)
    return {"from": d1.isoformat(), "to": d2.isoformat(), "granularity": granularity, "totals": an.totals(rows),
            "series": data, "data_sources": an.sources(rows)}


@router.get("/shifts")
def shifts(request: Request, db: DB, user: View, factory_id: int | None = None, module_id: int | None = None,
           date_from: date | None = None, date_to: date | None = None, fmt: Fmt = "json"):
    fid, factory, d1, d2, rows = _ctx(db, user, factory_id, date_from, date_to, module_id)
    groups = an.by_key(rows, lambda r: r.shift or "—")
    defs = {s["code"]: f'{s["start"]}–{s["end"]}' for s in factory.shifts or []}
    data = [{"shift": k, "hours": defs.get(k, ""), "entries": n, "passed": ok, "failed": n - ok,
             "compliance": an.pct(ok, n)} for k, (n, ok) in sorted(groups.items())]
    if fmt == "csv":
        return _csv(db, request, user, "shift_report", ["Shift", "Hours", "Entries", "Successful", "Failed", "Compliance %"],
                    [[r["shift"], r["hours"], r["entries"], r["passed"], r["failed"], r["compliance"]] for r in data], fid)
    return {"from": d1.isoformat(), "to": d2.isoformat(), "rows": data}


def _employee_rows(db, rows):
    groups: dict = defaultdict(lambda: {"n": 0, "f": 0, "items": Counter(), "last": None})
    for r in rows:
        if r.employee_id is None:
            continue
        g = groups[r.employee_id]
        g["n"] += 1
        if not r.passed:
            g["f"] += 1
            g["items"].update(r.missing_items or [])
            g["last"] = max(g["last"], r.occurred_at) if g["last"] else r.occurred_at
    emps = {e.id: e for e in db.scalars(select(Employee).where(Employee.id.in_(list(groups) or [0]))).all()}
    out = []
    for eid, g in groups.items():
        e = emps.get(eid)
        if e is None:
            continue
        top = g["items"].most_common(1)
        out.append({"employee_id": eid, "employee_code": e.employee_code, "full_name": e.full_name,
                    "department": e.department.name if e.department else "", "module": e.module.name if e.module else "",
                    "entries": g["n"], "violations": g["f"], "compliance": an.pct(g["n"] - g["f"], g["n"]),
                    "most_missed": f"{PPE_LABELS[top[0][0]]} ({top[0][1]}×)" if top else "",
                    "last_violation_at": iso(g["last"])})
    return sorted(out, key=lambda r: (-r["violations"], -r["entries"]))


@router.get("/employees")
def employees(request: Request, db: DB, user: View, factory_id: int | None = None, module_id: int | None = None,
              date_from: date | None = None, date_to: date | None = None, fmt: Fmt = "json"):
    fid, factory, d1, d2, rows = _ctx(db, user, factory_id, date_from, date_to, module_id)
    data = _employee_rows(db, rows)
    if fmt == "csv":
        return _csv(db, request, user, "employee_compliance",
                    ["Employee ID", "Employee", "Department", "Module", "Entries", "Violations", "Compliance %"],
                    [[r["employee_code"], r["full_name"], r["department"], r["module"], r["entries"], r["violations"],
                      r["compliance"]] for r in data], fid)
    return {"from": d1.isoformat(), "to": d2.isoformat(), "rows": data}


@router.get("/repeat-violations")
def repeat_violations(request: Request, db: DB, user: View, factory_id: int | None = None,
                      module_id: int | None = None, date_from: date | None = None, date_to: date | None = None,
                      min_count: Annotated[int, Query(ge=2, le=50)] = 2, fmt: Fmt = "json"):
    fid, factory, d1, d2, rows = _ctx(db, user, factory_id, date_from, date_to, module_id)
    data = [r for r in _employee_rows(db, rows) if r["violations"] >= min_count]
    if fmt == "csv":
        return _csv(db, request, user, "repeat_violations",
                    ["Employee ID", "Employee", "Module", "Violations", "Most missed item", "Last violation"],
                    [[r["employee_code"], r["full_name"], r["module"], r["violations"], r["most_missed"],
                      r["last_violation_at"]] for r in data], fid)
    return {"from": d1.isoformat(), "to": d2.isoformat(), "rows": data}


@router.get("/modules")
def modules(request: Request, db: DB, user: View, factory_id: int | None = None, module_id: int | None = None,
            date_from: date | None = None, date_to: date | None = None, fmt: Fmt = "json"):
    fid, factory, d1, d2, rows = _ctx(db, user, factory_id, date_from, date_to, module_id)
    mods = db.scalars(select(Module).where(Module.factory_id == fid).order_by(Module.id)).all()
    if module_id:
        mods = [m for m in mods if m.id == module_id]
    groups = an.by_key(rows, lambda r: r.module_id)
    data = [{"module_id": m.id, "name": m.name, "color": m.color, "entry_points": len(m.entry_points),
             "entries": groups[m.id][0], "passed": groups[m.id][1], "failed": groups[m.id][0] - groups[m.id][1],
             "compliance": an.pct(groups[m.id][1], groups[m.id][0])} for m in mods]
    if fmt == "csv":
        return _csv(db, request, user, "module_compliance",
                    ["Module", "Entry points", "Entries", "Successful", "Failed", "Compliance %"],
                    [[r["name"], r["entry_points"], r["entries"], r["passed"], r["failed"], r["compliance"]] for r in data], fid)
    daily = {m.id: an.series([r for r in rows if r.module_id == m.id], factory.timezone, "day", fill=(d1, d2)) for m in mods}
    return {"from": d1.isoformat(), "to": d2.isoformat(), "rows": data,
            "series": [{"module_id": m.id, "name": m.name, "color": m.color, "points": daily[m.id]} for m in mods]}


@router.get("/ppe")
def ppe(request: Request, db: DB, user: View, factory_id: int | None = None, module_id: int | None = None,
        date_from: date | None = None, date_to: date | None = None, fmt: Fmt = "json"):
    fid, factory, d1, d2, rows = _ctx(db, user, factory_id, date_from, date_to, module_id)
    required = defaultdict(set)
    for mid, item in db.execute(select(PPERequirement.module_id, PPERequirement.item).join(Module).where(
            Module.factory_id == fid, PPERequirement.required.is_(True))).all():
        required[item].add(mid)
    data = []
    for item in PPE_ITEMS:
        checks = sum(1 for r in rows if r.module_id in required[item])
        miss = sum(1 for r in rows if not r.passed and item in (r.missing_items or []))
        data.append({"item": item, "label": PPE_LABELS[item], "checks": checks, "missing": miss,
                     "miss_rate": round(miss / checks * 100, 2) if checks else None})
    if fmt == "csv":
        return _csv(db, request, user, "ppe_violations", ["PPE item", "Entries where required", "Missing", "Miss rate %"],
                    [[r["label"], r["checks"], r["missing"], r["miss_rate"]] for r in data], fid)
    return {"from": d1.isoformat(), "to": d2.isoformat(), "rows": data}


@router.get("/entries")
def entries(request: Request, db: DB, user: View, factory_id: int | None = None, module_id: int | None = None,
            date_from: date | None = None, date_to: date | None = None,
            result: Literal["granted", "denied"] | None = None, fmt: Fmt = "json",
            page_no: Annotated[int, Query(alias="page", ge=1)] = 1, page_size: Annotated[int, Query(ge=1, le=100)] = 15):
    fid = resolve_factory_id(db, user, factory_id)
    factory = db.get(Factory, fid)
    d1, d2, _, _ = an.date_range(factory, date_from, date_to)
    stmt = entries_query(db, user, fid, module_id=module_id, result=result, date_from=d1, date_to=d2)
    if fmt == "csv":
        rows = db.scalars(stmt.order_by(EntryLog.occurred_at.desc()).limit(50_000)).all()
        return _csv(db, request, user, "entry_history",
                    ["Entry", "Date & time", "Employee ID", "Employee", "Module", "Entry point", "Result", "Missing PPE", "Shift", "Data source"],
                    [[e.id, to_zone(e.occurred_at, factory.timezone).strftime("%Y-%m-%d %H:%M:%S"),
                      e.employee.employee_code if e.employee else "", e.employee.full_name if e.employee else "Unidentified",
                      e.module.name, e.entry_point.name if e.entry_point else "", "PASS" if e.passed else "FAIL",
                      "; ".join(PPE_LABELS.get(i, i) for i in e.missing_items), e.shift or "", e.source] for e in rows], fid)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(EntryLog.occurred_at.desc()).offset((page_no - 1) * page_size).limit(page_size)).all()
    return {**page([entry_out(e) for e in rows], total, page_no, page_size), "from": d1.isoformat(), "to": d2.isoformat()}


@router.get("/audit")
def audit_log(request: Request, db: DB, user: Annotated[User, Depends(require("audit.view"))],
              factory_id: int | None = None, date_from: date | None = None, date_to: date | None = None,
              q: str = Query("", max_length=80), fmt: Fmt = "json",
              page_no: Annotated[int, Query(alias="page", ge=1)] = 1, page_size: Annotated[int, Query(ge=1, le=100)] = 15):
    fid = resolve_factory_id(db, user, factory_id)
    factory = db.get(Factory, fid)
    d1, d2, start, end = an.date_range(factory, date_from, date_to)
    stmt = select(AuditLog).where(AuditLog.created_at >= start, AuditLog.created_at < end)
    # Factory-restricted users see only their factory's entries; unrestricted users also see global ones.
    stmt = stmt.where(AuditLog.factory_id == fid) if user.factory_id is not None else \
        stmt.where((AuditLog.factory_id == fid) | (AuditLog.factory_id.is_(None)))
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(func.lower(AuditLog.action).like(like) | func.lower(AuditLog.detail).like(like)
                          | func.lower(AuditLog.user_email).like(like))
    def row(a):
        return {"id": a.id, "created_at": iso(a.created_at), "user": a.user_email, "action": a.action,
                "detail": a.detail, "ip": a.ip}
    if fmt == "csv":
        rows = db.scalars(stmt.order_by(AuditLog.created_at.desc()).limit(50_000)).all()
        return _csv(db, request, user, "audit_log", ["Date & time (UTC)", "User", "Action", "Detail", "IP address"],
                    [[a.created_at.strftime("%Y-%m-%d %H:%M:%S"), a.user_email, a.action, a.detail, a.ip] for a in rows], fid)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(AuditLog.created_at.desc()).offset((page_no - 1) * page_size).limit(page_size)).all()
    return {**page([row(a) for a in rows], total, page_no, page_size), "from": d1.isoformat(), "to": d2.isoformat()}
