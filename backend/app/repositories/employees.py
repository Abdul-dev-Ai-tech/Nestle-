"""Query helpers for employees (search, filter, sort, paginate, statistics)."""
from sqlalchemy import Integer, case, func, or_, select
from sqlalchemy.orm import Session

from app.models import Employee, EntryLog

SORTS = {"name": Employee.full_name, "code": Employee.employee_code, "designation": Employee.designation,
         "shift": Employee.shift, "status": Employee.status, "created": Employee.created_at}


def search(db: Session, factory_id: int, *, q: str = "", module_id: int | None = None,
           department_id: int | None = None, status: str | None = None, shift: str | None = None,
           sort: str = "name", order: str = "asc", page: int = 1, size: int = 20) -> tuple[list[Employee], int]:
    stmt = select(Employee).where(Employee.factory_id == factory_id)
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(Employee.full_name).like(like), func.lower(Employee.employee_code).like(like),
                              func.lower(Employee.designation).like(like)))
    if module_id:
        stmt = stmt.where(Employee.module_id == module_id)
    if department_id:
        stmt = stmt.where(Employee.department_id == department_id)
    if status in ("active", "inactive"):
        stmt = stmt.where(Employee.status == status)
    if shift:
        stmt = stmt.where(Employee.shift == shift)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    col = SORTS.get(sort, Employee.full_name)
    stmt = stmt.order_by(col.desc() if order == "desc" else col.asc(), Employee.id)
    rows = db.scalars(stmt.offset((page - 1) * size).limit(size)).all()
    return list(rows), total


def stats_for(db: Session, employee_ids: list[int], since=None) -> dict[int, dict]:
    """Entry count / violation count / last entry per employee, in one grouped query."""
    if not employee_ids:
        return {}
    stmt = select(EntryLog.employee_id, func.count(EntryLog.id),
                  func.sum(case((EntryLog.passed.is_(False), 1), else_=0)).cast(Integer),
                  func.max(EntryLog.occurred_at)).where(EntryLog.employee_id.in_(employee_ids))
    if since is not None:
        stmt = stmt.where(EntryLog.occurred_at >= since)
    out = {}
    for emp_id, n, fails, last in db.execute(stmt.group_by(EntryLog.employee_id)).all():
        fails = int(fails or 0)
        out[emp_id] = {"entries": n, "violations": fails, "compliance": round((n - fails) / n * 100, 1) if n else None,
                       "last_entry_at": last.isoformat() if hasattr(last, "isoformat") else last}
    return out
