"""Doctor dashboard API: today's list (nurse order, read-only), patient workspace, override, search."""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.audit import log_action, log_view
from app.auth.deps import doctor_profile, require_doctor
from app.common import timeutil
from app.db import get_session
from app.ehr.adapter import get_adapter
from app.ehr.history_policy import AccessDenied, audit_scope, view_for_doctor
from app.ehr.router import has_relationship
from app.models import Appointment, Hospital, Patient, User
from app.pipeline import store
from app.queue import service as q
from app.queue.router import _summary_block

router = APIRouter(prefix="/doctor", tags=["Doctor"])


@router.get("/today")
def today(user: User = Depends(require_doctor), db: Session = Depends(get_session)):
    doc = doctor_profile(db, user)
    day = timeutil.today()
    label = q.current_session_label()
    entries = q.day_entries(db, doc.id, day)
    cur = q.with_doctor(db, doc.id, day)
    ordered = []
    for lbl in (label, "afternoon" if label == "morning" else "morning"):
        ordered += q.ordered_waiting(db, doc.id, day, lbl)
    h = db.get(Hospital, doc.hospital_id)
    from app.models import NurseAssignment
    assignment = db.exec(select(NurseAssignment).where(NurseAssignment.doctor_id == doc.id)).first()
    nurse_u = db.get(User, assignment.nurse_id) if assignment else None
    return {
        "doctor": {"id": doc.id, "name": doc.name, "specialty": doc.specialty, "hospital": h.name if h else "", "room": doc.room},
        "assigned_nurse": {"id": nurse_u.id, "name": nurse_u.full_name} if nurse_u else None,
        "date": day.isoformat(), "session": label,
        "with_doctor": q.to_contract(db, cur) if cur else None,
        "next": q.to_contract(db, ordered[0]) if ordered else None,
        "present": [q.to_contract(db, e) for e in ordered],
        "not_arrived_count": len([e for e in entries if e.presence != "present" and e.status == "waiting"]),
        "done_count": len([e for e in entries if e.status == "done"]),
        "order_note": "Order is set by the nurse (token order unless she changed it). Read-only here.",
    }


@router.post("/start/{entry_id}")
def start_consult(entry_id: int, user: User = Depends(require_doctor), db: Session = Depends(get_session)):
    """Doctor calls a present patient in (marks 'with doctor'). Does not change anyone's queue position."""
    e = q.get_entry_for_staff(db, entry_id, user)
    cur = q.with_doctor(db, e.doctor_id, e.date)
    if cur and cur.id != e.id:
        raise HTTPException(409, f"Finish {cur.token_label} first")
    return q.to_contract(db, q.nurse_action(db, e, "mark_with_doctor", user))


@router.get("/patient/{patient_id}")
def patient_workspace(patient_id: int, appointment_id: Optional[int] = None, user: User = Depends(require_doctor),
                      db: Session = Depends(get_session)):
    doc = doctor_profile(db, user)
    if not has_relationship(db, doc.id, patient_id):
        raise HTTPException(403, "No appointment relationship with this patient")
    u, p = db.get(User, patient_id), db.get(Patient, patient_id)
    appts = db.exec(select(Appointment).where(Appointment.doctor_id == doc.id, Appointment.patient_id == patient_id,
                                              Appointment.status != "cancelled").order_by(Appointment.date.desc(), Appointment.id.desc())).all()
    appt = next((a for a in appts if a.id == appointment_id), None) if appointment_id else None
    appt = appt or next((a for a in appts if a.date == timeutil.today() and a.status not in ("completed",)), None) or (appts[0] if appts else None)
    try:
        history = view_for_doctor(get_adapter(db).get_encounters(patient_id), doc.id, True, p.share_history_consent)
    except AccessDenied:
        raise HTTPException(403, "No access")
    log_view(db, user, patient_id, audit_scope(history))
    e = q.entry_for_appointment(db, appt.id) if appt else None
    v = q.latest_vitals(db, e.id) if e else None
    return {
        "patient": {"id": u.id, "full_name": u.full_name, "age": p.dob_or_age, "language": p.language},
        "appointment": {"id": appt.id, "status": appt.status, "token_label": appt.token_label, "date": appt.date.isoformat(),
                        "type": appt.type} if appt else None,
        "entry": q.to_contract(db, e) if e else None,
        **(_summary_block(db, appt) if appt and appt.intake_id else {"summary": None, "lines": [], "answers": None}),
        "vitals": v.model_dump() if v else None,
        "history": history,
    }


class OverrideRequest(BaseModel):
    appointment_id: int
    priority: Literal["emergency", "same-day", "routine"]
    reason: str = Field(min_length=1, max_length=300)


@router.post("/override")
def override(req: OverrideRequest, user: User = Depends(require_doctor), db: Session = Depends(get_session)):
    doc = doctor_profile(db, user)
    appt = db.get(Appointment, req.appointment_id)
    if appt is None or appt.doctor_id != doc.id:
        raise HTTPException(404, "Appointment not found")
    d = q.save_decision_override(db, appt, req.priority, req.reason.strip(), user)
    db.commit()
    return d


@router.get("/patients")
def patients(query: str = Query("", max_length=60), user: User = Depends(require_doctor), db: Session = Depends(get_session)):
    """Search among THIS doctor's own patients (appointment relationship), with encounters this doctor wrote."""
    doc = doctor_profile(db, user)
    ids = sorted({a.patient_id for a in db.exec(select(Appointment).where(Appointment.doctor_id == doc.id, Appointment.status != "cancelled")).all()})
    term = query.strip().lower()
    adapter = get_adapter(db)
    out = []
    for pid in ids:
        u = db.get(User, pid)
        if term and term not in u.full_name.lower():
            continue
        own = [e for e in adapter.get_encounters(pid) if e.doctor_id == doc.id]
        out.append({"patient_id": pid, "full_name": u.full_name,
                    "encounters": [{"id": e.id, "date": e.date.isoformat(), "diagnosis_text": e.diagnosis_text} for e in own]})
    if out:
        log_action(db, user, "doctor_patient_search", None, None, str(len(out)), None, hospital_id=doc.hospital_id)
    return out[:50]
