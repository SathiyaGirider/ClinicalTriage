"""Booking API (patients only; every object is checked against the caller)."""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth.deps import require_patient
from app.booking import service
from app.common import timeutil
from app.db import get_session
from app.models import Appointment, ClinicSession, User
from app.queue import service as queue

router = APIRouter(prefix="/booking", tags=["Booking"])


class HoldRequest(BaseModel):
    session_id: int


class FinalizeRequest(BaseModel):
    intake_id: int
    hold_id: Optional[int] = None  # routine path: the held session
    session_id: Optional[int] = None  # same-day path: a session running today
    mode: Literal["hold", "same_day"] = "hold"


class RescheduleRequest(BaseModel):
    session_id: int


class ArrivedRequest(BaseModel):
    change: Literal["none", "better", "worse", "new_symptom"]
    text: Optional[str] = Field(default=None, max_length=2000)


class WalkInIntentRequest(BaseModel):
    intake_id: int
    hospital_id: int
    doctor_id: Optional[int] = None


@router.post("/hold", status_code=201)
def hold(req: HoldRequest, user: User = Depends(require_patient), db: Session = Depends(get_session)):
    h = service.create_hold(db, user, req.session_id)
    return {"hold_id": h.id, "session_id": h.session_id, "held_until": h.held_until.isoformat()}


@router.post("/{hold_id}/release")
def release(hold_id: int, user: User = Depends(require_patient), db: Session = Depends(get_session)):
    service.release_hold(db, service.get_own_hold(db, user, hold_id))
    return {"released": True}


@router.post("/finalize")
def finalize(req: FinalizeRequest, user: User = Depends(require_patient), db: Session = Depends(get_session)):
    """Issues the token. The outcome comes from the server-side triage decision for intake_id."""
    if req.mode == "same_day":
        if req.session_id is None:
            raise HTTPException(422, "session_id is required for same_day")
        return service.finalize_same_day(db, user, req.session_id, req.intake_id)
    if req.hold_id is None:
        raise HTTPException(422, "hold_id is required")
    return service.finalize_hold(db, user, req.hold_id, req.intake_id)


@router.get("/mine")
def mine(user: User = Depends(require_patient), db: Session = Depends(get_session)):
    rows = db.exec(select(Appointment).where(Appointment.patient_id == user.id).order_by(Appointment.date.desc(), Appointment.id.desc())).all()
    today = timeutil.today()
    views = [service.appointment_view(db, a) for a in rows]
    upcoming = [v for v, a in zip(views, rows) if a.date >= today and a.status not in ("completed", "cancelled", "no_show")]
    past = [v for v, a in zip(views, rows) if v not in upcoming]
    return {"upcoming": list(reversed(upcoming)), "past": past}


@router.get("/today-sessions")
def today_sessions(doctor_id: Optional[int] = None, specialty: Optional[str] = Query(default=None, max_length=40),
                   hospital_id: Optional[int] = None, _: User = Depends(require_patient), db: Session = Depends(get_session)):
    return service.today_sessions(db, doctor_id=doctor_id, specialty=specialty, hospital_id=hospital_id)


@router.post("/walk-in-intent", status_code=201)
def walk_in_intent(req: WalkInIntentRequest, user: User = Depends(require_patient), db: Session = Depends(get_session)):
    return service.walk_in_intent(db, user, req.intake_id, req.hospital_id, req.doctor_id)


@router.get("/{appointment_id}/status")
def status(appointment_id: int, user: User = Depends(require_patient), db: Session = Depends(get_session)):
    return service.status(db, service.get_own_appointment(db, user, appointment_id))


@router.post("/{appointment_id}/cancel")
def cancel(appointment_id: int, user: User = Depends(require_patient), db: Session = Depends(get_session)):
    service.cancel(db, user, service.get_own_appointment(db, user, appointment_id))
    return {"cancelled": True}


@router.post("/{appointment_id}/reschedule")
def reschedule(appointment_id: int, req: RescheduleRequest, user: User = Depends(require_patient), db: Session = Depends(get_session)):
    return service.reschedule(db, user, service.get_own_appointment(db, user, appointment_id), req.session_id)


@router.post("/{appointment_id}/arrived")
def arrived(appointment_id: int, req: ArrivedRequest, user: User = Depends(require_patient), db: Session = Depends(get_session)):
    return queue.patient_arrived(db, service.get_own_appointment(db, user, appointment_id), req.change, req.text, user)


@router.get("/{appointment_id}/ics")
def ics(appointment_id: int, user: User = Depends(require_patient), db: Session = Depends(get_session)):
    a = service.get_own_appointment(db, user, appointment_id)
    v = service.appointment_view(db, a)
    s = db.get(ClinicSession, a.session_id) if a.session_id else None
    start = (s.window_start if s else "09:00").replace(":", "")
    end = (s.window_end if s else "17:00").replace(":", "")
    d = a.date.strftime("%Y%m%d")
    body = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//LifeLine demo//EN", "BEGIN:VEVENT",
        f"UID:lifeline-{a.id}@demo", f"DTSTAMP:{timeutil.now().strftime('%Y%m%dT%H%M%S')}",
        f"DTSTART:{d}T{start}00", f"DTEND:{d}T{end}00",
        f"SUMMARY:Doctor visit, token {v['token_label'] or '-'} (demo)",
        f"LOCATION:{v['hospital']['name']}, {v['hospital']['address']}".replace(",", "\\,"),
        "DESCRIPTION:Times are approximate. Please arrive about 20 minutes before your estimated time.",
        "END:VEVENT", "END:VCALENDAR", ""])
    return Response(body, media_type="text/calendar", headers={"Content-Disposition": f"attachment; filename=lifeline-{a.id}.ics"})
