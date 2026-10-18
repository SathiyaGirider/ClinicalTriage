"""Adaptive intake session API used by the patient app (and by nurse assisted mode)."""

from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth.deps import get_current_user, require_patient
from app.db import get_session
from app.intake import session as flow
from app.models import IntakeSessionRow, Patient, User
from app.pipeline.service import load_session

router = APIRouter(prefix="/intake/session", tags=["Intake session"])


class StartRequest(BaseModel):
    mode: Literal["booking", "symptom_first"] = "booking"
    language: Optional[Literal["en", "ta"]] = None


class AnswerRequest(BaseModel):
    key: str = Field(min_length=1, max_length=40)
    answer: Any


def start_for_patient(db: Session, creator: User, patient: Patient, mode: str, language: str | None,
                      appointment_id: int | None = None, base_intake: dict | None = None, extra: dict | None = None) -> dict:
    state = flow.new_state(mode, language or patient.language, flow.parse_age(patient.dob_or_age), [], base_intake)
    if appointment_id:
        state["appointment_id"] = appointment_id
    state.update(extra or {})
    row = IntakeSessionRow(id=state["id"], patient_id=patient.user_id, created_by=creator.id, mode=mode, state_json=flow.dumps(state))
    db.add(row)
    db.commit()
    return flow.public_view(state)


@router.post("/start")
def start(req: StartRequest, user: User = Depends(require_patient), db: Session = Depends(get_session)):
    p = db.get(Patient, user.id)
    if p is None:
        raise HTTPException(409, "Patient profile missing")
    return start_for_patient(db, user, p, req.mode, req.language)


@router.post("/{session_id}/answer")
def answer(session_id: str, req: AnswerRequest, user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    row = load_session(db, session_id, user)
    if row.intake_id and row.mode != "recheck":
        raise HTTPException(409, "This intake was already submitted")
    state = flow.loads(row.state_json)
    try:
        state = flow.answer(state, req.key, req.answer)
    except flow.IntakeFlowError as exc:
        raise HTTPException(422, str(exc))
    row.state_json = flow.dumps(state)
    db.add(row)
    db.commit()
    return flow.public_view(state)


@router.get("/{session_id}")
def get_state(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    row = load_session(db, session_id, user)
    return flow.public_view(flow.loads(row.state_json))


@router.get("/{session_id}/result")
def result(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    """Confirm-screen preview: what we understood, in the patient's own words. No triage output."""
    row = load_session(db, session_id, user)
    state = flow.loads(row.state_json)
    if not state["done"]:
        raise HTTPException(409, "Please answer the remaining questions first")
    intake = flow.build_intake_result(state, str(row.patient_id), run_extractor=False)
    return {"session": flow.public_view(state), "understood": flow.understood(state, intake)}
