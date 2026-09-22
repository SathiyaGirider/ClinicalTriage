"""
FastAPI router for the Triage module.

Exposes POST /triage, which accepts an IntakeResult and returns
a TriageDecision, by calling the triage() service function.
"""

from fastapi import APIRouter

from app.triage.service import triage
from app.common.schemas import IntakeResult, TriageDecision

router = APIRouter()


@router.post("/triage", response_model=TriageDecision)
def triage_endpoint(intake_result: IntakeResult) -> TriageDecision:
    return triage(intake_result)