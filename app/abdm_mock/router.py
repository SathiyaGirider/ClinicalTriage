"""
ABDM Simulation API Router.
SIMULATION ONLY. Not connected to ABDM. Not certified.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.abdm_mock import crypto
from app.abdm_mock.gateway import SIMULATION_DISCLAIMER, get_gateway
from app.audit import log_action, log_view
from app.auth.deps import doctor_profile, require_doctor, require_nurse, require_patient, require_staff
from app.common import timeutil
from app.db import get_session
from app.ehr import fhir_mapper
from app.ehr.adapter import get_adapter
from app.models import Appointment, ConsentRequest, ConsentStatusHistory, Doctor, Hospital, Patient, User

router = APIRouter(prefix="/abdm", tags=["ABDM Simulation"])

SYNTHETIC_ABHA_REGEX = r"^[a-zA-Z0-9._-]+@(abdm|sbx|demo)$"


# -----------------------------------------------------------------------------
# Pydantic Request Schemas
# -----------------------------------------------------------------------------

class CreateConsentRequestIn(BaseModel):
    patient_id: int
    purpose: str = Field(default="Care and treatment", max_length=120)
    hi_types: list[str] = Field(default_factory=lambda: ["OPConsultNote", "Prescription"])
    date_from: dt.date
    date_to: dt.date
    duration_hours: Literal[24, 168, 720] = 24  # 24 hours, 7 days, 30 days


class ApproveConsentIn(BaseModel):
    duration_hours: Literal[24, 168, 720] = 24
    hi_types: Optional[list[str]] = None


class DenyConsentIn(BaseModel):
    reason: Optional[str] = Field(default="Denied by patient", max_length=300)


class RevokeConsentIn(BaseModel):
    reason: Optional[str] = Field(default="Revoked by patient", max_length=300)


class ScanAndShareIn(BaseModel):
    abha_address: str = Field(min_length=3, max_length=100)
    full_name: str = Field(min_length=1, max_length=120)
    age: int = Field(ge=0, le=125)
    gender: Optional[str] = Field(default="O", max_length=10)


# -----------------------------------------------------------------------------
# Doctor Flow: Request Outside Records
# -----------------------------------------------------------------------------

@router.post("/consent/request", status_code=201)
def request_consent(
    req: CreateConsentRequestIn,
    user: User = Depends(require_doctor),
    db: Session = Depends(get_session),
):
    """Doctor requests outside medical history access from patient (ABDM simulation)."""
    doc = doctor_profile(db, user)
    patient = db.get(Patient, req.patient_id)
    if not patient:
        raise HTTPException(404, "Patient not found")

    gateway = get_gateway()
    consent = gateway.request_consent(
        db=db,
        doctor=doc,
        patient_id=req.patient_id,
        purpose=req.purpose,
        hi_types=req.hi_types,
        date_from=req.date_from,
        date_to=req.date_to,
        duration_hours=req.duration_hours,
    )
    return {
        "disclaimer": SIMULATION_DISCLAIMER,
        "consent_request_id": consent.id,
        "status": consent.status,
        "purpose": consent.purpose,
        "created_at": consent.created_at.isoformat(),
    }


@router.get("/consent/doctor-requests")
def doctor_consent_requests(
    patient_id: Optional[int] = None,
    user: User = Depends(require_doctor),
    db: Session = Depends(get_session),
):
    """Doctor views status of consent requests they initiated."""
    doc = doctor_profile(db, user)
    q = select(ConsentRequest).where(ConsentRequest.doctor_id == doc.id)
    if patient_id:
        q = q.where(ConsentRequest.patient_id == patient_id)
    rows = db.exec(q.order_by(ConsentRequest.id.desc())).all()

    # Enforce expiry on check
    gateway = get_gateway()
    out = []
    for r in rows:
        valid, reason, updated = gateway.check_consent_validity(db, r.id, doc.id, r.patient_id)
        current = updated or r
        pat_u = db.get(User, current.patient_id)
        out.append({
            "id": current.id,
            "patient_id": current.patient_id,
            "patient_name": pat_u.full_name if pat_u else f"Patient {current.patient_id}",
            "status": current.status,
            "purpose": current.purpose,
            "hi_types": json.loads(current.hi_types_json),
            "date_from": current.date_from.isoformat(),
            "date_to": current.date_to.isoformat(),
            "expires_at": current.expires_at.isoformat() if current.expires_at else None,
            "is_valid": valid,
            "status_reason": reason,
        })
    return {"disclaimer": SIMULATION_DISCLAIMER, "requests": out}


# -----------------------------------------------------------------------------
# Patient Flow: Privacy Inbox & Approvals
# -----------------------------------------------------------------------------

@router.get("/consent/patient/inbox")
def patient_consent_inbox(
    user: User = Depends(require_patient),
    db: Session = Depends(get_session),
):
    """Patient views pending requests, active consents, and past consent history."""
    gateway = get_gateway()
    rows = db.exec(
        select(ConsentRequest)
        .where(ConsentRequest.patient_id == user.id)
        .order_by(ConsentRequest.id.desc())
    ).all()

    pending, active, past = [], [], []
    for r in rows:
        # Check validity/expiry
        valid, _, updated = gateway.check_consent_validity(db, r.id, r.doctor_id, r.patient_id)
        curr = updated or r
        doc = db.get(Doctor, curr.doctor_id)
        h = db.get(Hospital, curr.hospital_id)
        item = {
            "id": curr.id,
            "doctor_name": doc.name if doc else "Doctor",
            "specialty": doc.specialty if doc else "",
            "hospital_name": h.name if h else "",
            "purpose": curr.purpose,
            "hi_types": json.loads(curr.hi_types_json),
            "date_from": curr.date_from.isoformat(),
            "date_to": curr.date_to.isoformat(),
            "status": curr.status,
            "expires_at": curr.expires_at.isoformat() if curr.expires_at else None,
            "created_at": curr.created_at.isoformat(),
        }
        if curr.status == "REQUESTED":
            pending.append(item)
        elif curr.status == "GRANTED" and valid:
            active.append(item)
        else:
            past.append(item)

    patient_row = db.get(Patient, user.id)
    return {
        "disclaimer": SIMULATION_DISCLAIMER,
        "abha_address": patient_row.abha_address if patient_row else None,
        "pending": pending,
        "active": active,
        "past": past,
    }


@router.post("/consent/{request_id}/approve")
def approve_consent(
    request_id: int,
    req: ApproveConsentIn,
    user: User = Depends(require_patient),
    db: Session = Depends(get_session),
):
    gateway = get_gateway()
    try:
        updated = gateway.grant_consent(
            db=db,
            patient_user=user,
            consent_request_id=request_id,
            duration_hours=req.duration_hours,
            approved_hi_types=req.hi_types,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {
        "disclaimer": SIMULATION_DISCLAIMER,
        "id": updated.id,
        "status": updated.status,
        "expires_at": updated.expires_at.isoformat() if updated.expires_at else None,
    }


@router.post("/consent/{request_id}/deny")
def deny_consent(
    request_id: int,
    req: DenyConsentIn,
    user: User = Depends(require_patient),
    db: Session = Depends(get_session),
):
    gateway = get_gateway()
    try:
        updated = gateway.deny_consent(
            db=db,
            patient_user=user,
            consent_request_id=request_id,
            reason=req.reason,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {
        "disclaimer": SIMULATION_DISCLAIMER,
        "id": updated.id,
        "status": updated.status,
    }


@router.post("/consent/{request_id}/revoke")
def revoke_consent(
    request_id: int,
    req: RevokeConsentIn,
    user: User = Depends(require_patient),
    db: Session = Depends(get_session),
):
    gateway = get_gateway()
    try:
        updated = gateway.revoke_consent(
            db=db,
            patient_user=user,
            consent_request_id=request_id,
            reason=req.reason,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {
        "disclaimer": SIMULATION_DISCLAIMER,
        "id": updated.id,
        "status": updated.status,
    }


# -----------------------------------------------------------------------------
# Provider Enforcement & Secure Transfer: Fetch Consented Records
# -----------------------------------------------------------------------------

@router.get("/records/patient/{patient_id}")
def fetch_consented_records(
    patient_id: int,
    consent_request_id: int = Query(...),
    user: User = Depends(require_doctor),
    db: Session = Depends(get_session),
):
    """
    HIP Provider-side enforcement & HIU receiver fetch (ABDM simulation).
    Enforces that consent is GRANTED, active, and within date and record scope.
    Simulates ECDH+AES-GCM encryption from provider facility to requester.
    """
    doc = doctor_profile(db, user)
    gateway = get_gateway()

    is_valid, reason, consent = gateway.check_consent_validity(
        db, consent_request_id, doc.id, patient_id
    )

    if not is_valid or not consent:
        log_action(
            db,
            user,
            "abdm_record_access_refused",
            patient_id,
            consent.status if consent else "NONE",
            "REFUSED",
            reason,
            hospital_id=doc.hospital_id,
            commit=True,
        )
        raise HTTPException(403, f"Access refused: {reason}")

    # Scope filtering by hi_types and date range
    approved_types = set(json.loads(consent.hi_types_json))
    adapter = get_adapter(db)
    all_encounters = adapter.get_encounters(patient_id)

    matched_records = []
    for e in all_encounters:
        # Provider filters by date range
        if not (consent.date_from <= e.date <= consent.date_to):
            continue

        record_entry = {
            "encounter_id": e.id,
            "date": e.date.isoformat(),
            "doctor_name": e.doctor_name,
            "specialty": e.specialty,
            "hospital_name": e.hospital_name,
            "diagnosis_text": e.diagnosis_text,
            "diagnosis_code": e.diagnosis_code,
        }

        # Handle Prescriptions if approved
        if "Prescription" in approved_types:
            record_entry["prescriptions"] = [p.model_dump() for p in e.prescriptions]
        else:
            record_entry["prescriptions"] = []

        # Create FHIR document bundle
        diagnoses_only = "Prescription" not in approved_types
        bundle = fhir_mapper.op_consult_note_document_bundle(e, diagnoses_only=diagnoses_only)

        # Simulate secure cryptographic transfer from author doctor to requester doctor
        encrypted_envelope = crypto.encrypt_and_sign_bundle(
            bundle_dict=bundle,
            sender_doctor_id=e.doctor_id,
            recipient_doctor_id=doc.id,
        )

        matched_records.append({
            "record": record_entry,
            "fhir_document_bundle": bundle,
            "simulated_transfer": encrypted_envelope,
        })

    # Audit log the successful access
    log_view(db, user, patient_id, f"abdm_consent_{consent.id}_read")

    return {
        "disclaimer": SIMULATION_DISCLAIMER,
        "consent_id": consent.id,
        "approved_types": list(approved_types),
        "expires_at": consent.expires_at.isoformat() if consent.expires_at else None,
        "records": matched_records,
    }


# -----------------------------------------------------------------------------
# Simulated Scan & Share (Profile Registration / Check-In)
# -----------------------------------------------------------------------------

@router.post("/scan-and-share")
def scan_and_share(
    req: ScanAndShareIn,
    nurse: User = Depends(require_nurse),
    db: Session = Depends(get_session),
):
    """
    Simulated Scan and Share OPD check-in.
    Shares ONLY profile fields (name, age, gender, synthetic ABHA address).
    NEVER shares health records.
    Finds or registers the patient and confirms arrival or creates a walk-in token.
    """
    if not re.match(SYNTHETIC_ABHA_REGEX, req.abha_address):
        raise HTTPException(
            422,
            "Invalid synthetic ABHA address format. Must be synthetic e.g. name@abdm or name@demo",
        )

    # Scoped to nurse's assigned doctor
    from app.queue import service as q
    doc = q.get_nurse_assigned_doctor(db, nurse)

    # Check if patient with this ABHA exists, else find by name/register walk-in
    patient_row = db.exec(
        select(Patient).where(Patient.abha_address == req.abha_address)
    ).first()

    if patient_row:
        user = db.get(User, patient_row.user_id)
    else:
        # Register new walk-in patient with synthetic ABHA profile
        from app.auth.security import UNUSABLE_PASSWORD
        from app.common.ids import new_id
        user = User(
            email=f"abha-{new_id()}@walkin.invalid",
            password_hash=UNUSABLE_PASSWORD,
            role="patient",
            full_name=req.full_name.strip(),
        )
        db.add(user)
        db.flush()
        patient_row = Patient(
            user_id=user.id,
            dob_or_age=str(req.age),
            language="en",
            is_walk_in=True,
            abha_address=req.abha_address,
        )
        db.add(patient_row)
        db.commit()

    # Find today's appointment if exists, else create walk-in
    today = timeutil.today()
    appt = db.exec(
        select(Appointment).where(
            Appointment.patient_id == user.id,
            Appointment.doctor_id == doc.id,
            Appointment.date == today,
            Appointment.status != "cancelled",
        )
    ).first()

    if not appt:
        appt = Appointment(
            patient_id=user.id,
            doctor_id=doc.id,
            hospital_id=doc.hospital_id,
            date=today,
            type="walk_in",
            status="expected_today",
        )
        db.add(appt)
        db.flush()
        e = q.create_entry(db, appt, None, False, None)
        log_action(
            db,
            nurse,
            "abdm_scan_and_share_walkin",
            user.id,
            req.abha_address,
            str(appt.id),
            "Registered via simulated scan and share",
            hospital_id=doc.hospital_id,
            commit=False,
        )
        db.commit()
        res = q.check_in(db, e, "none", "Scan and Share self-registration", nurse)
        return {
            "disclaimer": SIMULATION_DISCLAIMER,
            "shared_profile": {
                "name": req.full_name,
                "age": req.age,
                "gender": req.gender,
                "abha_address": req.abha_address,
            },
            "action": "walk_in_registered",
            "appointment_id": appt.id,
            **res,
        }

    # Already had a booking today -> confirm arrival
    e = q.entry_for_appointment(db, appt.id)
    if not e:
        e = q.create_entry(db, appt, None, False, None)
    res = q.check_in(db, e, "none", "Confirmed arrival via Scan and Share", nurse)
    return {
        "disclaimer": SIMULATION_DISCLAIMER,
        "shared_profile": {
            "name": req.full_name,
            "age": req.age,
            "gender": req.gender,
            "abha_address": req.abha_address,
        },
        "action": "arrival_confirmed",
        "appointment_id": appt.id,
        **res,
    }
