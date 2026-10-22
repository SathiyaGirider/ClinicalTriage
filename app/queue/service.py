"""Queue entries, presence, check-in, nurse actions, flags, vitals, alerts, estimates."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import HTTPException
from sqlmodel import Session, select

from app.audit import log_action
from app.catalog.service import session_start
from app.common import timeutil
from app.common.ids import token_label
from app.common.schemas import IntakeAddendum, QueueEntry, TriageDecision
from app.config import settings
from app.models import Appointment, ClinicSession, Doctor, QueueEntryRow, QueueOrderMode, User, Vitals
from app.pipeline import store
from app.queue.ordering import is_walk_in, order_queue
from app.triage.rules import VitalsInput
from app.triage.service import reclassify

ACTIVE = ("waiting", "fast_tracked", "with_doctor")


def current_session_label(now: datetime | None = None) -> str:
    now = now or timeutil.now()
    _, morning_end = timeutil.window(settings.morning_window)
    return "morning" if now.time() < morning_end or now.hour < 13 else "afternoon"


# ---------------------------------------------------------------- creation

def create_entry(db: Session, appt: Appointment, s: ClinicSession | None, flagged: bool, flag_reason: str | None) -> QueueEntryRow:
    e = QueueEntryRow(
        appointment_id=appt.id, doctor_id=appt.doctor_id, session_id=s.id if s else None, session_label=s.label if s else None,
        date=appt.date, token_number=appt.token_number, token_label=appt.token_label, presence="booked_not_arrived",
        status="waiting", flagged=flagged, flag_source="ai" if flagged else None, flag_reason=flag_reason if flagged else None,
        flagged_at=timeutil.now() if flagged else None,
    )
    db.add(e)
    db.flush()
    return e


def entry_for_appointment(db: Session, appt_id: int) -> QueueEntryRow | None:
    return db.exec(select(QueueEntryRow).where(QueueEntryRow.appointment_id == appt_id)).first()


# ---------------------------------------------------------------- access

def doctor_hospital(db: Session, doctor_id: int) -> int:
    d = db.get(Doctor, doctor_id)
    return d.hospital_id if d else -1


def get_nurse_assigned_doctor(db: Session, nurse: User) -> Doctor:
    from app.models import NurseAssignment
    assignment = db.exec(select(NurseAssignment).where(NurseAssignment.nurse_id == nurse.id)).first()
    if not assignment:
        log_action(db, nurse, "unassigned_nurse_blocked", None, None, None, "Nurse has no assigned doctor", hospital_id=nurse.hospital_id)
        raise HTTPException(403, "No doctor assigned. Please contact the administrator.")
    doc = db.get(Doctor, assignment.doctor_id)
    if not doc:
        raise HTTPException(403, "Assigned doctor not found")
    return doc


def get_entry_for_staff(db: Session, entry_id: int, user: User) -> QueueEntryRow:
    e = db.get(QueueEntryRow, entry_id)
    if e is None:
        raise HTTPException(404, "Queue entry not found")
    if user.role == "nurse":
        doc = get_nurse_assigned_doctor(db, user)
        if e.doctor_id != doc.id:
            log_action(db, user, "cross_doctor_access_blocked", None, str(e.doctor_id), str(doc.id),
                       "Nurse attempted to access another doctor's queue entry", hospital_id=user.hospital_id)
            raise HTTPException(403, "Not allowed: this patient belongs to another doctor")
    if user.role == "doctor":
        doc = db.exec(select(Doctor).where(Doctor.user_id == user.id)).first()
        if not doc or doc.id != e.doctor_id:
            raise HTTPException(403, "Not your patient")
    return e


# ---------------------------------------------------------------- modes and order

def get_mode(db: Session, doctor_id: int, day: date, label: str) -> str:
    row = db.exec(select(QueueOrderMode).where(QueueOrderMode.doctor_id == doctor_id, QueueOrderMode.date == day,
                                               QueueOrderMode.session_label == label)).first()
    return row.mode if row else "token"


def set_mode(db: Session, doctor_id: int, day: date, label: str, mode: str) -> None:
    row = db.exec(select(QueueOrderMode).where(QueueOrderMode.doctor_id == doctor_id, QueueOrderMode.date == day,
                                               QueueOrderMode.session_label == label)).first()
    if row is None:
        row = QueueOrderMode(doctor_id=doctor_id, date=day, session_label=label, mode=mode)
    row.mode = mode
    db.add(row)


def day_entries(db: Session, doctor_id: int, day: date, label: str | None = None) -> list[QueueEntryRow]:
    q = select(QueueEntryRow).where(QueueEntryRow.doctor_id == doctor_id, QueueEntryRow.date == day)
    if label:
        q = q.where(QueueEntryRow.session_label == label)
    return list(db.exec(q).all())


def ordered_waiting(db: Session, doctor_id: int, day: date, label: str) -> list[QueueEntryRow]:
    entries = day_entries(db, doctor_id, day, label)
    return order_queue(entries, get_mode(db, doctor_id, day, label), settings.walkin_policy)


def with_doctor(db: Session, doctor_id: int, day: date) -> QueueEntryRow | None:
    rows = db.exec(select(QueueEntryRow).where(QueueEntryRow.doctor_id == doctor_id, QueueEntryRow.date == day,
                                               QueueEntryRow.status == "with_doctor")).all()
    return max(rows, key=lambda e: e.called_at or datetime.min) if rows else None


def now_serving(db: Session, doctor_id: int, day: date) -> QueueEntryRow | None:
    return with_doctor(db, doctor_id, day)


def pin_order(db: Session, ordered: list[QueueEntryRow]) -> None:
    for i, e in enumerate(ordered):
        if e.status == "fast_tracked":
            continue
        e.nurse_position = i
        db.add(e)


def clear_positions(db: Session, doctor_id: int, day: date, label: str) -> None:
    for e in day_entries(db, doctor_id, day, label):
        if e.nurse_position is not None:
            e.nurse_position = None
            db.add(e)


# ---------------------------------------------------------------- alerts

def alert_state(e: QueueEntryRow, now: datetime | None = None) -> str:
    if not e.flagged or e.acknowledged_at is not None:
        return "none"
    if e.presence != "present":
        return "normal"
    now = now or timeutil.now()
    start = max([t for t in (e.flagged_at, e.check_in_ts) if t] or [now])
    elapsed = (now - start).total_seconds()
    if elapsed >= settings.alert_red_seconds:
        return "red"
    if elapsed >= settings.alert_amber_seconds:
        return "amber"
    return "normal"


# ---------------------------------------------------------------- serialisation

def to_contract(db: Session, e: QueueEntryRow, now: datetime | None = None) -> QueueEntry:
    now = now or timeutil.now()
    appt = db.get(Appointment, e.appointment_id)
    patient = db.get(User, appt.patient_id)
    decision = store.latest_decision(db, appt.intake_id)
    intake = store.load_intake(db, appt.intake_id)
    return QueueEntry(
        id=e.id, appointment_id=appt.id, patient_id=appt.patient_id, patient_name=patient.full_name if patient else "",
        doctor_id=e.doctor_id, date=e.date.isoformat(), session_label=e.session_label, token_number=e.token_number,
        token_label=e.token_label, appointment_type=appt.type, presence=e.presence, status=e.status, flagged=e.flagged,
        flag_source=e.flag_source, flag_reason=e.flag_reason, acknowledged=e.acknowledged_at is not None,
        alert_state=alert_state(e, now), checkin_change=e.checkin_change, check_in_ts=timeutil.iso(e.check_in_ts),
        late_arrival=e.late_arrival, fast_tracked=e.status == "fast_tracked", nurse_position=e.nurse_position,
        waiting_seconds=int((now - e.check_in_ts).total_seconds()) if e.check_in_ts and e.status in ("waiting", "fast_tracked") else None,
        chief_complaint=intake.chief_complaint if intake else None,
        priority=decision.priority if decision else None,
        priority_rationale=decision.priority_rationale if decision else None,
        decided_by=decision.decided_by if decision else None,
        red_flags=decision.red_flags_matched if decision else [],
        rule_based=bool(decision and decision.decided_by == "rule"),
        audit_notes=decision.audit_notes if decision else [],
    )


# ---------------------------------------------------------------- estimates

def recent_avg_minutes(db: Session, doctor_id: int, day: date, default: int) -> float:
    rows = db.exec(select(QueueEntryRow).where(QueueEntryRow.doctor_id == doctor_id, QueueEntryRow.date == day,
                                               QueueEntryRow.status == "done")).all()
    durs = sorted([(r.done_at, (r.done_at - r.called_at).total_seconds() / 60) for r in rows if r.done_at and r.called_at])[-5:]
    return sum(d for _, d in durs) / len(durs) if durs else float(default)


def estimate(db: Session, appt: Appointment, now: datetime | None = None) -> tuple[datetime | None, datetime | None]:
    """Approximate call range. Initial: session start + active tokens ahead x consult minutes.
    Once the doctor has started: now + entries ahead in the live order x recent average consult."""
    now = now or timeutil.now()
    if appt.status in ("completed", "cancelled", "no_show") or appt.token_number is None:
        return None, None
    doc = db.get(Doctor, appt.doctor_id)
    e = entry_for_appointment(db, appt.id)
    if e is None:
        return None, None
    if e.status == "with_doctor":
        return now, now
    entries = day_entries(db, appt.doctor_id, appt.date, e.session_label)
    started = any(x.called_at for x in entries)
    if not started or appt.date != now.date():
        start = session_start(db.get(ClinicSession, appt.session_id)) if appt.session_id else now
        ahead = [x for x in entries if x.status in ACTIVE and x.presence != "no_show" and x.token_number is not None
                 and not is_walk_in(x) and x.token_number < appt.token_number]
        base = max(start, now) if appt.date == now.date() else start
        est = base + timedelta(minutes=len(ahead) * doc.consult_minutes)
    else:
        avg = recent_avg_minutes(db, appt.doctor_id, appt.date, doc.consult_minutes)
        if e.presence == "present":
            order = ordered_waiting(db, appt.doctor_id, appt.date, e.session_label)
            ahead_n = next((i for i, x in enumerate(order) if x.id == e.id), len(order))
        else:
            ahead_n = len([x for x in entries if x.status in ("waiting", "fast_tracked") and x.token_number is not None
                           and not is_walk_in(x) and x.token_number < appt.token_number])
        current = 1 if any(x.status == "with_doctor" for x in entries) else 0
        est = now + timedelta(minutes=(ahead_n + current) * avg)
    est = est.replace(second=0, microsecond=0)
    return est, est + timedelta(minutes=30)


def refresh_estimate(db: Session, appt: Appointment) -> None:
    appt.est_call_from, appt.est_call_to = estimate(db, appt)
    db.add(appt)


# ---------------------------------------------------------------- flags

def set_flag(db: Session, e: QueueEntryRow, source: str, reason: str) -> None:
    if not e.flagged:
        e.flagged_at = timeutil.now()
        e.acknowledged_at = None
    e.flagged, e.flag_source, e.flag_reason = True, source, reason
    db.add(e)


def apply_addendum(db: Session, appt: Appointment, text: str, change: str, source: str, actor: User | None):
    """Merge a check-in change into the intake and re-run triage (raise-only)."""
    intake = store.load_intake(db, appt.intake_id)
    prev = store.latest_decision(db, appt.intake_id)
    if intake is None or prev is None:
        return None, False, []
    from app.common.symptom_vocab import detect_tags
    intake.addenda = list(intake.addenda) + [IntakeAddendum(ts=timeutil.now().isoformat(), change=change, text=text[:2000],
                                                             symptom_tags=detect_tags(text), source=source)]
    from app.models import IntakeRecord
    store.update_intake(db, db.get(IntakeRecord, appt.intake_id), intake)
    new, raised, reasons = reclassify(intake, prev)
    note = "patient_reported_worse_at_checkin" if change == "worse" else "patient_reported_new_symptom_at_checkin"
    new.audit_notes = list(dict.fromkeys(new.audit_notes + [note]))
    store.save_decision(db, appt.intake_id, new)
    if raised:
        log_action(db, actor, "priority_raised_by_recheck", appt.patient_id, prev.priority, new.priority,
                   "; ".join(reasons), hospital_id=appt.hospital_id, commit=False)
    return new, raised, reasons


def save_decision_override(db: Session, appt: Appointment, new_priority: str, reason: str, actor: User) -> TriageDecision:
    prev = store.latest_decision(db, appt.intake_id)
    if prev is None:
        raise HTTPException(409, "No triage decision to change")
    d = prev.model_copy(deep=True)
    d.priority = new_priority
    d.decided_by = "human"
    d.priority_rationale = f"Changed by {actor.role}: {reason}"
    d.audit_notes = list(dict.fromkeys(d.audit_notes + [f"override_by_{actor.role}"]))
    d.timestamp = timeutil.now().isoformat()
    d.flag_for_nurse = d.priority != "routine" or d.flag_for_nurse
    store.save_decision(db, appt.intake_id, d)
    log_action(db, actor, "change_priority", appt.patient_id, prev.priority, new_priority, reason, hospital_id=appt.hospital_id, commit=False)
    return d


# ---------------------------------------------------------------- check-in

def next_walkin_number(db: Session, doctor_id: int, day: date) -> int:
    rows = db.exec(select(QueueEntryRow).where(QueueEntryRow.doctor_id == doctor_id, QueueEntryRow.date == day)).all()
    nums = [r.token_number for r in rows if is_walk_in(r) and r.token_number]
    return max(nums, default=0) + 1


def check_in(db: Session, e: QueueEntryRow, outcome: str, note: str | None, nurse: User) -> dict:
    if e.date != timeutil.today():
        raise HTTPException(409, "Check-in is only possible on the appointment day")
    if e.presence == "present":
        raise HTTPException(409, "Already checked in")
    if e.status in ("done", "no_show", "sent_to_er"):
        raise HTTPException(409, f"Entry is {e.status}")
    appt = db.get(Appointment, e.appointment_id)
    serving = now_serving(db, e.doctor_id, e.date)
    late = e.late_arrival or e.presence == "called_absent" or bool(
        serving and serving.token_number and e.token_number and not is_walk_in(e) and e.session_label == serving.session_label
        and e.token_number < serving.token_number)
    if appt.type == "walk_in" and e.token_number is None:
        n = next_walkin_number(db, e.doctor_id, e.date)
        e.token_number, e.token_label = n, token_label(None, n, walk_in=True)
        e.session_label = current_session_label()
        appt.token_number, appt.token_label = e.token_number, e.token_label
    e.presence, e.checked_in_by, e.check_in_ts, e.checkin_change, e.late_arrival = "present", nurse.id, timeutil.now(), outcome, late
    appt.status = "checked_in"
    db.add(appt)
    db.add(e)
    log_action(db, nurse, "check_in", appt.patient_id, None, outcome, note[:200] if note else None, hospital_id=appt.hospital_id, commit=False)
    raised, reasons = False, []
    if outcome in ("worse", "new_symptom"):
        set_flag(db, e, "nurse", "Reported worse at check-in" if outcome == "worse" else "New symptom at check-in")
        if note and note.strip():
            _, raised, reasons = apply_addendum(db, appt, note, outcome, "nurse", nurse)
        else:
            prev = store.latest_decision(db, appt.intake_id)
            if prev:
                d = prev.model_copy(deep=True)
                d.audit_notes = list(dict.fromkeys(d.audit_notes + [f"patient_reported_{outcome}_at_checkin"]))
                d.flag_for_nurse = True
                store.save_decision(db, appt.intake_id, d)
    refresh_estimate(db, appt)
    db.commit()
    return {"entry": to_contract(db, e), "recheck_recommended": outcome in ("worse", "new_symptom"),
            "priority_raised": raised, "raise_reasons": reasons}


def patient_arrived(db: Session, appt: Appointment, change: str, text: str | None, patient: User) -> dict:
    e = entry_for_appointment(db, appt.id)
    if e is None or appt.status in ("cancelled", "completed", "no_show"):
        raise HTTPException(409, "This appointment is not active")
    if appt.date != timeutil.today():
        raise HTTPException(409, "You can only tell us you are here on the day of your appointment")
    if e.presence == "present":
        return {"state": "present", "message": "You are checked in."}
    if e.presence == "called_absent":
        e.late_arrival = True
    e.presence, e.self_reported_ts, e.checkin_change = "self_reported_arrived", timeutil.now(), change
    db.add(e)
    log_action(db, patient, "self_reported_arrival", appt.patient_id, None, change, None, hospital_id=appt.hospital_id, commit=False)
    if change in ("worse", "new_symptom"):
        set_flag(db, e, "ai", "Patient reported worse" if change == "worse" else "Patient reported a new symptom")
        if text and text.strip():
            apply_addendum(db, appt, text, change, "patient", patient)
    db.commit()
    return {"state": "self_reported_arrived", "message": "Waiting for the nurse to confirm."}


# ---------------------------------------------------------------- nurse actions

def _need_reason(reason: str | None, what: str) -> str:
    if not reason or not reason.strip():
        raise HTTPException(422, f"A reason is required to {what}")
    return reason.strip()[:300]


def mark_called_absent(db: Session, e: QueueEntryRow) -> None:
    if e.token_number is None or is_walk_in(e):
        return
    for other in day_entries(db, e.doctor_id, e.date, e.session_label):
        if other.presence == "booked_not_arrived" and other.token_number and not is_walk_in(other) and other.token_number < e.token_number:
            other.presence = "called_absent"
            db.add(other)


def nurse_action(db: Session, e: QueueEntryRow, action: str, actor: User, reason: str | None = None,
                 position: int | None = None, priority: str | None = None) -> QueueEntryRow:
    appt = db.get(Appointment, e.appointment_id)
    before = e.status
    label = e.session_label or current_session_label()
    if action == "acknowledge":
        e.acknowledged_at = timeutil.now()
    elif action == "send_to_er":
        e.status = "sent_to_er"
        appt.status = "escalated"
    elif action == "fast_track":
        if e.presence != "present":
            raise HTTPException(409, "Only present patients can be fast-tracked")
        e.status, e.fast_tracked_at = "fast_tracked", timeutil.now()
    elif action == "return_to_queue":
        e.status, e.fast_tracked_at, e.nurse_position = "waiting", None, None
    elif action in ("move_up", "move_down", "move_to"):
        if get_mode(db, e.doctor_id, e.date, label) != "nurse":
            raise HTTPException(409, "Switch to 'My order' to move patients")
        order = [x for x in ordered_waiting(db, e.doctor_id, e.date, label) if x.status == "waiting"]
        if e not in order:
            raise HTTPException(409, "Patient is not waiting in the queue")
        i = order.index(e)
        j = {"move_up": i - 1, "move_down": i + 1}.get(action, position if position is not None else i)
        j = max(0, min(len(order) - 1, j))
        order.insert(j, order.pop(i))
        pin_order(db, order)
        log_action(db, actor, action, appt.patient_id, str(i + 1), str(j + 1), reason, hospital_id=appt.hospital_id, commit=False)
        db.commit()
        return e
    elif action == "mark_with_doctor":
        if e.presence != "present":
            raise HTTPException(409, "Patient is not present")
        e.status, e.called_at = "with_doctor", timeutil.now()
        appt.status = "with_doctor"
        mark_called_absent(db, e)
    elif action == "mark_done":
        e.status, e.done_at = "done", timeutil.now()
        if appt.status != "completed":
            appt.status = "completed"
    elif action == "mark_no_show":
        if e.presence == "present":
            raise HTTPException(409, "Patient is present; cannot mark no-show")
        e.status = "no_show"
        appt.status = "no_show"
    elif action == "change_priority":
        if priority not in ("emergency", "same-day", "routine"):
            raise HTTPException(422, "priority must be emergency, same-day or routine")
        save_decision_override(db, appt, priority, _need_reason(reason, "change the priority"), actor)
        db.commit()
        return e
    else:
        raise HTTPException(422, "Unknown action")
    db.add(e)
    db.add(appt)
    log_action(db, actor, action, appt.patient_id, before, e.status, reason, hospital_id=appt.hospital_id, commit=False)
    db.commit()
    return e


def flag(db: Session, e: QueueEntryRow, flagged: bool, reason: str | None, actor: User) -> QueueEntryRow:
    r = _need_reason(reason, "flag or unflag a patient")
    appt = db.get(Appointment, e.appointment_id)
    if flagged:
        set_flag(db, e, "nurse", r)
    else:
        e.flagged, e.flag_source, e.flag_reason, e.flagged_at = False, None, None, None
        db.add(e)
    log_action(db, actor, "flag" if flagged else "unflag", appt.patient_id, str(not flagged), str(flagged), r, hospital_id=appt.hospital_id, commit=False)
    db.commit()
    return e


def record_vitals(db: Session, e: QueueEntryRow, v: VitalsInput, actor: User) -> dict:
    appt = db.get(Appointment, e.appointment_id)
    db.add(Vitals(queue_entry_id=e.id, bp_sys=v.bp_sys, bp_dia=v.bp_dia, temp_c=v.temp_c, spo2=v.spo2, pulse=v.pulse, entered_by=actor.id))
    log_action(db, actor, "vitals_entered", appt.patient_id, None, None, None, hospital_id=appt.hospital_id, commit=False)
    intake = store.load_intake(db, appt.intake_id)
    prev = store.latest_decision(db, appt.intake_id)
    raised, reasons, message = False, [], None
    if intake and prev:
        new, raised, reasons = reclassify(intake, prev, vitals=v, use_llm=False)
        if raised:
            store.save_decision(db, appt.intake_id, new)
            set_flag(db, e, "ai", "Priority raised by vitals: " + "; ".join(reasons))
            message = "Priority raised: " + "; ".join(reasons) + "."
            log_action(db, None, "priority_raised_by_vitals", appt.patient_id, prev.priority, new.priority, "; ".join(reasons),
                       hospital_id=appt.hospital_id, commit=False)
    db.commit()
    return {"priority_raised": raised, "message": message or "Vitals saved. Priority unchanged.", "entry": to_contract(db, e)}


def latest_vitals(db: Session, entry_id: int) -> Vitals | None:
    return db.exec(select(Vitals).where(Vitals.queue_entry_id == entry_id).order_by(Vitals.id.desc())).first()
