from datetime import timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from app.api.deps import DB, client_ip, ensure_factory_access, require, resolve_factory_id
from app.core.time import utcnow
from app.models import Department, Employee, EntryLog, Module, User, Violation
from app.repositories import employees as repo
from app.schemas.common import employee_out, entry_out, page, violation_out
from app.schemas.inputs import EmployeeIn, EmployeeUpdate
from app.services import storage
from app.services.audit import audit

router = APIRouter(prefix="/employees", tags=["employees"])
View = Annotated[User, Depends(require("employees.view"))]
Manage = Annotated[User, Depends(require("employees.manage"))]


def _get(db, employee_id: int, user: User) -> Employee:
    e = db.get(Employee, employee_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Employee not found")
    ensure_factory_access(user, e.factory_id)
    return e


def _check_refs(db, factory_id: int, module_id: int | None, department_id: int | None) -> None:
    if module_id is not None:
        m = db.get(Module, module_id)
        if m is None or m.factory_id != factory_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Module does not belong to this factory")
    if department_id is not None:
        d = db.get(Department, department_id)
        if d is None or d.factory_id != factory_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Department does not belong to this factory")


@router.get("")
def list_employees(db: DB, user: View, factory_id: int | None = None, q: str = Query("", max_length=80),
                   module_id: int | None = None, department_id: int | None = None,
                   status_: Annotated[Literal["active", "inactive"] | None, Query(alias="status")] = None,
                   shift: str | None = Query(None, max_length=4),
                   sort: Literal["name", "code", "designation", "shift", "status", "created"] = "name",
                   order: Literal["asc", "desc"] = "asc", page_no: Annotated[int, Query(alias="page", ge=1)] = 1,
                   page_size: Annotated[int, Query(ge=1, le=100)] = 20):
    fid = resolve_factory_id(db, user, factory_id)
    rows, total = repo.search(db, fid, q=q, module_id=module_id, department_id=department_id, status=status_,
                              shift=shift, sort=sort, order=order, page=page_no, size=page_size)
    stats = repo.stats_for(db, [e.id for e in rows], since=utcnow() - timedelta(days=30))
    items = [{**employee_out(e), "stats_30d": stats.get(e.id, {"entries": 0, "violations": 0, "compliance": None,
                                                               "last_entry_at": None})} for e in rows]
    counts = dict(db.execute(select(Employee.status, func.count()).where(Employee.factory_id == fid)
                             .group_by(Employee.status)).all())
    return {**page(items, total, page_no, page_size),
            "summary": {"total": sum(counts.values()), "active": counts.get("active", 0),
                        "inactive": counts.get("inactive", 0)}}


@router.get("/lookup")
def lookup(code: Annotated[str, Query(min_length=2, max_length=20)], db: DB,
           user: Annotated[User, Depends(require("monitoring.view"))], factory_id: int | None = None):
    """Find one employee by badge/employee code (used at the entry point)."""
    fid = resolve_factory_id(db, user, factory_id)
    e = db.scalar(select(Employee).where(Employee.factory_id == fid, Employee.employee_code == code.upper().strip()))
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No employee with this code")
    return employee_out(e)


@router.post("", status_code=201)
def create_employee(body: EmployeeIn, request: Request, db: DB, user: Manage, factory_id: int | None = None):
    fid = resolve_factory_id(db, user, factory_id)
    if db.scalar(select(Employee.id).where(Employee.factory_id == fid, Employee.employee_code == body.employee_code)):
        raise HTTPException(status.HTTP_409_CONFLICT, "This employee ID already exists")
    _check_refs(db, fid, body.module_id, body.department_id)
    e = Employee(factory_id=fid, **body.model_dump())
    db.add(e)
    audit(db, user, "employee.create", f"Added {e.full_name} ({e.employee_code})", ip=client_ip(request), factory_id=fid)
    db.commit()
    db.refresh(e)
    return employee_out(e)


@router.get("/{employee_id}")
def get_employee(employee_id: int, db: DB, user: View):
    e = _get(db, employee_id, user)
    s30 = repo.stats_for(db, [e.id], since=utcnow() - timedelta(days=30)).get(e.id)
    all_time = repo.stats_for(db, [e.id]).get(e.id)
    empty = {"entries": 0, "violations": 0, "compliance": None, "last_entry_at": None}
    return {**employee_out(e), "stats_30d": s30 or empty, "stats_all": all_time or empty}


@router.patch("/{employee_id}")
def update_employee(employee_id: int, body: EmployeeUpdate, request: Request, db: DB, user: Manage):
    e = _get(db, employee_id, user)
    data = body.model_dump(exclude_unset=True)
    _check_refs(db, e.factory_id, data.get("module_id"), data.get("department_id"))
    for k, v in data.items():
        setattr(e, k, v)
    audit(db, user, "employee.update", f"{e.full_name} ({e.employee_code}): {', '.join(data.keys())}",
          ip=client_ip(request), factory_id=e.factory_id)
    db.commit()
    db.refresh(e)
    return employee_out(e)


@router.delete("/{employee_id}")
def delete_employee(employee_id: int, request: Request, db: DB, user: Manage):
    """Hard-delete only when there is no history; otherwise the record is deactivated (audit trail kept)."""
    e = _get(db, employee_id, user)
    has_history = db.scalar(select(func.count(EntryLog.id)).where(EntryLog.employee_id == e.id))
    if has_history:
        e.status = "inactive"
        result = "deactivated"
    else:
        storage.delete(e.photo_path)
        db.delete(e)
        result = "deleted"
    audit(db, user, "employee.delete", f"{e.full_name} ({e.employee_code}): {result}", ip=client_ip(request),
          factory_id=e.factory_id)
    db.commit()
    return {"ok": True, "result": result}


@router.post("/{employee_id}/photo")
async def upload_photo(employee_id: int, request: Request, db: DB, user: Manage, file: UploadFile = File(...)):
    e = _get(db, employee_id, user)
    data = await storage.read_upload(file)
    new_path = storage.save_image(data, "employees", max_side=600)
    storage.delete(e.photo_path)
    e.photo_path = new_path
    audit(db, user, "employee.photo", f"Updated photo for {e.employee_code}", ip=client_ip(request),
          factory_id=e.factory_id)
    db.commit()
    return {"ok": True}


@router.get("/{employee_id}/photo")
def get_photo(employee_id: int, db: DB, user: Annotated[User, Depends(require("dashboard.view"))]):
    e = _get(db, employee_id, user)
    path = storage.resolve(e.photo_path)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No photo")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})


@router.get("/{employee_id}/entries")
def employee_entries(employee_id: int, db: DB, user: View, page_no: Annotated[int, Query(alias="page", ge=1)] = 1,
                     page_size: Annotated[int, Query(ge=1, le=100)] = 12):
    e = _get(db, employee_id, user)
    base = select(EntryLog).where(EntryLog.employee_id == e.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(base.order_by(EntryLog.occurred_at.desc()).offset((page_no - 1) * page_size).limit(page_size)).all()
    return page([entry_out(r) for r in rows], total, page_no, page_size)


@router.get("/{employee_id}/violations")
def employee_violations(employee_id: int, db: DB, user: View):
    e = _get(db, employee_id, user)
    rows = db.scalars(select(Violation).where(Violation.employee_id == e.id).order_by(Violation.created_at.desc())
                      .limit(50)).all()
    return [violation_out(v) for v in rows]
