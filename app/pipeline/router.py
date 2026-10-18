"""POST /pipeline/submit: intake -> triage -> summary -> PatientAdvice (fail safe)."""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth.deps import get_current_user
from app.db import get_session
from app.models import User
from app.pipeline.service import load_session, submit

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


class SubmitRequest(BaseModel):
    intake_session_id: str = Field(min_length=1, max_length=40)
    hold_id: Optional[int] = None


@router.post("/submit")
def submit_endpoint(req: SubmitRequest, user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    row = load_session(db, req.intake_session_id, user)
    return submit(db, user, row, req.hold_id)
