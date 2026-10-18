"""Clinic-local time helpers. Tests can freeze "now" with set_now()."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import settings

_frozen: datetime | None = None


def set_now(value: datetime | None) -> None:
    """Freeze (or unfreeze with None) the clock. Naive local time."""
    global _frozen
    _frozen = value


def advance(**kwargs) -> None:
    global _frozen
    _frozen = now() + timedelta(**kwargs)


def now() -> datetime:
    """Naive datetime in clinic-local time."""
    if _frozen is not None:
        return _frozen
    return datetime.now(ZoneInfo(settings.clinic_tz)).replace(tzinfo=None, microsecond=0)


def today() -> date:
    return now().date()


def parse_hhmm(value: str) -> time:
    h, m = value.strip().split(":")
    return time(int(h), int(m))


def window(value: str) -> tuple[time, time]:
    start, end = value.split("-")
    return parse_hhmm(start), parse_hhmm(end)


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None
