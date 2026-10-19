"""Consultation (doctor writes the EHR record) and the read-only FHIR demo endpoints."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.audit import log_action, log_view
from app.auth.deps import doctor_profile, require_doctor
from app.common import timeutil
from app.db import get_session
from app.ehr import fhir_mapper as fhir
from app.ehr.adapter import EncounterIn, PrescriptionItem, get_adapter
from app.ehr.history_policy import AccessDenied, view_for_doctor
from app.models import Appointment, Patient, User
from app.queue import service as queue

router = APIRouter(prefix="/ehr", tags=["EHR"])


class ConsultationRequest(BaseModel):
    """Typed by the doctor only. Nothing in this form is AI-suggested or autofilled."""
    appointment_id: int
    diagnosis_text: str = Field(min_length=1, max_length=500)
    diagnosis_code: Optional[str] = Field(default=None, max_length=20)
    clinical_notes: str = Field(default="", max_length=5000)
    prescription: list[PrescriptionItem] = Field(default_factory=list, max_length=20)
    follow_up_date: Optional[date] = None


def has_relationship(db: Session, doctor_id: int, patient_id: int) -> bool:
    return db.exec(select(Appointment).where(Appointment.doctor_id == doctor_id, Appointment.patient_id == patient_id,
                                             Appointment.status != "cancelled")).first() is not None


@router.post("/consultation", status_code=201)
def consultation(req: ConsultationRequest, user: User = Depends(require_doctor), db: Session = Depends(get_session)):
    doc = doctor_profile(db, user)
    appt = db.get(Appointment, req.appointment_id)
    if appt is None or appt.doctor_id != doc.id:
        raise HTTPException(404, "Appointment not found")
    if appt.status in ("completed", "cancelled", "no_show"):
        raise HTTPException(409, f"Appointment is {appt.status}")
    adapter = get_adapter(db)
    enc = adapter.save_encounter(EncounterIn(patient_id=appt.patient_id, doctor_id=doc.id, appointment_id=appt.id, date=timeutil.today(),
                                             diagnosis_text=req.diagnosis_text.strip(), diagnosis_code=req.diagnosis_code,
                                             clinical_notes=req.clinical_notes, follow_up_date=req.follow_up_date))
    adapter.save_prescription(enc.id, req.prescription)
    appt.status = "completed"
    db.add(appt)
    e = queue.entry_for_appointment(db, appt.id)
    if e:
        now = timeutil.now()
        e.called_at = e.called_at or now
        e.status, e.done_at = "done", now
        db.add(e)
    log_action(db, user, "complete_consultation", appt.patient_id, None, str(enc.id), None, hospital_id=appt.hospital_id, commit=False)
    db.commit()
    return {"encounter_id": enc.id, "appointment_status": "completed"}


def _doctor_view(db: Session, user: User, patient_id: int, scope: str) -> dict:
    doc = doctor_profile(db, user)
    p = db.get(Patient, patient_id)
    if p is None:
        raise HTTPException(404, "Patient not found")
    try:
        view = view_for_doctor(get_adapter(db).get_encounters(patient_id), doc.id, has_relationship(db, doc.id, patient_id),
                               p.share_history_consent)
    except AccessDenied:
        raise HTTPException(403, "No appointment relationship with this patient")
    log_view(db, user, patient_id, scope)
    return view


@router.get("/fhir/Patient/{patient_id}")
def fhir_patient(patient_id: int, user: User = Depends(require_doctor), db: Session = Depends(get_session)):
    doc = doctor_profile(db, user)
    if not has_relationship(db, doc.id, patient_id):
        raise HTTPException(403, "No appointment relationship with this patient")
    u, p = db.get(User, patient_id), db.get(Patient, patient_id)
    log_view(db, user, patient_id, "fhir_patient")
    return fhir.patient_resource(u.id, u.full_name, p.language, p.dob_or_age)


@router.get("/fhir/Encounter")
def fhir_encounters(patient: int = Query(...), user: User = Depends(require_doctor), db: Session = Depends(get_session)):
    """Policy-filtered: own encounters + (with consent) other doctors' Conditions only."""
    view = _doctor_view(db, user, patient, "fhir_encounter")
    adapter = get_adapter(db)
    res = []
    for item in view["own"]:
        e = adapter.get_encounter(item["id"])
        res += [fhir.encounter_resource(e), fhir.condition_resource(e)]
    for item in view["shared"]:
        e = adapter.get_encounter(item["id"])
        cond = fhir.condition_resource(e)
        cond["meta"] = {"tag": [{"code": "shared-with-consent-diagnosis-only"}]}
        res.append(cond)
    return fhir.bundle(res)


@router.get("/fhir/MedicationRequest")
def fhir_medication_requests(patient: int = Query(...), user: User = Depends(require_doctor), db: Session = Depends(get_session)):
    """Only prescriptions from encounters this doctor authored; never other doctors' prescriptions."""
    view = _doctor_view(db, user, patient, "fhir_medication_request")
    adapter = get_adapter(db)
    res = []
    for item in view["own"]:
        res += fhir.medication_requests(adapter.get_encounter(item["id"]))
    return fhir.bundle(res)
