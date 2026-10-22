"""
Tests for ABDM Mock Gateway, Consent Lifecycle, Read Enforcement,
Crypto Transfer, and Scan & Share (Simulation).
"""

from datetime import date, datetime, timedelta, timezone
import json
import pytest
from sqlmodel import Session, select

from app.abdm_mock import crypto
from app.abdm_mock.gateway import MockGateway, get_gateway
from app.abdm_mock.router import SYNTHETIC_ABHA_REGEX
from app.ehr import fhir_mapper
from app.ehr.adapter import EncounterRecord, PrescriptionItem
from app.models import (
    Appointment,
    AuditLog,
    ConsentRequest,
    Doctor,
    Hospital,
    NurseAssignment,
    Patient,
    User,
)


def test_synthetic_abha_regex():
    assert re_match := bool(__import__("re").match(SYNTHETIC_ABHA_REGEX, "anitha.kumar@abdm"))
    assert bool(__import__("re").match(SYNTHETIC_ABHA_REGEX, "patient1@demo"))
    assert bool(__import__("re").match(SYNTHETIC_ABHA_REGEX, "john_doe@sbx"))
    # Rejects real or non-simulation ABHA addresses
    assert not bool(__import__("re").match(SYNTHETIC_ABHA_REGEX, "14-digit-abha-number"))
    assert not bool(__import__("re").match(SYNTHETIC_ABHA_REGEX, "user@gmail.com"))
    assert not bool(__import__("re").match(SYNTHETIC_ABHA_REGEX, "user@realabha"))


def test_crypto_bundle_transfer_roundtrip():
    """
    Simulated ECDH key agreement + AES-256-GCM + ECDSA signature roundtrip.
    """
    bundle = {
        "resourceType": "Bundle",
        "type": "document",
        "id": "bundle-demo-1",
        "entry": [{"resource": {"resourceType": "Composition", "title": "OP Consult Note"}}],
    }
    sender_doc_id = 101
    recipient_doc_id = 202

    envelope = crypto.encrypt_and_sign_bundle(
        bundle_dict=bundle,
        sender_doctor_id=sender_doc_id,
        recipient_doctor_id=recipient_doc_id,
    )
    assert envelope["protocol"] == "ABDM-Simulated-ECDH-AES-GCM-v1"
    assert envelope["sender_doctor_id"] == sender_doc_id
    assert envelope["recipient_doctor_id"] == recipient_doc_id
    assert "ciphertext_b64" in envelope
    assert "signature_b64" in envelope

    # Decrypt and verify with recipient
    decrypted = crypto.decrypt_and_verify_bundle(envelope, recipient_doctor_id=recipient_doc_id)
    assert decrypted["resourceType"] == "Bundle"
    assert decrypted["id"] == "bundle-demo-1"


def test_crypto_signature_tamper_fails():
    """Tampering with the ciphertext or signature must fail verification."""
    bundle = {"resourceType": "Bundle", "id": "test"}
    envelope = crypto.encrypt_and_sign_bundle(bundle, 1, 2)
    # Corrupt signature
    envelope["signature_b64"] = "AAAA" + envelope["signature_b64"][4:]
    with pytest.raises(ValueError, match="failed"):
        crypto.decrypt_and_verify_bundle(envelope, recipient_doctor_id=2)


def test_consent_lifecycle_and_expiry_enforcement(db_session: Session):
    """
    Test request -> grant -> check -> revoke -> expire.
    """
    gateway = MockGateway()

    # Create test entities
    h = Hospital(name="ABDM Test Hospital", address="Addr", area="Area")
    db_session.add(h)
    db_session.flush()

    u_pat = User(email="pat_abdm@demo.test", password_hash="x", role="patient", full_name="Pat ABDM")
    u_doc = User(email="doc_abdm@demo.test", password_hash="x", role="doctor", full_name="Dr ABDM")
    db_session.add(u_pat)
    db_session.add(u_doc)
    db_session.flush()

    pat = Patient(user_id=u_pat.id, abha_address="pat.abdm@abdm", language="en")
    doc = Doctor(user_id=u_doc.id, hospital_id=h.id, name="Dr ABDM", specialty="General")
    db_session.add(pat)
    db_session.add(doc)
    db_session.commit()

    # 1. Doctor requests consent
    req = gateway.create_consent_request(
        db=db_session,
        doctor_id=doc.id,
        hospital_id=h.id,
        patient_id=u_pat.id,
        purpose="Care and treatment",
        hi_types=["OPConsultNote", "Prescription"],
        date_from=date(2026, 1, 1),
        date_to=date(2026, 12, 31),
    )
    assert req.status == "REQUESTED"
    assert req.patient_id == u_pat.id
    assert req.doctor_id == doc.id

    # Check validity while pending -> False
    valid, reason, _ = gateway.check_consent_validity(db_session, req.id, doc.id, u_pat.id)
    assert not valid
    assert "REQUESTED" in reason

    # 2. Patient denies consent
    req_denied = gateway.create_consent_request(
        db=db_session,
        doctor_id=doc.id,
        hospital_id=h.id,
        patient_id=u_pat.id,
        purpose="Second opinion",
        hi_types=["OPConsultNote"],
        date_from=date(2026, 1, 1),
        date_to=date(2026, 12, 31),
    )
    req_denied = gateway.deny_consent_request(db_session, req_denied.id, u_pat.id)
    assert req_denied.status == "DENIED"
    valid, reason, _ = gateway.check_consent_validity(db_session, req_denied.id, doc.id, u_pat.id)
    assert not valid
    assert "DENIED" in reason

    # 3. Patient grants consent on first request for 24h
    granted = gateway.grant_consent_request(
        db=db_session,
        consent_id=req.id,
        patient_id=u_pat.id,
        duration_hours=24,
        approved_hi_types=["OPConsultNote"],  # excluded prescription
    )
    assert granted.status == "GRANTED"
    assert granted.expires_at is not None
    assert json.loads(granted.hi_types_json) == ["OPConsultNote"]

    # Now valid for requesting doctor
    valid, reason, _ = gateway.check_consent_validity(db_session, granted.id, doc.id, u_pat.id)
    assert valid

    # Refused for wrong doctor
    valid_wrong, reason_wrong, _ = gateway.check_consent_validity(db_session, granted.id, 9999, u_pat.id)
    assert not valid_wrong
    assert "Requester doctor does not match" in reason_wrong

    # 4. Patient revokes consent
    revoked = gateway.revoke_consent_request(db_session, granted.id, u_pat.id)
    assert revoked.status == "REVOKED"
    valid_rev, reason_rev, _ = gateway.check_consent_validity(db_session, granted.id, doc.id, u_pat.id)
    assert not valid_rev
    assert "REVOKED" in reason_rev

    # 5. Dynamic expiry on read
    req_expired = gateway.create_consent_request(
        db=db_session,
        doctor_id=doc.id,
        hospital_id=h.id,
        patient_id=u_pat.id,
        purpose="Followup",
        hi_types=["OPConsultNote"],
        date_from=date(2026, 1, 1),
        date_to=date(2026, 12, 31),
    )
    # Grant with expiry in the past
    req_expired.status = "GRANTED"
    req_expired.expires_at = datetime.now(timezone.utc) - timedelta(hours=2)
    db_session.add(req_expired)
    db_session.commit()

    valid_exp, reason_exp, updated = gateway.check_consent_validity(db_session, req_expired.id, doc.id, u_pat.id)
    assert not valid_exp
    assert "expired" in reason_exp
    assert updated.status == "EXPIRED"


def test_fhir_mapper_document_bundles():
    """Verify ehr/fhir_mapper generates valid R4 Document Bundle with Composition."""
    enc = EncounterRecord(
        id=42,
        patient_id=1,
        doctor_id=10,
        date=date(2026, 2, 1),
        diagnosis_text="Type 2 Diabetes Mellitus",
        diagnosis_code="E11.9",
        clinical_notes="Diet modification advised.",
        doctor_name="Dr. Rao",
        specialty="Endocrinology",
        hospital_name="Apex Care",
        prescriptions=[
            PrescriptionItem(drug="Metformin", dose="500 mg", frequency="BD", duration="30 days", instructions="After meals")
        ],
    )

    # Document bundle with prescriptions
    bundle = fhir_mapper.op_consult_note_document_bundle(enc, diagnoses_only=False)
    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "document"
    assert len(bundle["entry"]) >= 2
    comp = bundle["entry"][0]["resource"]
    assert comp["resourceType"] == "Composition"
    assert comp["status"] == "final"
    assert "OPConsultNote" in str(comp["type"])

    # Document bundle diagnoses only (prescription minimisation)
    bundle_min = fhir_mapper.op_consult_note_document_bundle(enc, diagnoses_only=True)
    assert bundle_min["resourceType"] == "Bundle"
    entries = [e["resource"]["resourceType"] for e in bundle_min["entry"]]
    assert "MedicationRequest" not in entries
