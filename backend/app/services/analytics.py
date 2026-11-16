"""Dashboard and report aggregation computed from entry logs in the database.

Rows are fetched as light tuples and grouped in Python in the factory's time zone, which keeps
the code identical on PostgreSQL and SQLite. For very large sites, replace with daily rollups.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import local_day_bounds, to_zone, utcnow
from app.models import PPE_ITEMS, PPE_LABELS, EntryLog, Factory

MAX_RANGE_DAYS = 366


def pct(ok: int, n: int) -> float | None:
    return round(ok / n * 100, 1) if n else None


def date_range(factory: Factory, date_from: date | None, date_to: date | None, default_days: int = 7):
    today = to_zone(utcnow(), factory.timezone).date()
    d2 = min(date_to or today, today)
    d1 = date_from or (d2 - timedelta(days=default_days - 1))
    if d1 > d2:
        d1 = d2
    if (d2 - d1).days > MAX_RANGE_DAYS:
        d1 = d2 - timedelta(days=MAX_RANGE_DAYS)
    return d1, d2, local_day_bounds(d1, factory.timezone)[0], local_day_bounds(d2, factory.timezone)[1]


def fetch(db: Session, factory_id: int, start: datetime, end: datetime, module_id: int | None = None) -> list:
    stmt = select(EntryLog.occurred_at, EntryLog.passed, EntryLog.module_id, EntryLog.employee_id, EntryLog.shift,
                  EntryLog.missing_items, EntryLog.source).where(
        EntryLog.factory_id == factory_id, EntryLog.occurred_at >= start, EntryLog.occurred_at < end)
    if module_id:
        stmt = stmt.where(EntryLog.module_id == module_id)
    return db.execute(stmt).all()


def _bucket_key(d: date, granularity: str) -> date:
    if granularity == "week":
        return d - timedelta(days=d.weekday())
    if granularity == "month":
        return d.replace(day=1)
    return d


def _bucket_label(d: date, granularity: str) -> str:
    if granularity == "week":
        return "Week of " + d.strftime("%d %b")
    if granularity == "month":
        return d.strftime("%B %Y")
    return d.strftime("%d %b")


def series(rows: list, tz: str, granularity: str = "day", fill: tuple[date, date] | None = None) -> list[dict]:
    buckets: dict[date, list[int]] = defaultdict(lambda: [0, 0])
    if fill and granularity == "day":
        d = fill[0]
        while d <= fill[1]:
            buckets[d]
            d += timedelta(days=1)
    for r in rows:
        b = buckets[_bucket_key(to_zone(r.occurred_at, tz).date(), granularity)]
        b[0] += 1
        b[1] += 1 if r.passed else 0
    return [{"date": k.isoformat(), "label": _bucket_label(k, granularity), "entries": n, "passed": ok,
             "failed": n - ok, "compliance": pct(ok, n)} for k, (n, ok) in sorted(buckets.items())]


def totals(rows: list) -> dict:
    n = len(rows)
    ok = sum(1 for r in rows if r.passed)
    return {"entries": n, "passed": ok, "failed": n - ok, "compliance": pct(ok, n)}


def missing_counts(rows: list) -> list[dict]:
    c = Counter(i for r in rows if not r.passed for i in (r.missing_items or []))
    return [{"item": i, "label": PPE_LABELS[i], "missing": c.get(i, 0)} for i in PPE_ITEMS]


def by_key(rows: list, key) -> dict:
    out: dict = defaultdict(lambda: [0, 0])
    for r in rows:
        b = out[key(r)]
        b[0] += 1
        b[1] += 1 if r.passed else 0
    return out


def sources(rows: list) -> dict:
    return dict(Counter(r.source for r in rows))
