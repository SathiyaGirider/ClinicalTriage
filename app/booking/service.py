"""
Session capacity holds, token issuing, finalise, same-day, walk-in intent,
cancel, reschedule, live status.

Capacity is transactional: every check-and-write runs under one process-wide
lock and a single DB transaction (one uvicorn worker; see ASSUMPTIONS #15).
Token numbers come from ClinicSession.next_token_seq, which only increases,
so a cancelled or released token is never reused and nothing is renumbered.
"""

from __future__ import annotations

import threading
from datetime import timedelta

from fastapi import HTTPException
from sqlmodel import Session, select

from app.audit import log_action
from app.catalog.service import doctor_view, is_bookable, session_view, tokens_left
from app.common import timeutil
from app.common.ids import token_label
from app.common.schemas import TriageDecision
from app.config import settings
from app.models import Appointment, BookingHold, ClinicSession, Doctor, Hospital, IntakeRecord, QueueEntryRow, User
from app.pipeline import store
from app.pipeline.advice import OUTCOME_CONCERNING, OUTCOME_EMERGENCY, OUTCOME_ROUTINE, outcome_for
from app.queue import service as queue

capacity_lock = threading.RLock()


def _own_intake(db: Session, patient: User, intake_id: int) -> tuple[IntakeRecord, TriageDecision]:
    row = db.get(IntakeRecord, intake_id)
    if row is None or row.patient_id != patient.id:
        raise HTTPException(404, "Intake not found")
    d = store.latest_decision(db, intake_id)
    if d is None:
        raise HTTPException(409, "This intake has not been assessed yet")
    return row, d


def create_hold(db: Session, patient: User, session_id: int) -> BookingHold:
    with capacity_lock:
        s = db.get(ClinicSession, session_id)
        if s is None:
            raise HTTPException(404, "Session not found")
        if not is_bookable(s):
            raise HTTPException(409, "This session is closed or over")
        now = timeutil.now()
        # One active hold per patient: starting a new flow releases the old hold.
        for h in db.exec(select(BookingHold).where(BookingHold.patient_id == patient.id, BookingHold.released == False,  # noqa: E712
                                                   BookingHold.finalized == False)).all():  # noqa: E712
            h.released = True
            db.add(h)
        db.flush()
        if tokens_left(db, s, urgent=False, now=now) <= 0:
            db.rollback()
            raise HTTPException(409, "No tokens left in this session")
        hold = BookingHold(session_id=s.id, patient_id=patient.id, held_until=now + timedelta(minutes=settings.hold_minutes))
        db.add(hold)
        db.commit()
        db.refresh(hold)
        return hold


def get_own_hold(db: Session, patient: User, hold_id: int) -> BookingHold:
    h = db.get(BookingHold, hold_id)
    if h is None or h.patient_id != patient.id:
        raise HTTPException(404, "Hold not found")
    return h


def release_hold(db: Session, hold: BookingHold) -> None:
    with capacity_lock:
        if not hold.finalized:
            hold.released = True
            db.add(hold)
            db.commit()


def _issue(db: Session, patient: User, s: ClinicSession, intake_id: int, appt_type: str, decision: TriageDecision) -> Appointment:
    """Caller holds capacity_lock and has checked capacity."""
    doc = db.get(Doctor, s.doctor_id)
    number = s.next_token_seq
    s.next_token_seq = number + 1
    db.add(s)
    appt = Appointment(patient_id=patient.id, doctor_id=doc.id, hospital_id=doc.hospital_id, session_id=s.id, date=s.date,
                       token_number=number, token_label=token_label(s.label, number), type=appt_type, status="booked",
                       intake_id=intake_id)
    db.add(appt)
    db.flush()
    rec = db.get(IntakeRecord, intake_id)
    rec.appointment_id = appt.id
    db.add(rec)
    flagged = decision.flag_for_nurse or decision.priority != "routine"
    queue.create_entry(db, appt, s, flagged, "Flagged at booking (AI-assisted)" if flagged else None)
    queue.refresh_estimate(db, appt)
    return appt


def finalize_hold(db: Session, patient: User, hold_id: int, intake_id: int) -> dict:
    with capacity_lock:
        hold = get_own_hold(db, patient, hold_id)
        if hold.finalized:
            raise HTTPException(409, "This hold was already used")
        if hold.released:
            raise HTTPException(410, "This hold was released. Please choose a session again.")
        now = timeutil.now()
        if hold.held_until <= now:
            hold.released = True
            db.add(hold)
            db.commit()
            raise HTTPException(410, "Your 10-minute hold expired. Please choose a session again.")
        _, decision = _own_intake(db, patient, intake_id)
        outcome = outcome_for(decision)
        s = db.get(ClinicSession, hold.session_id)
        if outcome == OUTCOME_EMERGENCY:
            hold.released = True
            db.add(hold)
            log_action(db, patient, "emergency_advice", patient.id, None, None, None, commit=False)
            db.commit()
            return {"outcome": outcome, "appointment": None}
        if outcome == OUTCOME_CONCERNING:
            hold.released = True
            db.add(hold)
            db.commit()
            return {"outcome": outcome, "appointment": None,
                    "today": today_sessions(db, doctor_id=s.doctor_id)}
        hold.finalized = True  # the held unit becomes the appointment
        db.add(hold)
        appt = _issue(db, patient, s, intake_id, "booked", decision)
        db.commit()
        db.refresh(appt)
        return {"outcome": OUTCOME_ROUTINE, "appointment": appointment_view(db, appt)}


def finalize_same_day(db: Session, patient: User, session_id: int, intake_id: int) -> dict:
    with capacity_lock:
        _, decision = _own_intake(db, patient, intake_id)
        if outcome_for(decision) != OUTCOME_CONCERNING:
            raise HTTPException(409, "Same-day urgent tokens are only for patients a nurse should see today")
        if db.exec(select(Appointment).where(Appointment.intake_id == intake_id, Appointment.status != "cancelled")).first():
            raise HTTPException(409, "This intake already has a booking")
        s = db.get(ClinicSession, session_id)
        if s is None or s.date != timeutil.today() or not is_bookable(s):
            raise HTTPException(409, "That session is not running today")
        if tokens_left(db, s, urgent=True) <= 0:
            raise HTTPException(409, "No tokens left in this session")
        appt = _issue(db, patient, s, intake_id, "same_day", decision)
        db.commit()
        db.refresh(appt)
        return {"outcome": OUTCOME_CONCERNING, "appointment": appointment_view(db, appt)}


def walk_in_intent(db: Session, patient: User, intake_id: int, hospital_id: int, doctor_id: int | None) -> dict:
    with capacity_lock:
        _, decision = _own_intake(db, patient, intake_id)
        if outcome_for(decision) != OUTCOME_CONCERNING:
            raise HTTPException(409, "Walk-in intent is only for the 'visit today' outcome")
        h = db.get(Hospital, hospital_id)
        if h is None:
            raise HTTPException(404, "Hospital not found")
        doc = db.get(Doctor, doctor_id) if doctor_id else None
        if doc is None or doc.hospital_id != hospital_id:
            dept = decision.suggested_department or "General Medicine"
            doc = db.exec(select(Doctor).where(Doctor.hospital_id == hospital_id, Doctor.specialty == dept)).first() or \
                db.exec(select(Doctor).where(Doctor.hospital_id == hospital_id, Doctor.specialty == "General Medicine")).first() or \
                db.exec(select(Doctor).where(Doctor.hospital_id == hospital_id)).first()
        if doc is None:
            raise HTTPException(409, "No doctor available at this hospital")
        appt = Appointment(patient_id=patient.id, doctor_id=doc.id, hospital_id=hospital_id, session_id=None, date=timeutil.today(),
                           type="walk_in", status="expected_today", intake_id=intake_id)
        db.add(appt)
        db.flush()
        rec = db.get(IntakeRecord, intake_id)
        rec.appointment_id = appt.id
        db.add(rec)
        queue.create_entry(db, appt, None, True, "Expected today (flagged at booking)")
        log_action(db, patient, "walk_in_intent", patient.id, None, str(appt.id), None, hospital_id=hospital_id, commit=False)
        db.commit()
        db.refresh(appt)
        return {"outcome": OUTCOME_CONCERNING, "appointment": appointment_view(db, appt)}


def today_sessions(db: Session, doctor_id: int | None = None, specialty: str | None = None, hospital_id: int | None = None) -> dict:
    """Sessions still running today with tokens left (reserved urgent tokens count: concerning patients only)."""
    today = timeutil.today()
    def running(doc_ids: list[int]) -> list[dict]:
        out = []
        for s in db.exec(select(ClinicSession).where(ClinicSession.date == today, ClinicSession.doctor_id.in_(doc_ids))
                         .order_by(ClinicSession.window_start)).all():
            if is_bookable(s) and tokens_left(db, s, urgent=True) > 0:
                v = session_view(db, s, urgent=True)
                v["doctor"] = doctor_view(db, db.get(Doctor, s.doctor_id), with_next=False)
                out.append(v)
        return out

    doc = db.get(Doctor, doctor_id) if doctor_id else None
    hospital_id = hospital_id or (doc.hospital_id if doc else None)
    specialty = specialty or (doc.specialty if doc else None)
    sessions = running([doc.id]) if doc else []
    scope = "same_doctor"
    if not sessions and hospital_id:
        q = select(Doctor).where(Doctor.hospital_id == hospital_id)
        if specialty:
            q = q.where(Doctor.specialty == specialty)
        others = [d.id for d in db.exec(q).all() if not doc or d.id != doc.id]
        sessions = running(others) if others else []
        scope = "same_specialty_same_hospital"
    h = db.get(Hospital, hospital_id) if hospital_id else None
    return {
        "sessions": sessions,
        "scope": scope if sessions else "none",
        "hospital": h.model_dump() if h else None,
        "walk_in_fallback": None if sessions else ({"walk_in_window_text": h.walk_in_window_text, "opd_hours": h.opd_hours} if h else None),
    }


def get_own_appointment(db: Session, patient: User, appt_id: int) -> Appointment:
    a = db.get(Appointment, appt_id)
    if a is None or a.patient_id != patient.id:
        raise HTTPException(404, "Appointment not found")
    return a


def cancel(db: Session, patient: User, appt: Appointment) -> None:
    with capacity_lock:
        if appt.status in ("completed", "cancelled", "with_doctor"):
            raise HTTPException(409, f"Cannot cancel an appointment that is {appt.status}")
        appt.status = "cancelled"
        db.add(appt)
        e = queue.entry_for_appointment(db, appt.id)
        if e:
            db.delete(e)
        log_action(db, patient, "cancel_appointment", patient.id, appt.token_label, "cancelled", None, hospital_id=appt.hospital_id, commit=False)
        db.commit()


def reschedule(db: Session, patient: User, appt: Appointment, session_id: int) -> dict:
    """Reuses the intake. Old token released for good; new token in the new session."""
    with capacity_lock:
        if appt.status not in ("booked", "expected_today"):
            raise HTTPException(409, "Only upcoming bookings can be rescheduled")
        s = db.get(ClinicSession, session_id)
        if s is None or not is_bookable(s):
            raise HTTPException(409, "That session is not available")
        decision = store.latest_decision(db, appt.intake_id)
        if decision is None:
            raise HTTPException(409, "No assessment on this booking")
        outcome = outcome_for(decision)
        if outcome == OUTCOME_EMERGENCY:
            raise HTTPException(409, "Please go to the Emergency department")
        urgent = outcome == OUTCOME_CONCERNING
        if urgent and s.date != timeutil.today():
            raise HTTPException(409, "Please choose a session today")
        if tokens_left(db, s, urgent=urgent) <= 0:
            raise HTTPException(409, "No tokens left in this session")
        old_label = appt.token_label
        appt.status = "cancelled"
        db.add(appt)
        e = queue.entry_for_appointment(db, appt.id)
        if e:
            db.delete(e)
        db.flush()
        new = _issue(db, patient, s, appt.intake_id, "same_day" if urgent else "booked", decision)
        log_action(db, patient, "reschedule", patient.id, old_label, new.token_label, None, hospital_id=new.hospital_id, commit=False)
        db.commit()
        db.refresh(new)
        return {"outcome": outcome, "appointment": appointment_view(db, new)}


STATE_MAP = {
    "booked_not_arrived": "booked", "self_reported_arrived": "arrived_unconfirmed", "present": "arrived", "called_absent": "called_absent",
}


def patient_state(appt: Appointment, e: QueueEntryRow | None) -> str:
    if appt.status in ("completed", "cancelled", "no_show"):
        return {"completed": "done"}.get(appt.status, appt.status)
    if e is None:
        return appt.status
    if e.status == "with_doctor":
        return "with_doctor"
    if e.status == "done":
        return "done"
    if e.status == "sent_to_er":
        return "sent_to_er"
    if e.presence == "present" and e.status in ("waiting", "fast_tracked"):
        return "arrived"
    return STATE_MAP.get(e.presence, "booked")


def appointment_view(db: Session, appt: Appointment) -> dict:
    doc = db.get(Doctor, appt.doctor_id)
    h = db.get(Hospital, appt.hospital_id)
    s = db.get(ClinicSession, appt.session_id) if appt.session_id else None
    e = queue.entry_for_appointment(db, appt.id)
    return {
        "id": appt.id, "type": appt.type, "status": appt.status, "date": appt.date.isoformat(),
        "token_number": appt.token_number, "token_label": appt.token_label,
        "est_call_from": timeutil.iso(appt.est_call_from), "est_call_to": timeutil.iso(appt.est_call_to), "estimate_is_approximate": True,
        "doctor": {"id": doc.id, "name": doc.name, "specialty": doc.specialty} if doc else None,
        "hospital": {"id": h.id, "name": h.name, "address": h.address, "area": h.area, "lat": h.lat, "lon": h.lon,
                     "er_phone": h.er_phone, "walk_in_window_text": h.walk_in_window_text} if h else None,
        "session": {"id": s.id, "label": s.label, "window_start": s.window_start, "window_end": s.window_end} if s else None,
        "state": patient_state(appt, e),
        "flagged_expected_today": appt.type == "walk_in" and appt.status == "expected_today",
        "intake_id": appt.intake_id,
    }


def status(db: Session, appt: Appointment) -> dict:
    queue.refresh_estimate(db, appt)
    db.commit()
    serving = queue.now_serving(db, appt.doctor_id, appt.date)
    v = appointment_view(db, appt)
    v["now_serving"] = serving.token_label if serving else None
    return v
