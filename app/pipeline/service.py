"""
intake -> triage -> summary -> PatientAdvice, fail safe at every step.
Patient text is never logged; only ids and decisions.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException
from sqlmodel import Session

from app.audit import log_action
from app.common.schemas import IntakeResult, TriageDecision
from app.intake import session as flow
from app.models import Appointment, BookingHold, IntakeSessionRow, Patient, User
from app.pipeline import store
from app.pipeline.advice import OUTCOME_EMERGENCY, make_advice, outcome_for
from app.triage.service import failsafe_decision, reclassify, triage
from app.triage.summary import generate_summary, template_summary

logger = logging.getLogger("lifeline.pipeline")


def load_session(db: Session, session_id: str, user: User) -> IntakeSessionRow:
    row = db.get(IntakeSessionRow, session_id)
    if row is None:
        raise HTTPException(404, "Intake session not found")
    if user.role == "patient" and row.patient_id != user.id:
        raise HTTPException(404, "Intake session not found")
    if user.role in ("nurse", "doctor") and row.created_by != user.id:
        raise HTTPException(403, "Not your intake session")
    return row


def _safe_build(state: dict, patient_id: int) -> IntakeResult:
    try:
        return flow.build_intake_result(state, str(patient_id))
    except Exception as exc:
        logger.error("intake build failed patient=%s error=%s", patient_id, type(exc).__name__)
        words = str(state.get("answers", {}).get("complaint", ""))[:2000]
        return IntakeResult(patient_id=str(patient_id), chief_complaint="unspecified", duration="unspecified", symptoms=[],
                            raw_transcript=words, input_confidence="low", language=state.get("language", "en"),
                            safety_screen=list(state.get("answers", {}).get("safety_screen") or []))


def run_triage_and_summary(intake: IntakeResult, client=None) -> tuple[TriageDecision, object]:
    decision = triage(intake, client=client)
    try:
        summary = generate_summary(intake, decision)
    except Exception:
        summary = template_summary(intake, decision)
    return decision, summary


def run_pipeline(intake: IntakeResult, language: str = "en", client=None) -> tuple[TriageDecision, object, PatientAdvice]:
    """Single unified pipeline: intake -> triage -> summary -> advice."""
    decision, summary = run_triage_and_summary(intake, client=client)
    advice = make_advice(decision, language)
    return decision, summary, advice


def submit_scenario(db: Session, user: User, scenario_name: str, hold_id: int | None = None) -> dict:
    from pathlib import Path
    import json
    mock_dir = Path(__file__).resolve().parents[2] / "mock-data"
    path = mock_dir / scenario_name
    if not path.is_file():
        raise HTTPException(404, f"Scenario {scenario_name} not found")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    intake = IntakeResult.model_validate(data["stageB"]["mock_input"])
    intake.patient_id = str(user.id)
    decision, summary, advice = run_pipeline(intake, language=intake.language)
    rec = store.save_intake(db, user.id, intake)
    store.save_decision(db, rec.id, decision)
    store.save_summary(db, rec.id, summary)
    advice.intake_id = rec.id
    outcome = advice.outcome
    if hold_id is not None:
        hold = db.get(BookingHold, hold_id)
        if hold and hold.patient_id == user.id and outcome != "wait_in_queue" and not hold.finalized:
            hold.released = True
            db.add(hold)
    if outcome == OUTCOME_EMERGENCY:
        log_action(db, user, "emergency_advice", user.id, None, None, None, commit=False)
    db.commit()
    return {
        "advice": advice.model_dump(),
        "intake_id": rec.id,
        "decision": decision.model_dump(),
        "summary": summary.model_dump(),
    }


def submit(db: Session, user: User, row: IntakeSessionRow, hold_id: int | None = None) -> dict:
    state = flow.loads(row.state_json)
    if not state["done"]:
        raise HTTPException(409, "Please answer the remaining questions first")
    if row.intake_id and state["mode"] != "recheck":
        intake_id = row.intake_id
        decision = store.latest_decision(db, intake_id)
        lang = state["language"]
        return {"advice": make_advice(decision, lang, intake_id).model_dump(), "intake_id": intake_id, "already_submitted": True}
    if state["mode"] == "recheck":
        return submit_recheck(db, user, row, state)

    intake = _safe_build(state, row.patient_id)
    try:
        decision, summary = run_triage_and_summary(intake)
    except Exception:
        decision = failsafe_decision(str(row.patient_id), "pipeline_error")
        summary = template_summary(intake, decision)
    rec = store.save_intake(db, row.patient_id, intake, state.get("appointment_id"))
    store.save_decision(db, rec.id, decision)
    store.save_summary(db, rec.id, summary)
    row.intake_id = rec.id
    db.add(row)
    outcome = outcome_for(decision)

    if hold_id is not None:
        hold = db.get(BookingHold, hold_id)
        if hold and hold.patient_id == row.patient_id and outcome != "wait_in_queue" and not hold.finalized:
            hold.released = True  # concerning / emergency never books the original session
            db.add(hold)
    if outcome == OUTCOME_EMERGENCY:
        log_action(db, user, "emergency_advice", row.patient_id, None, None, None, commit=False)

    if state["mode"] == "assisted" and state.get("appointment_id"):
        _link_assisted(db, user, state["appointment_id"], rec.id, decision)
    db.commit()
    p = db.get(Patient, row.patient_id)
    lang = state["language"] if state["mode"] != "assisted" else (p.language if p else "en")
    advice = make_advice(decision, lang, rec.id)
    logger.info("pipeline intake=%s outcome=%s", rec.id, outcome)
    out = {"advice": advice.model_dump(), "intake_id": rec.id}
    if user.role == "nurse":
        out["decision"] = decision.model_dump()
        out["summary"] = summary.model_dump()
    return out


def _link_assisted(db: Session, nurse: User, appointment_id: int, intake_id: int, decision: TriageDecision) -> None:
    from app.queue import service as queue
    appt = db.get(Appointment, appointment_id)
    if appt is None:
        return
    appt.intake_id = intake_id
    db.add(appt)
    e = queue.entry_for_appointment(db, appt.id)
    if e and decision.flag_for_nurse:
        queue.set_flag(db, e, "ai", "Flagged by assisted intake (AI-assisted)" if decision.decided_by != "rule" else "Fixed safety rule")
    log_action(db, nurse, "assisted_intake", appt.patient_id, None, decision.priority, None, hospital_id=appt.hospital_id, commit=False)


def submit_recheck(db: Session, user: User, row: IntakeSessionRow, state: dict) -> dict:
    from app.queue import service as queue
    appt = db.get(Appointment, state["appointment_id"])
    prev = store.latest_decision(db, appt.intake_id)
    base_row_intake = store.load_intake(db, appt.intake_id)
    state["base_intake"] = base_row_intake.model_dump() if base_row_intake else state.get("base_intake")
    intake = _safe_build(state, appt.patient_id)
    if prev is None:
        prev = failsafe_decision(str(appt.patient_id), "no_previous_decision")
    new, raised, reasons = reclassify(intake, prev)
    new.audit_notes = list(dict.fromkeys(new.audit_notes + ["recheck_addendum"]))
    from app.models import IntakeRecord
    rec = db.get(IntakeRecord, appt.intake_id)
    store.update_intake(db, rec, intake)
    store.save_decision(db, rec.id, new)
    store.save_summary(db, rec.id, template_summary(intake, new))
    row.intake_id = rec.id
    db.add(row)
    e = queue.entry_for_appointment(db, appt.id)
    if e and (raised or new.flag_for_nurse):
        queue.set_flag(db, e, "ai" if raised else (e.flag_source or "nurse"),
                       ("Priority raised by re-check: " + "; ".join(reasons)) if raised else (e.flag_reason or "Re-check completed"))
    log_action(db, user, "recheck_completed", appt.patient_id, prev.priority, new.priority, "; ".join(reasons) or None,
               hospital_id=appt.hospital_id, commit=False)
    db.commit()
    return {"decision": new.model_dump(), "priority_raised": raised, "raise_reasons": reasons, "intake_id": rec.id}


def skip_intake(db: Session, user: User, hold_id: int) -> dict:
    """
    Patient opts out of automated questions before booking (ICMR-aligned).
    The booking goes ahead marked 'not pre-screened' and flagged for nurse check-in.
    """
    from app.booking import service as booking_svc
    from app.common import timeutil

    hold = booking_svc.get_own_hold(db, user, hold_id)
    if hold.finalized:
        raise HTTPException(409, "This hold was already used")
    if hold.released:
        raise HTTPException(410, "This hold was released. Please choose a session again.")
    if hold.held_until <= timeutil.now():
        hold.released = True
        db.add(hold)
        db.commit()
        raise HTTPException(410, "Your hold expired. Please choose a session again.")

    intake = IntakeResult(
        patient_id=str(user.id),
        chief_complaint="Not pre-screened (patient opted to speak to staff)",
        duration="unspecified",
        symptoms=[],
        raw_transcript="Patient chose to skip automated questions and be evaluated directly by staff.",
        input_confidence="unscreened",
        language="en",
        safety_screen=[],
    )
    decision = TriageDecision(
        patient_id=str(user.id),
        priority="routine",
        decided_by="human",
        confidence="medium",
        escalation_required=False,
        flag_for_nurse=True,
        priority_rationale="Patient skipped automated intake questions; nurse check-in required before consultation.",
        timestamp=timeutil.now().isoformat(),
        audit_notes=["not_pre_screened"],
        suggested_department="General Medicine",
    )
    summary = template_summary(intake, decision)

    rec = store.save_intake(db, user.id, intake)
    store.save_decision(db, rec.id, decision)
    store.save_summary(db, rec.id, summary)

    # Finalize hold
    hold.finalized = True
    db.add(hold)
    s = db.get(ClinicSession, hold.session_id)
    appt = booking_svc._issue(db, user, s, rec.id, "booked", decision)

    # Update queue entry with flag for nurse
    from app.queue import service as queue
    e = queue.entry_for_appointment(db, appt.id)
    if e:
        queue.set_flag(db, e, "nurse", "Not pre-screened (nurse check-in required)")

    log_action(db, user, "skip_intake_booking", user.id, None, str(appt.id), "Patient opted to speak to staff", hospital_id=appt.hospital_id, commit=False)
    db.commit()
    db.refresh(appt)

    advice = make_advice(decision, "en", rec.id)
    return {
        "advice": advice.model_dump(),
        "intake_id": rec.id,
        "appointment": booking_svc.appointment_view(db, appt),
        "not_pre_screened": True,
    }

