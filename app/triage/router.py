"""
Triage API. Staff only: patients never see priorities.

POST /triage            (kept from Person B) IntakeResult -> TriageDecision
POST /triage/classify   same, explicit name
POST /triage/reclassify vitals and/or re-check addendum on a stored intake (raise-only)
POST /triage/test-scenario  dev only: run one mock scenario through the pipeline
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth.deps import require_staff
from app.common import timeutil
from app.common.llm import FakeLLMClient
from app.common.schemas import IntakeAddendum, IntakeResult, TriageDecision
from app.common.symptom_vocab import detect_tags
from app.config import settings
from app.db import get_session
from app.models import IntakeRecord, User
from app.pipeline import store
from app.triage.rules import VitalsInput
from app.triage.service import reclassify, triage

router = APIRouter(tags=["Triage"])


@router.post("/triage", response_model=TriageDecision)
def triage_endpoint(intake_result: IntakeResult, _: User = Depends(require_staff)) -> TriageDecision:
    return triage(intake_result)


@router.post("/triage/classify", response_model=TriageDecision)
def classify(intake_result: IntakeResult, _: User = Depends(require_staff)) -> TriageDecision:
    return triage(intake_result)


class VitalsBody(BaseModel):
    bp_sys: Optional[int] = Field(default=None, ge=40, le=300)
    bp_dia: Optional[int] = Field(default=None, ge=20, le=200)
    temp_c: Optional[float] = Field(default=None, ge=30, le=45)
    spo2: Optional[int] = Field(default=None, ge=40, le=100)
    pulse: Optional[int] = Field(default=None, ge=20, le=250)


class ReclassifyRequest(BaseModel):
    intake_id: int
    vitals: Optional[VitalsBody] = None
    addendum_text: Optional[str] = Field(default=None, max_length=2000)


@router.post("/triage/reclassify")
def reclassify_endpoint(req: ReclassifyRequest, user: User = Depends(require_staff), db: Session = Depends(get_session)):
    from app.models import Appointment
    from app.queue.service import doctor_hospital
    rec = db.get(IntakeRecord, req.intake_id)
    if rec is None:
        raise HTTPException(404, "Intake not found")
    appt = db.get(Appointment, rec.appointment_id) if rec.appointment_id else None
    if appt is None or (user.role == "nurse" and doctor_hospital(db, appt.doctor_id) != user.hospital_id):
        raise HTTPException(403, "Not a patient in your hospital's queue")
    intake = store.load_intake(db, rec.id)
    prev = store.latest_decision(db, rec.id)
    if req.addendum_text:
        intake.addenda = list(intake.addenda) + [IntakeAddendum(ts=timeutil.now().isoformat(), change="worse", text=req.addendum_text,
                                                                 symptom_tags=detect_tags(req.addendum_text), source="nurse")]
        store.update_intake(db, rec, intake)
    vitals = VitalsInput(**req.vitals.model_dump()) if req.vitals else None
    new, raised, reasons = reclassify(intake, prev, vitals=vitals, use_llm=bool(req.addendum_text))
    store.save_decision(db, rec.id, new)
    db.commit()
    return {"decision": new, "priority_raised": raised, "raise_reasons": reasons}


class ScenarioRequest(BaseModel):
    scenario: str = Field(pattern=r"^scenario-0[1-8]\.json$")


@router.post("/triage/test-scenario")
def test_scenario(req: ScenarioRequest, _: User = Depends(require_staff)):
    if not settings.dev_endpoints:
        raise HTTPException(404, "Not found")
    from app.triage.cli import MOCK, load_expected
    data = json.loads((MOCK / req.scenario).read_text(encoding="utf-8-sig"))
    exp = load_expected()[req.scenario]
    intake = IntakeResult.model_validate(data["stageB"]["mock_input"])
    client = FakeLLMClient(json.dumps(exp["fake_llm"])) if exp.get("fake_llm") else FakeLLMClient(None)
    d = triage(intake, client=client)
    return {"decision": d, "expected": {k: exp[k] for k in ("priority", "decided_by")},
            "pass": d.priority == exp["priority"] and d.decided_by == exp["decided_by"]}
