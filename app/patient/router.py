"""Patient self-service: records (as written by the doctor), consent, access log, profile."""

from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.audit import log_action
from app.auth.deps import require_patient
from app.db import get_session
from app.ehr.adapter import get_adapter
from app.ehr.history_policy import view_for_patient
from app.models import AuditLog, Doctor, Hospital, Patient, User

router = APIRouter(prefix="/me", tags=["Patient (me)"])

SCOPE_TEXT = {
    "history_own_full": "your visit records with them",
    "history_own_full+shared_diagnoses": "your diagnosis history (shared with your consent)",
    "fhir_patient": "your basic details (data-exchange view)",
    "fhir_encounter": "your visit records (data-exchange view)",
    "fhir_medication_request": "prescriptions they wrote (data-exchange view)",
}


@router.get("/records")
def records(user: User = Depends(require_patient), db: Session = Depends(get_session)):
    return {"visits": view_for_patient(get_adapter(db).get_encounters(user.id)), "footer": "Follow your doctor's instructions."}


@router.get("/prescriptions")
def prescriptions(user: User = Depends(require_patient), db: Session = Depends(get_session)):
    return get_adapter(db).list_prescriptions(user.id)


class ConsentRequest(BaseModel):
    share_history_consent: bool


@router.put("/consent")
def consent(req: ConsentRequest, user: User = Depends(require_patient), db: Session = Depends(get_session)):
    p = db.get(Patient, user.id)
    before = p.share_history_consent
    p.share_history_consent = req.share_history_consent
    db.add(p)
    log_action(db, user, "consent_change", user.id, str(before), str(req.share_history_consent), None, commit=False)
    db.commit()
    return {"share_history_consent": p.share_history_consent,
            "explanation": "Other doctors can see diagnosis history only. They never see your prescriptions or notes."}


@router.get("/access-log")
def access_log(user: User = Depends(require_patient), db: Session = Depends(get_session)):
    out = []
    for r in db.exec(select(AuditLog).where(AuditLog.patient_id == user.id).order_by(AuditLog.id.desc()).limit(200)).all():
        viewer = db.get(User, r.viewer_user_id)
        doc = db.exec(select(Doctor).where(Doctor.user_id == r.viewer_user_id)).first()
        h = db.get(Hospital, doc.hospital_id if doc else (viewer.hospital_id if viewer else None) or 0)
        out.append({"viewer": doc.name if doc else (viewer.full_name if viewer else "staff"), "role": viewer.role if viewer else "",
                    "hospital": h.name if h else "", "scope": r.scope, "what": SCOPE_TEXT.get(r.scope, r.scope), "ts": r.ts.isoformat()})
    return out


class ProfileRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    age: Optional[int] = Field(default=None, ge=0, le=125)
    dob: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    language: Optional[Literal["en", "ta"]] = None
    area: Optional[str] = Field(default=None, max_length=80)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)

    model_config = {"extra": "forbid"}


@router.put("/profile")
def profile(req: ProfileRequest, user: User = Depends(require_patient), db: Session = Depends(get_session)):
    p = db.get(Patient, user.id)
    if req.full_name:
        user.full_name = req.full_name.strip()
        db.add(user)
    if req.dob or req.age is not None:
        p.dob_or_age = req.dob or str(req.age)
    if req.language:
        p.language = req.language
    if req.area is not None:
        p.area = req.area
    if req.lat is not None and req.lon is not None:
        p.lat, p.lon = req.lat, req.lon
    db.add(p)
    db.commit()
    return {"full_name": user.full_name, "age": p.dob_or_age, "language": p.language, "area": p.area}
