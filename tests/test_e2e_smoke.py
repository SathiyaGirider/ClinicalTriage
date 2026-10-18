"""One end-to-end journey: patient books, nurse checks in, doctor completes, patient sees the record."""

from app.common import timeutil
from tests.helpers import book_routine, doctor_by_email, entry_id_for, session_of


def test_full_journey(client, H):
    doc = doctor_by_email("dr.gm.adyar@example.com")
    s = session_of(doc.id, timeutil.today(), "morning")
    appt = book_routine(client, H("asha"), s.id)
    assert appt["token_label"].startswith("M-")
    assert appt["est_call_from"] and appt["estimate_is_approximate"]

    eid = entry_id_for(appt["id"])
    r = client.post(f"/queue/{eid}/check-in", json={"outcome": "none"}, headers=H("nurse.adyar"))
    assert r.status_code == 200, r.text
    q = client.get(f"/queue?doctor_id={doc.id}", headers=H("nurse.adyar")).json()
    assert any(e["id"] == eid for e in q["doctors"][0]["present_waiting"])

    today = client.get("/doctor/today", headers=H("dr.gm.adyar")).json()
    assert any(e["id"] == eid for e in today["present"])
    r = client.post(f"/doctor/start/{eid}", headers=H("dr.gm.adyar"))
    assert r.status_code == 200, r.text
    st = client.get(f"/booking/{appt['id']}/status", headers=H("asha")).json()
    assert st["now_serving"] == appt["token_label"] and st["state"] == "with_doctor"

    ws = client.get(f"/doctor/patient/{st['doctor'] and today['present'][0]['patient_id']}", headers=H("dr.gm.adyar"))
    assert ws.status_code == 200, ws.text
    assert len(ws.json()["lines"]) == 5
    r = client.post("/ehr/consultation", json={"appointment_id": appt["id"], "diagnosis_text": "Common cold",
                                               "clinical_notes": "Mild URTI", "prescription": [
                                                   {"drug": "Saline nasal drops", "dose": "2 drops", "frequency": "three times daily",
                                                    "duration": "5 days", "instructions": "Each nostril"}]}, headers=H("dr.gm.adyar"))
    assert r.status_code == 201, r.text
    rec = client.get("/me/records", headers=H("asha")).json()
    assert rec["visits"][0]["diagnosis_text"] == "Common cold"
    assert rec["visits"][0]["prescriptions"][0]["drug"] == "Saline nasal drops"
    assert rec["footer"] == "Follow your doctor's instructions."
