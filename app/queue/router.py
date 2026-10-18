"""Nurse queue API. Nurses act only on their own hospital's doctors."""

from datetime import date as Date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.audit import log_action
from app.auth.deps import require_nurse, require_staff
from app.auth.security import UNUSABLE_PASSWORD
from app.common import timeutil
from app.common.ids import new_id
from app.db import get_session
from app.models import ActionLog, Appointment, Doctor, Patient, User
from app.pipeline import store
from app.queue import service as q
from app.triage.router import VitalsBody
from app.triage.rules import VitalsInput
from app.triage.summary import render_lines

router = APIRouter(prefix="/queue", tags=["Queue (nurse)"])


def _doctor_in_hospital(db: Session, doctor_id: int, nurse: User) -> Doctor:
    d = db.get(Doctor, doctor_id)
    if d is None or d.hospital_id != nurse.hospital_id:
        raise HTTPException(403, "Doctor is not in your hospital")
    return d


def _summary_block(db: Session, appt: Appointment) -> dict:
    s = store.latest_summary(db, appt.intake_id)
    d = store.latest_decision(db, appt.intake_id)
    intake = store.load_intake(db, appt.intake_id)
    if s and d:  # keep priority + rationale in sync with the latest decision
        s.priority, s.priority_rationale, s.red_flags = d.priority, d.priority_rationale, d.red_flags_matched
        s.audit_notes = list(dict.fromkeys(s.audit_notes + d.audit_notes))
    return {
        "summary": s.model_dump() if s else None,
        "lines": render_lines(s) if s else [],
        "answers": ({"your_words": intake.raw_transcript, "follow_up_answers": intake.follow_up_answers,
                     "safety_screen": intake.safety_screen, "addenda": [a.model_dump() for a in intake.addenda],
                     "assisted": intake.assisted} if intake else None),
    }


@router.get("")
def get_queue(doctor_id: Optional[int] = None, date: Optional[Date] = None, session: Optional[Literal["morning", "afternoon"]] = None,
              nurse: User = Depends(require_nurse), db: Session = Depends(get_session)):
    """Dashboard data: needs attention, present and waiting, booked not arrived, expected today (flagged), doctors."""
    day = date or timeutil.today()
    label = session or q.current_session_label()
    docs = db.exec(select(Doctor).where(Doctor.hospital_id == nurse.hospital_id)).all()
    if doctor_id:
        docs = [_doctor_in_hospital(db, doctor_id, nurse)]
    now = timeutil.now()
    out = {"date": day.isoformat(), "session": label, "doctors": []}
    for d in docs:
        entries = q.day_entries(db, d.id, day)
        ordered = q.ordered_waiting(db, d.id, day, label)
        cur = q.with_doctor(db, d.id, day)
        attention = [x for x in entries if x.flagged and x.presence == "present" and x.status in ("waiting", "fast_tracked")]
        attention_c = [q.to_contract(db, x, now) for x in attention]
        attention_c.sort(key=lambda c: (c.priority != "emergency", c.check_in_ts or ""))
        not_arrived = [x for x in entries if x.presence in ("booked_not_arrived", "self_reported_arrived", "called_absent")
                       and x.status == "waiting" and (x.session_label in (label, None))]
        if not (attention or ordered or cur or not_arrived) and doctor_id is None:
            continue
        out["doctors"].append({
            "doctor": {"id": d.id, "name": d.name, "specialty": d.specialty},
            "mode": q.get_mode(db, d.id, day, label),
            "now_serving": cur.token_label if cur else None,
            "with_doctor": q.to_contract(db, cur, now) if cur else None,
            "next": q.to_contract(db, ordered[0], now) if ordered else None,
            "needs_attention": attention_c,
            "present_waiting": [q.to_contract(db, x, now) for x in ordered],
            "booked_not_arrived": [q.to_contract(db, x, now) for x in not_arrived if not x.flagged],
            "expected_today_flagged": [q.to_contract(db, x, now) for x in not_arrived if x.flagged],
            "still_to_come": len(not_arrived),
            "done_count": len([x for x in entries if x.status == "done"]),
            "total": len(entries),
        })
    return out


@router.get("/search")
def search(query: str = Query(min_length=1, max_length=60), nurse: User = Depends(require_nurse), db: Session = Depends(get_session)):
    """Check-in desk: today's entries in this hospital by token label or name."""
    term = query.strip().lower()
    doc_ids = [d.id for d in db.exec(select(Doctor).where(Doctor.hospital_id == nurse.hospital_id)).all()]
    out = []
    for d_id in doc_ids:
        for e in q.day_entries(db, d_id, timeutil.today()):
            c = q.to_contract(db, e)
            if term in (c.token_label or "").lower() or term in c.patient_name.lower() or term == str(c.token_number):
                out.append(c)
    return out[:30]


@router.get("/entry/{entry_id}")
def entry_detail(entry_id: int, nurse: User = Depends(require_nurse), db: Session = Depends(get_session)):
    """Patient drawer: 5-line summary, answers, vitals. Never diagnosis history or prescriptions."""
    e = q.get_entry_for_staff(db, entry_id, nurse)
    appt = db.get(Appointment, e.appointment_id)
    v = q.latest_vitals(db, e.id)
    log_action(db, nurse, "view_triage_summary", appt.patient_id, None, None, None, hospital_id=appt.hospital_id)
    return {"entry": q.to_contract(db, e), **_summary_block(db, appt), "vitals": v.model_dump() if v else None}


class CheckInRequest(BaseModel):
    outcome: Literal["none", "better", "worse", "new_symptom"]
    note: Optional[str] = Field(default=None, max_length=2000)


@router.post("/{entry_id}/check-in")
def check_in(entry_id: int, req: CheckInRequest, nurse: User = Depends(require_nurse), db: Session = Depends(get_session)):
    return q.check_in(db, q.get_entry_for_staff(db, entry_id, nurse), req.outcome, req.note, nurse)


@router.post("/{entry_id}/recheck/start")
def recheck_start(entry_id: int, change: Literal["worse", "new_symptom"] = "worse", nurse: User = Depends(require_nurse),
                  db: Session = Depends(get_session)):
    from app.intake.session_router import start_for_patient
    e = q.get_entry_for_staff(db, entry_id, nurse)
    appt = db.get(Appointment, e.appointment_id)
    p = db.get(Patient, appt.patient_id)
    base = store.load_intake(db, appt.intake_id)
    return start_for_patient(db, nurse, p, "recheck", "en", appointment_id=appt.id,
                             base_intake=base.model_dump() if base else None,
                             extra={"change_kind": change, "addendum_source": "nurse"})


class WalkInRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    age: int = Field(ge=0, le=125)
    language: Literal["en", "ta"] = "en"
    doctor_id: int

    model_config = {"extra": "forbid"}


@router.post("/walk-in", status_code=201)
def walk_in(req: WalkInRequest, nurse: User = Depends(require_nurse), db: Session = Depends(get_session)):
    """Register a walk-in (no phone, no ID), issue a W token now, then run assisted intake."""
    doc = _doctor_in_hospital(db, req.doctor_id, nurse)
    user = User(email=f"walkin-{new_id()}@walkin.invalid", password_hash=UNUSABLE_PASSWORD, role="patient", full_name=req.full_name.strip())
    db.add(user)
    db.flush()
    db.add(Patient(user_id=user.id, dob_or_age=str(req.age), language=req.language, is_walk_in=True))
    appt = Appointment(patient_id=user.id, doctor_id=doc.id, hospital_id=doc.hospital_id, date=timeutil.today(), type="walk_in",
                       status="expected_today")
    db.add(appt)
    db.flush()
    e = q.create_entry(db, appt, None, False, None)
    log_action(db, nurse, "register_walk_in", user.id, None, str(appt.id), None, commit=False)
    db.commit()
    res = q.check_in(db, e, "none", None, nurse)
    return {"patient_id": user.id, "appointment_id": appt.id, **res}


class AssistedStart(BaseModel):
    entry_id: int


@router.post("/assisted-intake/start")
def assisted_start(req: AssistedStart, nurse: User = Depends(require_nurse), db: Session = Depends(get_session)):
    from app.intake.session_router import start_for_patient
    e = q.get_entry_for_staff(db, req.entry_id, nurse)
    appt = db.get(Appointment, e.appointment_id)
    if appt.intake_id:
        raise HTTPException(409, "This patient already has an intake; use the re-check instead")
    p = db.get(Patient, appt.patient_id)
    # Staff run the questions in English; patient's own words are typed as said.
    return start_for_patient(db, nurse, p, "assisted", "en", appointment_id=appt.id)


@router.post("/{entry_id}/ack")
def ack(entry_id: int, nurse: User = Depends(require_nurse), db: Session = Depends(get_session)):
    e = q.nurse_action(db, q.get_entry_for_staff(db, entry_id, nurse), "acknowledge", nurse)
    return q.to_contract(db, e)


class ActionRequest(BaseModel):
    entry_id: int
    action: Literal["acknowledge", "send_to_er", "fast_track", "return_to_queue", "move_up", "move_down", "move_to",
                    "mark_with_doctor", "mark_done", "mark_no_show", "change_priority"]
    reason: Optional[str] = Field(default=None, max_length=300)
    position: Optional[int] = Field(default=None, ge=0, le=500)
    priority: Optional[Literal["emergency", "same-day", "routine"]] = None


@router.post("/action")
def action(req: ActionRequest, nurse: User = Depends(require_nurse), db: Session = Depends(get_session)):
    e = q.nurse_action(db, q.get_entry_for_staff(db, req.entry_id, nurse), req.action, nurse, req.reason, req.position, req.priority)
    return q.to_contract(db, e)


class OrderRequest(BaseModel):
    doctor_id: int
    date: Optional[Date] = None
    session: Literal["morning", "afternoon"]
    mode: Literal["token", "nurse"]
    ordered_entry_ids: Optional[list[int]] = None


@router.post("/order")
def order(req: OrderRequest, nurse: User = Depends(require_nurse), db: Session = Depends(get_session)):
    _doctor_in_hospital(db, req.doctor_id, nurse)
    day = req.date or timeutil.today()
    before = q.get_mode(db, req.doctor_id, day, req.session)
    q.set_mode(db, req.doctor_id, day, req.session, req.mode)
    if req.mode == "token":
        q.clear_positions(db, req.doctor_id, day, req.session)
    db.flush()
    if req.mode == "nurse" and req.ordered_entry_ids:
        current = {e.id: e for e in q.ordered_waiting(db, req.doctor_id, day, req.session) if e.status == "waiting"}
        if set(req.ordered_entry_ids) - set(current):
            raise HTTPException(422, "ordered_entry_ids must be waiting patients of this doctor and session")
        listed = [current[i] for i in req.ordered_entry_ids]
        rest = [e for i, e in current.items() if i not in req.ordered_entry_ids]
        q.pin_order(db, listed + rest)
    log_action(db, nurse, "order_mode", None, before, req.mode, None, commit=False)
    db.commit()
    return {"mode": req.mode, "present_waiting": [q.to_contract(db, e) for e in q.ordered_waiting(db, req.doctor_id, day, req.session)]}


class FlagRequest(BaseModel):
    entry_id: int
    flagged: bool
    reason: str = Field(min_length=1, max_length=300)


@router.post("/flag")
def flag(req: FlagRequest, nurse: User = Depends(require_nurse), db: Session = Depends(get_session)):
    return q.to_contract(db, q.flag(db, q.get_entry_for_staff(db, req.entry_id, nurse), req.flagged, req.reason, nurse))


class VitalsRequest(VitalsBody):
    entry_id: int


@router.post("/vitals")
def vitals(req: VitalsRequest, nurse: User = Depends(require_nurse), db: Session = Depends(get_session)):
    v = VitalsInput(**req.model_dump(exclude={"entry_id"}))
    return q.record_vitals(db, q.get_entry_for_staff(db, req.entry_id, nurse), v, nurse)


@router.get("/expected-today")
def expected_today(doctor_id: Optional[int] = None, nurse: User = Depends(require_nurse), db: Session = Depends(get_session)):
    docs = [_doctor_in_hospital(db, doctor_id, nurse)] if doctor_id else db.exec(select(Doctor).where(Doctor.hospital_id == nurse.hospital_id)).all()
    out = []
    for d in docs:
        for e in q.day_entries(db, d.id, timeutil.today()):
            if e.presence != "present" and e.status == "waiting":
                out.append(q.to_contract(db, e))
    return {"flagged": [c for c in out if c.flagged], "others": [c for c in out if not c.flagged]}


@router.get("/action-log")
def action_log(limit: int = Query(200, ge=1, le=1000), nurse: User = Depends(require_nurse), db: Session = Depends(get_session)):
    rows = db.exec(select(ActionLog).where(ActionLog.hospital_id == nurse.hospital_id).order_by(ActionLog.id.desc()).limit(limit)).all()
    names = {}
    out = []
    for r in rows:
        if r.actor_user_id and r.actor_user_id not in names:
            u = db.get(User, r.actor_user_id)
            names[r.actor_user_id] = u.full_name if u else str(r.actor_user_id)
        out.append({**r.model_dump(), "ts": r.ts.isoformat(), "actor_name": names.get(r.actor_user_id, "system")})
    return out


@router.get("/doctors")
def doctors(user: User = Depends(require_staff), db: Session = Depends(get_session)):
    hid = user.hospital_id
    if user.role == "doctor":
        doc = db.exec(select(Doctor).where(Doctor.user_id == user.id)).first()
        hid = doc.hospital_id if doc else None
    return [{"id": d.id, "name": d.name, "specialty": d.specialty} for d in db.exec(select(Doctor).where(Doctor.hospital_id == hid)).all()]
