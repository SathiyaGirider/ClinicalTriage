"""
Who may see which parts of a patient's encounter history. Pure functions,
unit-tested in tests/test_history_policy.py.

- Patient: all own encounters (diagnosis, prescriptions, doctor, date).
- Treating doctor (authored the encounter): that encounter in FULL.
- Other doctors with an appointment relationship: ONLY if the patient's
  share_history_consent is on, and then only date, specialty, hospital and
  diagnosis text. Never prescriptions, never clinical notes.
- Doctor with no appointment relationship: no access at all.
- Nurse: no diagnosis history, no prescriptions (triage summary only).
"""

from __future__ import annotations

from app.ehr.adapter import EncounterRecord

SHARED_LABEL = "Shared with patient's consent. Diagnoses only."


class AccessDenied(Exception):
    pass


def view_for_patient(encounters: list[EncounterRecord]) -> list[dict]:
    return [{"id": e.id, "date": e.date.isoformat(), "doctor_name": e.doctor_name, "specialty": e.specialty, "hospital_name": e.hospital_name,
             "diagnosis_text": e.diagnosis_text, "follow_up_date": e.follow_up_date.isoformat() if e.follow_up_date else None,
             "prescriptions": [p.model_dump() for p in e.prescriptions]} for e in encounters]


def view_for_doctor(encounters: list[EncounterRecord], viewer_doctor_id: int, has_relationship: bool, consent: bool) -> dict:
    if not has_relationship:
        raise AccessDenied("No appointment relationship with this patient")
    own, shared = [], []
    for e in encounters:
        if e.doctor_id == viewer_doctor_id:
            own.append({"id": e.id, "date": e.date.isoformat(), "doctor_name": e.doctor_name, "specialty": e.specialty,
                        "hospital_name": e.hospital_name, "diagnosis_text": e.diagnosis_text, "diagnosis_code": e.diagnosis_code,
                        "clinical_notes": e.clinical_notes, "follow_up_date": e.follow_up_date.isoformat() if e.follow_up_date else None,
                        "prescriptions": [p.model_dump() for p in e.prescriptions], "scope": "full"})
        elif consent:
            shared.append({"id": e.id, "date": e.date.isoformat(), "specialty": e.specialty, "hospital_name": e.hospital_name,
                           "diagnosis_text": e.diagnosis_text, "scope": "shared_diagnosis_only"})
    # With consent off nothing about other doctors' encounters is returned, not even a count.
    return {"own": own, "shared": shared, "shared_label": SHARED_LABEL if shared else None, "consent": consent}


def view_for_nurse() -> None:
    raise AccessDenied("Nurses see the triage summary only")


def audit_scope(view: dict) -> str:
    if view["shared"]:
        return "history_own_full+shared_diagnoses"
    return "history_own_full"
