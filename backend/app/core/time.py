from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_zone(dt: datetime, tz: str) -> datetime:
    try:
        return dt.astimezone(ZoneInfo(tz))
    except Exception:  # unknown zone name -> UTC
        return dt.astimezone(timezone.utc)


def local_day_bounds(day, tz: str) -> tuple[datetime, datetime]:
    """UTC start/end of a calendar day in the factory's time zone."""
    try:
        zone = ZoneInfo(tz)
    except Exception:
        zone = timezone.utc
    start = datetime.combine(day, time.min, tzinfo=zone)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def shift_for(dt_local: datetime, shifts: list[dict]) -> str | None:
    """Return the shift code whose [start, end) window contains the local time."""
    t = dt_local.time()
    for s in shifts or []:
        try:
            a, b = time.fromisoformat(s["start"]), time.fromisoformat(s["end"])
        except Exception:
            continue
        if (a <= t < b) if a < b else (t >= a or t < b):
            return s.get("code")
    return None
