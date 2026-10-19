"""Unit tests for app/ehr/history_policy.py."""

from datetime import date

import pytest

from app.ehr.adapter import EncounterRecord, PrescriptionItem
from app.ehr.history_policy import AccessDenied, view_for_doctor, view_for_nurse, view_for_patient


def enc(i, doctor_id):
    return EncounterRecord(id=i, patient_id=1, doctor_id=doctor_id, date=date(2026, 1, i), diagnosis_text=f"dx{i}", clinical_notes=f"notes{i}",
                           doctor_name=f"D{doctor_id}", specialty="GM", hospital_name="H",
                           prescriptions=[PrescriptionItem(drug=f"drug{i}", dose="1")])


ENCS = [enc(1, 10), enc(2, 20)]


def test_patient_sees_all_own():
    v = view_for_patient(ENCS)
    assert {e["diagnosis_text"] for e in v} == {"dx1", "dx2"} and v[0]["prescriptions"]


def test_treating_doctor_full_others_hidden_without_consent():
    v = view_for_doctor(ENCS, 10, True, consent=False)
    assert [e["diagnosis_text"] for e in v["own"]] == ["dx1"] and v["own"][0]["clinical_notes"] == "notes1"
    assert v["shared"] == [] and "dx2" not in str(v) and "drug2" not in str(v)


def test_consent_on_diagnoses_only():
    v = view_for_doctor(ENCS, 10, True, consent=True)
    assert v["shared"] == [{"id": 2, "date": "2026-01-02", "specialty": "GM", "hospital_name": "H", "diagnosis_text": "dx2",
                            "scope": "shared_diagnosis_only"}]
    assert "notes2" not in str(v) and "drug2" not in str(v)


def test_no_relationship_no_access():
    with pytest.raises(AccessDenied):
        view_for_doctor(ENCS, 30, False, consent=True)


def test_nurse_no_access():
    with pytest.raises(AccessDenied):
        view_for_nurse()
