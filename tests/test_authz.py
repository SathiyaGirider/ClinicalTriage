"""Role checks and object-level checks (IDOR attempts), history policy over the API, audit logging."""

from datetime import timedelta

from sqlmodel import Session, select

from app.common import timeutil
from app.db import get_engine
from app.models import AuditLog, User
from tests.helpers import book_routine, doctor_by_email, entry_id_for, run_intake, session_of


def uid(email):
    with Session(get_engine()) as db:
        return db.exec(select(User).where(User.email == email)).first().id


def test_unauthenticated_rejected(client):
    for path in ("/booking/mine", "/queue", "/doctor/today", "/me/records", "/catalog/hospitals"):
        assert client.get(path).status_code == 401


def test_roles_enforced(client, H):
    assert client.get("/queue", headers=H("asha")).status_code == 403
    assert client.get("/doctor/today", headers=H("nurse.adyar")).status_code == 403
    assert client.get("/booking/mine", headers=H("dr.gm.adyar")).status_code == 403
    assert client.post("/triage", json={}, headers=H("asha")).status_code == 403  # patients never see priority


def test_register_is_patient_only_and_rejects_phone(client):
    r = client.post("/auth/register", json={"full_name": "X", "email": "x1@example.com", "password": "long-password-1", "age": 30, "role": "doctor"})
    assert r.status_code == 422
    r = client.post("/auth/register", json={"full_name": "X", "email": "x2@example.com", "password": "long-password-1", "age": 30, "phone": "9999999999"})
    assert r.status_code == 422
    r = client.post("/auth/register", json={"full_name": "X", "email": "x3@example.com", "password": "short", "age": 30})
    assert r.status_code == 422
    r = client.post("/auth/register", json={"full_name": "X", "email": "x4@example.com", "password": "long-password-1", "age": 30, "language": "ta"})
    assert r.status_code == 201 and r.json()["role"] == "patient"


def test_login_rate_limit(client):
    for _ in range(5):
        assert client.post("/auth/login", json={"email": "asha@example.com", "password": "wrong-password"}).status_code == 401
    assert client.post("/auth/login", json={"email": "asha@example.com", "password": "test-password-123"}).status_code == 429


def test_patient_cannot_read_other_patients_data(client, H):
    doc = doctor_by_email("dr.gm.adyar@example.com")
    a = book_routine(client, H("asha"), session_of(doc.id, timeutil.today() + timedelta(days=1)).id)
    rv = H("ravi")
    assert client.get(f"/booking/{a['id']}/status", headers=rv).status_code == 404
    assert client.post(f"/booking/{a['id']}/cancel", headers=rv).status_code == 404
    assert client.post(f"/booking/{a['id']}/arrived", json={"change": "none"}, headers=rv).status_code == 404
    assert client.get(f"/booking/{a['id']}/ics", headers=rv).status_code == 404
    sid, _ = run_intake(client, H("asha"), "mild cold")
    assert client.get(f"/intake/session/{sid}/result", headers=rv).status_code == 404
    assert client.post("/pipeline/submit", json={"intake_session_id": sid}, headers=rv).status_code == 404
    res = client.post("/pipeline/submit", json={"intake_session_id": sid}, headers=H("asha")).json()
    assert client.post("/booking/finalize", json={"mode": "same_day", "session_id": 1, "intake_id": res["intake_id"]}, headers=rv).status_code == 404
    assert "Ravi" not in str(client.get("/me/records", headers=H("asha")).json())


def test_nurse_cannot_read_diagnoses_or_prescriptions(client, H):
    nh = H("nurse.adyar")
    asha = uid("asha@example.com")
    assert client.get(f"/doctor/patient/{asha}", headers=nh).status_code == 403
    assert client.get(f"/ehr/fhir/Encounter?patient={asha}", headers=nh).status_code == 403
    assert client.get(f"/ehr/fhir/MedicationRequest?patient={asha}", headers=nh).status_code == 403
    assert client.get("/me/records", headers=nh).status_code == 403
    doc = doctor_by_email("dr.gm.adyar@example.com")
    a = book_routine(client, H("asha"), session_of(doc.id, timeutil.today()).id)
    detail = client.get(f"/queue/entry/{entry_id_for(a['id'])}", headers=nh).json()
    text = str(detail)
    assert "Palpitations" not in text and "Propranolol" not in text and "Viral fever" not in text
    assert detail["lines"] and len(detail["lines"]) == 5


def test_nurse_other_hospital_blocked(client, H):
    doc = doctor_by_email("dr.gm.adyar@example.com")
    a = book_routine(client, H("asha"), session_of(doc.id, timeutil.today()).id)
    eid = entry_id_for(a["id"])
    other = H("nurse.mylapore")
    assert client.get(f"/queue/entry/{eid}", headers=other).status_code == 403
    assert client.post(f"/queue/{eid}/check-in", json={"outcome": "none"}, headers=other).status_code == 403
    assert client.post("/queue/action", json={"entry_id": eid, "action": "fast_track"}, headers=other).status_code == 403


def test_nurse_cross_doctor_in_same_hospital_blocked(client, H):
    """Nurse A cannot read, check in, flag, or act on Doctor B's queue even in the same hospital."""
    doc_gm = doctor_by_email("dr.gm.adyar@example.com")
    a = book_routine(client, H("asha"), session_of(doc_gm.id, timeutil.today()).id)
    eid = entry_id_for(a["id"])
    cardio_nurse = H("nurse.cardio.adyar")  # same hospital (Adyar), different assigned doctor

    assert client.get(f"/queue/entry/{eid}", headers=cardio_nurse).status_code == 403
    assert client.post(f"/queue/{eid}/check-in", json={"outcome": "none"}, headers=cardio_nurse).status_code == 403
    assert client.post("/queue/action", json={"entry_id": eid, "action": "fast_track"}, headers=cardio_nurse).status_code == 403
    assert client.post("/queue/flag", json={"entry_id": eid, "flagged": True, "reason": "test"}, headers=cardio_nurse).status_code == 403
    assert client.post("/queue/vitals", json={"entry_id": eid, "spo2": 98}, headers=cardio_nurse).status_code == 403
    assert client.post(f"/queue/{eid}/recheck/start", headers=cardio_nurse).status_code == 403


def test_nurse_unassigned_blocked(client, H):
    """A nurse with no assigned doctor is blocked on all queue actions and receives 403."""
    unassigned = H("nurse.unassigned")
    assert client.get("/queue", headers=unassigned).status_code == 403
    assert client.get("/queue/search?query=asha", headers=unassigned).status_code == 403
    assert client.get("/queue/expected-today", headers=unassigned).status_code == 403
    assert client.get("/queue/action-log", headers=unassigned).status_code == 403
    assert client.post("/queue/walk-in", json={"full_name": "Test Walkin", "age": 40, "language": "en"}, headers=unassigned).status_code == 403


def test_nurse_queue_ignores_client_doctor_id(client, H):
    """Nurse queue request strictly ignores any client-supplied doctor_id and returns only assigned doctor."""
    doc_gm = doctor_by_email("dr.gm.adyar@example.com")
    doc_cardio = doctor_by_email("dr.cardio.adyar@example.com")
    # nurse.adyar is assigned to dr.gm.adyar; sending doctor_id=doc_cardio.id must still return doc_gm.id
    res = client.get(f"/queue?doctor_id={doc_cardio.id}", headers=H("nurse.adyar")).json()
    assert len(res["doctors"]) == 1
    assert res["doctors"][0]["doctor"]["id"] == doc_gm.id
    assert res["assigned_doctor"]["id"] == doc_gm.id


def test_seed_pairing_is_one_to_one(client):
    """Every seeded nurse is paired with exactly one doctor, and every seeded doctor account has one nurse."""
    from app.models import NurseAssignment
    with Session(get_engine()) as db:
        assignments = db.exec(select(NurseAssignment)).all()
        nurse_ids = [a.nurse_id for a in assignments]
        doc_ids = [a.doctor_id for a in assignments]
        assert len(nurse_ids) == len(set(nurse_ids)), "Nurse IDs must be unique (1-to-1)"
        assert len(doc_ids) == len(set(doc_ids)), "Doctor IDs must be unique (1-to-1)"
        assert len(assignments) == 6  # 6 account doctors paired with 6 nurses


def test_doctor_cannot_read_unrelated_patient(client, H):
    priya = uid("priya@example.com")  # no appointments with anyone
    for d in ("dr.gm.adyar", "dr.derm.adyar"):
        assert client.get(f"/doctor/patient/{priya}", headers=H(d)).status_code == 403
        assert client.get(f"/ehr/fhir/Patient/{priya}", headers=H(d)).status_code == 403
    assert all(p["patient_id"] != priya for p in client.get("/doctor/patients", headers=H("dr.gm.adyar")).json())


def test_consent_off_hides_other_doctors_and_on_shows_diagnoses_only(client, H):
    asha = uid("asha@example.com")
    derm = doctor_by_email("dr.derm.adyar@example.com")
    book_routine(client, H("asha"), session_of(derm.id, timeutil.today() + timedelta(days=1)).id, "itchy rash on my arm")
    client.put("/me/consent", json={"share_history_consent": False}, headers=H("asha"))
    h = client.get(f"/doctor/patient/{asha}", headers=H("dr.derm.adyar")).json()["history"]
    assert h["shared"] == [] and "Palpitations" not in str(h) and "Viral fever" not in str(h)
    client.put("/me/consent", json={"share_history_consent": True}, headers=H("asha"))
    h = client.get(f"/doctor/patient/{asha}", headers=H("dr.derm.adyar")).json()["history"]
    dx = {s["diagnosis_text"] for s in h["shared"]}
    assert "Viral fever" in dx and h["shared_label"] == "Shared with patient's consent. Diagnoses only."
    for s in h["shared"]:
        assert "prescriptions" not in s and "clinical_notes" not in s
    assert "Propranolol" not in str(h) and "Paracetamol" not in str(h)
    meds = client.get(f"/ehr/fhir/MedicationRequest?patient={asha}", headers=H("dr.derm.adyar")).json()
    assert meds["total"] == 0


def test_treating_doctor_sees_own_encounters_in_full(client, H):
    asha = uid("asha@example.com")
    h = client.get(f"/doctor/patient/{asha}", headers=H("dr.cardio.adyar")).json()["history"]
    own = h["own"][0]
    assert own["diagnosis_text"].startswith("Palpitations") and own["clinical_notes"] and own["prescriptions"][0]["drug"] == "Propranolol"


def test_every_history_view_is_audit_logged(client, H):
    asha = uid("asha@example.com")
    with Session(get_engine()) as db:
        before = len(db.exec(select(AuditLog).where(AuditLog.patient_id == asha)).all())
    client.get(f"/doctor/patient/{asha}", headers=H("dr.cardio.adyar"))
    client.get(f"/ehr/fhir/Encounter?patient={asha}", headers=H("dr.cardio.adyar"))
    client.get(f"/ehr/fhir/MedicationRequest?patient={asha}", headers=H("dr.cardio.adyar"))
    with Session(get_engine()) as db:
        rows = db.exec(select(AuditLog).where(AuditLog.patient_id == asha)).all()
    assert len(rows) == before + 3
    log = client.get("/me/access-log", headers=H("asha")).json()
    assert log and log[0]["viewer"].startswith("Dr.") and log[0]["hospital"]


def test_doctor_cannot_consult_another_doctors_appointment(client, H):
    doc = doctor_by_email("dr.gm.adyar@example.com")
    a = book_routine(client, H("asha"), session_of(doc.id, timeutil.today()).id)
    r = client.post("/ehr/consultation", json={"appointment_id": a["id"], "diagnosis_text": "x"}, headers=H("dr.derm.adyar"))
    assert r.status_code == 404
    r = client.post("/doctor/override", json={"appointment_id": a["id"], "priority": "routine", "reason": "x"}, headers=H("dr.derm.adyar"))
    assert r.status_code == 404


def test_external_ehr_stub_raises_clear_error():
    import pytest
    from app.ehr.external_stub import ExternalEhrAdapter
    with pytest.raises(NotImplementedError, match="not connected"):
        ExternalEhrAdapter().get_encounters(1)
