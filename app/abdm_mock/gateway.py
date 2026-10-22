"""
ConsentGateway interface and MockGateway implementation for ABDM simulation.
SIMULATION ONLY. Not connected to ABDM. Not certified.
"""

from __future__ import annotations

import abc
import datetime as dt
import json
from datetime import timedelta
from typing import Optional

from sqlmodel import Session, select

from app.audit import log_action
from app.common import timeutil
from app.config import settings
from app.models import ConsentRequest, ConsentStatusHistory, Doctor, Hospital, Patient, User

SIMULATION_DISCLAIMER = "ABDM simulation. Not connected to ABDM."


class ConsentGateway(abc.ABC):
    """Interface for Consent Management in ABDM flow."""

    @abc.abstractmethod
    def request_consent(
        self,
        db: Session,
        doctor: Doctor,
        patient_id: int,
        purpose: str,
        hi_types: list[str],
        date_from: dt.date,
        date_to: dt.date,
        duration_hours: int = 24,
    ) -> ConsentRequest:
        pass

    @abc.abstractmethod
    def grant_consent(
        self,
        db: Session,
        patient_user: User,
        consent_request_id: int,
        duration_hours: int = 24,
        approved_hi_types: Optional[list[str]] = None,
    ) -> ConsentRequest:
        pass

    @abc.abstractmethod
    def deny_consent(
        self,
        db: Session,
        patient_user: User,
        consent_request_id: int,
        reason: Optional[str] = None,
    ) -> ConsentRequest:
        pass

    @abc.abstractmethod
    def revoke_consent(
        self,
        db: Session,
        patient_user: User,
        consent_request_id: int,
        reason: Optional[str] = None,
    ) -> ConsentRequest:
        pass

    @abc.abstractmethod
    def check_consent_validity(
        self,
        db: Session,
        consent_request_id: int,
        doctor_id: int,
        patient_id: int,
    ) -> tuple[bool, str, Optional[ConsentRequest]]:
        """Provider-side check enforced on every read. Returns (is_valid, reason, consent_request)."""
        pass


class RealGateway(ConsentGateway):
    """Stub for real ABDM connection. Deliberately not implemented in local demo."""

    def request_consent(self, *args, **kwargs) -> ConsentRequest:
        raise NotImplementedError("Real ABDM connection is not implemented in this prototype demo. This is a local simulation only.")

    def grant_consent(self, *args, **kwargs) -> ConsentRequest:
        raise NotImplementedError("Real ABDM connection is not implemented in this prototype demo. This is a local simulation only.")

    def deny_consent(self, *args, **kwargs) -> ConsentRequest:
        raise NotImplementedError("Real ABDM connection is not implemented in this prototype demo. This is a local simulation only.")

    def revoke_consent(self, *args, **kwargs) -> ConsentRequest:
        raise NotImplementedError("Real ABDM connection is not implemented in this prototype demo. This is a local simulation only.")

    def check_consent_validity(self, *args, **kwargs) -> tuple[bool, str, Optional[ConsentRequest]]:
        raise NotImplementedError("Real ABDM connection is not implemented in this prototype demo. This is a local simulation only.")


class MockGateway(ConsentGateway):
    """
    In-memory / SQLite ABDM Consent Manager Mock.
    Enforces expiry on every read.
    """

    def request_consent(
        self,
        db: Session,
        doctor: Doctor,
        patient_id: int,
        purpose: str,
        hi_types: list[str],
        date_from: dt.date,
        date_to: dt.date,
        duration_hours: int = 24,
    ) -> ConsentRequest:
        req = ConsentRequest(
            doctor_id=doctor.id,
            hospital_id=doctor.hospital_id,
            patient_id=patient_id,
            purpose=purpose.strip() or "Care and treatment",
            hi_types_json=json.dumps(hi_types or ["OPConsultNote", "Prescription"]),
            date_from=date_from,
            date_to=date_to,
            duration_hours=duration_hours,
            status="REQUESTED",
        )
        db.add(req)
        db.flush()

        # Append status history
        history = ConsentStatusHistory(
            consent_request_id=req.id,
            status="REQUESTED",
            actor_user_id=doctor.user_id or 0,
            actor_role="doctor",
            note=f"Consent requested by {doctor.name}",
        )
        db.add(history)

        log_action(
            db,
            db.get(User, doctor.user_id) if doctor.user_id else None,
            "abdm_consent_request_created",
            patient_id,
            None,
            str(req.id),
            req.purpose,
            hospital_id=doctor.hospital_id,
            commit=False,
        )
        db.commit()
        db.refresh(req)
        return req

    def grant_consent(
        self,
        db: Session,
        patient_user: User,
        consent_request_id: int,
        duration_hours: int = 24,
        approved_hi_types: Optional[list[str]] = None,
    ) -> ConsentRequest:
        req = db.get(ConsentRequest, consent_request_id)
        if not req or req.patient_id != patient_user.id:
            raise ValueError("Consent request not found for this patient")

        now = timeutil.now()
        req.status = "GRANTED"
        req.duration_hours = duration_hours
        req.expires_at = now + timedelta(hours=duration_hours)
        if approved_hi_types:
            req.hi_types_json = json.dumps(approved_hi_types)
        req.updated_at = now
        db.add(req)

        history = ConsentStatusHistory(
            consent_request_id=req.id,
            status="GRANTED",
            actor_user_id=patient_user.id,
            actor_role="patient",
            note=f"Granted for {duration_hours}h expiring at {req.expires_at.isoformat()}",
        )
        db.add(history)

        log_action(
            db,
            patient_user,
            "abdm_consent_granted",
            patient_user.id,
            "REQUESTED",
            "GRANTED",
            f"Expires {req.expires_at.isoformat()}",
            hospital_id=req.hospital_id,
            commit=False,
        )
        db.commit()
        db.refresh(req)
        return req

    def deny_consent(
        self,
        db: Session,
        patient_user: User,
        consent_request_id: int,
        reason: Optional[str] = None,
    ) -> ConsentRequest:
        req = db.get(ConsentRequest, consent_request_id)
        if not req or req.patient_id != patient_user.id:
            raise ValueError("Consent request not found for this patient")

        req.status = "DENIED"
        req.updated_at = timeutil.now()
        db.add(req)

        history = ConsentStatusHistory(
            consent_request_id=req.id,
            status="DENIED",
            actor_user_id=patient_user.id,
            actor_role="patient",
            note=reason or "Denied by patient",
        )
        db.add(history)

        log_action(
            db,
            patient_user,
            "abdm_consent_denied",
            patient_user.id,
            "REQUESTED",
            "DENIED",
            reason,
            hospital_id=req.hospital_id,
            commit=False,
        )
        db.commit()
        db.refresh(req)
        return req

    def revoke_consent(
        self,
        db: Session,
        patient_user: User,
        consent_request_id: int,
        reason: Optional[str] = None,
    ) -> ConsentRequest:
        req = db.get(ConsentRequest, consent_request_id)
        if not req or req.patient_id != patient_user.id:
            raise ValueError("Consent request not found for this patient")

        before = req.status
        req.status = "REVOKED"
        req.updated_at = timeutil.now()
        db.add(req)

        history = ConsentStatusHistory(
            consent_request_id=req.id,
            status="REVOKED",
            actor_user_id=patient_user.id,
            actor_role="patient",
            note=reason or "Revoked by patient",
        )
        db.add(history)

        log_action(
            db,
            patient_user,
            "abdm_consent_revoked",
            patient_user.id,
            before,
            "REVOKED",
            reason,
            hospital_id=req.hospital_id,
            commit=False,
        )
        db.commit()
        db.refresh(req)
        return req

    def check_consent_validity(
        self,
        db: Session,
        consent_request_id: int,
        doctor_id: int,
        patient_id: int,
    ) -> tuple[bool, str, Optional[ConsentRequest]]:
        req = db.get(ConsentRequest, consent_request_id)
        if not req:
            return False, "Consent request record not found", None

        # Verify requester doctor and patient match
        if req.doctor_id != doctor_id:
            return False, "Requester doctor does not match consent", req
        if req.patient_id != patient_id:
            return False, "Patient does not match consent", req

        # Check status
        if req.status == "REVOKED":
            return False, "Consent was revoked by patient", req
        if req.status == "DENIED":
            return False, "Consent was denied by patient", req
        if req.status == "REQUESTED":
            return False, "Consent is pending patient approval", req

        # Check expiry on every read
        now = timeutil.now()
        if req.expires_at and req.expires_at <= now:
            if req.status != "EXPIRED":
                req.status = "EXPIRED"
                req.updated_at = now
                db.add(req)
                db.add(
                    ConsentStatusHistory(
                        consent_request_id=req.id,
                        status="EXPIRED",
                        actor_user_id=0,
                        actor_role="system",
                        note="Automatic expiration enforced on read",
                    )
                )
                db.commit()
            return False, "Consent has expired", req

        if req.status == "GRANTED":
            return True, "Consent is active and valid", req

        return False, f"Invalid consent status: {req.status}", req


def get_gateway() -> ConsentGateway:
    if settings.abdm_mode == "mock":
        return MockGateway()
    return RealGateway()
