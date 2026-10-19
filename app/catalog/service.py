"""Hospitals, doctors, sessions, distance ranking, department mapping."""

from __future__ import annotations

import math
from datetime import date, datetime

from sqlmodel import Session, select

from app.common import timeutil
from app.models import Appointment, BookingHold, ClinicSession, Doctor, Hospital


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 1)


def active_units(db: Session, session_id: int, now: datetime | None = None) -> int:
    now = now or timeutil.now()
    holds = db.exec(select(BookingHold).where(
        BookingHold.session_id == session_id, BookingHold.released == False,  # noqa: E712
        BookingHold.finalized == False, BookingHold.held_until > now)).all()  # noqa: E712
    appts = db.exec(select(Appointment).where(Appointment.session_id == session_id, Appointment.status != "cancelled")).all()
    return len(holds) + len(appts)


def tokens_left(db: Session, s: ClinicSession, urgent: bool = False, now: datetime | None = None) -> int:
    cap = s.max_tokens if urgent else max(0, s.max_tokens - s.reserved_urgent)
    return max(0, cap - active_units(db, s.id, now))


def session_end(s: ClinicSession) -> datetime:
    return datetime.combine(s.date, timeutil.parse_hhmm(s.window_end))


def session_start(s: ClinicSession) -> datetime:
    return datetime.combine(s.date, timeutil.parse_hhmm(s.window_start))


def is_bookable(s: ClinicSession, now: datetime | None = None) -> bool:
    now = now or timeutil.now()
    return s.status == "open" and session_end(s) > now


def session_view(db: Session, s: ClinicSession, urgent: bool = False) -> dict:
    return {
        "id": s.id, "doctor_id": s.doctor_id, "date": s.date.isoformat(), "label": s.label,
        "window_start": s.window_start, "window_end": s.window_end, "max_tokens": s.max_tokens,
        "tokens_left": tokens_left(db, s, urgent) if is_bookable(s) else 0,
        "urgent_tokens_left": tokens_left(db, s, True) if is_bookable(s) else 0,
        "status": s.status, "bookable": is_bookable(s),
    }


def next_session(db: Session, doctor_id: int) -> dict | None:
    rows = db.exec(select(ClinicSession).where(ClinicSession.doctor_id == doctor_id, ClinicSession.date >= timeutil.today())
                   .order_by(ClinicSession.date, ClinicSession.window_start)).all()
    for s in rows:
        if is_bookable(s) and tokens_left(db, s) > 0:
            return session_view(db, s)
    return None


def hospital_view(h: Hospital, lat: float | None = None, lon: float | None = None) -> dict:
    d = h.model_dump()
    d["distance_km"] = haversine_km(lat, lon, h.lat, h.lon) if lat is not None and lon is not None else None
    return d


def doctor_view(db: Session, doc: Doctor, lat: float | None = None, lon: float | None = None, with_next: bool = True) -> dict:
    h = db.get(Hospital, doc.hospital_id)
    return {
        "id": doc.id, "name": doc.name, "specialty": doc.specialty, "hospital_id": doc.hospital_id,
        "hospital_name": h.name if h else "", "area": doc.area, "consult_minutes": doc.consult_minutes, "bio": doc.bio,
        "distance_km": haversine_km(lat, lon, doc.lat, doc.lon) if lat is not None and lon is not None else None,
        "next_session": next_session(db, doc.id) if with_next else None,
    }


def sort_by_distance_or_area(items: list[dict], area: str | None) -> list[dict]:
    if any(i.get("distance_km") is not None for i in items):
        return sorted(items, key=lambda i: (i["distance_km"] is None, i["distance_km"] or 0, i.get("name", "")))
    if area:
        a = area.strip().lower()
        return sorted(items, key=lambda i: (i.get("area", "").lower() != a, i.get("area", ""), i.get("name", "")))
    return sorted(items, key=lambda i: (i.get("area", ""), i.get("name", "")))


def sessions_for(db: Session, doctor_id: int, day: date | None) -> list[ClinicSession]:
    q = select(ClinicSession).where(ClinicSession.doctor_id == doctor_id)
    if day:
        q = q.where(ClinicSession.date == day)
    else:
        q = q.where(ClinicSession.date >= timeutil.today())
    return list(db.exec(q.order_by(ClinicSession.date, ClinicSession.window_start)).all())
