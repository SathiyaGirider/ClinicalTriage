"""Sessions, holds, tokens, outcomes. Concurrency included."""

import json
import threading
from datetime import timedelta

from sqlmodel import Session, select

from app.common import timeutil
from app.common.llm import FakeLLMClient, set_llm_client
from app.db import get_engine
from app.models import Appointment, ClinicSession, QueueEntryRow, User
from tests.conftest import SAME_DAY
from tests.helpers import book_routine, doctor_by_email, entry_id_for, hold, run_intake, session_of, submit


def _register(client, n):
    r = client.post("/auth/register", json={"full_name": f"Load Test {n}", "email": f"load{n}@example.com", "password": "long-password-1", "age": 30})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _small_session(doc_id, day, label="afternoon", max_tokens=5, reserved=2):
    with Session(get_engine()) as db:
        s = db.exec(select(ClinicSession).where(ClinicSession.doctor_id == doc_id, ClinicSession.date == day,
                                                ClinicSession.label == label)).first()
        for a in db.exec(select(Appointment).where(Appointment.session_id == s.id)).all():
            e = db.exec(select(QueueEntryRow).where(QueueEntryRow.appointment_id == a.id)).first()
            if e:
                db.delete(e)
                db.flush()
            a.status = "cancelled"  # frees capacity, keeps history
            db.add(a)
        s.max_tokens, s.reserved_urgent = max_tokens, reserved
        db.add(s)
        db.commit()
        return s.id


def test_no_overbooking_under_concurrency(client):
    doc = doctor_by_email("dr.gm.adyar@example.com")
    sid = _small_session(doc.id, timeutil.today() + timedelta(days=1), max_tokens=5, reserved=2)  # 3 regular units
    headers = [_register(client, i) for i in range(12)]
    results = []

    def worker(h):
        results.append(client.post("/booking/hold", json={"session_id": sid}, headers=h).status_code)

    threads = [threading.Thread(target=worker, args=(h,)) for h in headers]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert results.count(201) == 3 and results.count(409) == 9


def test_hold_expires_and_frees_capacity(client, H):
    doc = doctor_by_email("dr.gm.adyar@example.com")
    sid = _small_session(doc.id, timeutil.today() + timedelta(days=1), max_tokens=3, reserved=2)  # 1 regular unit
    hid = hold(client, H("asha"), sid)
    assert client.post("/booking/hold", json={"session_id": sid}, headers=H("ravi")).status_code == 409
    timeutil.advance(minutes=11)
    assert client.post("/booking/hold", json={"session_id": sid}, headers=H("ravi")).status_code == 201
    sid_i, _ = run_intake(client, H("asha"), "mild cold since yesterday")
    res = submit(client, H("asha"), sid_i)
    r = client.post("/booking/finalize", json={"hold_id": hid, "intake_id": res["intake_id"]}, headers=H("asha"))
    assert r.status_code == 410


def test_tokens_unique_increasing_never_reused(client, H):
    doc = doctor_by_email("dr.gm.adyar@example.com")
    day = timeutil.today() + timedelta(days=2)
    sid = _small_session(doc.id, day, max_tokens=10, reserved=2)
    a1 = book_routine(client, H("asha"), sid)
    a2 = book_routine(client, H("ravi"), sid)
    assert a2["token_number"] > a1["token_number"]
    assert client.post(f"/booking/{a1['id']}/cancel", headers=H("asha")).status_code == 200
    a3 = book_routine(client, H("priya"), sid)
    assert a3["token_number"] > a2["token_number"]  # cancelled number not reused
    assert len({a1["token_number"], a2["token_number"], a3["token_number"]}) == 3


def test_reserved_urgent_tokens_only_for_concerning(client, H, fake_llm):
    doc = doctor_by_email("dr.gm.adyar@example.com")
    sid = _small_session(doc.id, timeutil.today(), label="morning", max_tokens=3, reserved=2)
    book_routine(client, H("priya"), sid)  # uses the only regular unit
    assert client.post("/booking/hold", json={"session_id": sid}, headers=H("asha")).status_code == 409
    # routine intake cannot take a reserved token
    s_i, _ = run_intake(client, H("asha"), "mild cold since yesterday")
    routine = submit(client, H("asha"), s_i)
    r = client.post("/booking/finalize", json={"mode": "same_day", "session_id": sid, "intake_id": routine["intake_id"]}, headers=H("asha"))
    assert r.status_code == 409
    # concerning intake (repeated fainting) can
    s_c, _ = run_intake(client, H("ravi"), "I fainted twice yesterday")
    concern = submit(client, H("ravi"), s_c)
    assert concern["advice"]["outcome"] == "staff_will_check_on_you"
    r = client.post("/booking/finalize", json={"mode": "same_day", "session_id": sid, "intake_id": concern["intake_id"]}, headers=H("ravi"))
    assert r.status_code == 200, r.text
    appt = r.json()["appointment"]
    assert appt["type"] == "same_day" and appt["token_label"]
    with Session(get_engine()) as db:
        e = db.get(QueueEntryRow, entry_id_for(appt["id"]))
        assert e.flagged and e.presence == "booked_not_arrived"


def test_concerning_outcome_releases_original_hold(client, H):
    doc = doctor_by_email("dr.gm.adyar@example.com")
    sid = _small_session(doc.id, timeutil.today() + timedelta(days=1), max_tokens=3, reserved=2)
    hid = hold(client, H("asha"), sid)
    s_c, _ = run_intake(client, H("asha"), "I fainted twice this week")
    res = submit(client, H("asha"), s_c, hid)
    assert res["advice"]["outcome"] == "staff_will_check_on_you"
    r = client.post("/booking/finalize", json={"hold_id": hid, "intake_id": res["intake_id"]}, headers=H("asha"))
    assert r.status_code == 410  # released by the concerning outcome
    assert client.post("/booking/hold", json={"session_id": sid}, headers=H("ravi")).status_code == 201


def test_emergency_books_nothing(client, H):
    doc = doctor_by_email("dr.gm.adyar@example.com")
    sid = session_of(doc.id, timeutil.today() + timedelta(days=1)).id
    with Session(get_engine()) as db:
        before = len(db.exec(select(Appointment)).all())
    hid = hold(client, H("asha"), sid)
    s_e, st = run_intake(client, H("asha"), "severe chest pain and I can't breathe")
    assert st["ended_early_for_safety"]
    res = submit(client, H("asha"), s_e, hid)
    adv = res["advice"]
    assert adv["outcome"] == "seek_emergency_now" and "112" in adv["emergency_numbers"] and adv["suggested_department"] is None
    r = client.post("/booking/finalize", json={"hold_id": hid, "intake_id": res["intake_id"]}, headers=H("asha"))
    assert r.status_code == 410 or r.json().get("appointment") is None
    with Session(get_engine()) as db:
        assert len(db.exec(select(Appointment)).all()) == before


def test_today_sessions_and_walk_in_fallback(client, H, db):
    doc = doctor_by_email("dr.gm.adyar@example.com")
    r = client.get(f"/booking/today-sessions?doctor_id={doc.id}", headers=H("asha")).json()
    assert r["sessions"] and r["scope"] == "same_doctor"
    # close every General Medicine session today at that hospital -> walk-in fallback
    from app.models import Doctor
    for d in db.exec(select(Doctor).where(Doctor.hospital_id == doc.hospital_id, Doctor.specialty == "General Medicine")).all():
        for s in db.exec(select(ClinicSession).where(ClinicSession.doctor_id == d.id, ClinicSession.date == timeutil.today())).all():
            s.status = "closed"
            db.add(s)
    db.commit()
    r = client.get(f"/booking/today-sessions?doctor_id={doc.id}", headers=H("asha")).json()
    assert r["sessions"] == [] and r["walk_in_fallback"]["walk_in_window_text"]
    s_c, _ = run_intake(client, H("asha"), "I fainted twice this week")
    res = submit(client, H("asha"), s_c)
    w = client.post("/booking/walk-in-intent", json={"intake_id": res["intake_id"], "hospital_id": doc.hospital_id, "doctor_id": doc.id},
                    headers=H("asha"))
    assert w.status_code == 201, w.text
    appt = w.json()["appointment"]
    assert appt["type"] == "walk_in" and appt["status"] == "expected_today" and appt["token_label"] is None
    exp = client.get("/queue/expected-today", headers=H("nurse.adyar")).json()
    assert any(e["appointment_id"] == appt["id"] for e in exp["flagged"])
    # nurse check-in issues the W token
    eid = entry_id_for(appt["id"])
    c = client.post(f"/queue/{eid}/check-in", json={"outcome": "none"}, headers=H("nurse.adyar")).json()
    assert c["entry"]["token_label"].startswith("W-")


def test_estimate_updates_from_now_serving(client, H):
    doc = doctor_by_email("dr.gm.adyar@example.com")
    sid = _small_session(doc.id, timeutil.today(), label="morning", max_tokens=12, reserved=2)
    a1 = book_routine(client, H("asha"), sid)
    a2 = book_routine(client, H("ravi"), sid)
    st = client.get(f"/booking/{a2['id']}/status", headers=H("ravi")).json()
    first_est = st["est_call_from"]
    assert st["now_serving"] is None
    for a in (a1, a2):
        client.post(f"/queue/{entry_id_for(a['id'])}/check-in", json={"outcome": "none"}, headers=H("nurse.adyar"))
    client.post("/queue/action", json={"entry_id": entry_id_for(a1["id"]), "action": "mark_with_doctor"}, headers=H("nurse.adyar"))
    timeutil.advance(minutes=30)
    st2 = client.get(f"/booking/{a2['id']}/status", headers=H("ravi")).json()
    assert st2["now_serving"] == a1["token_label"]
    assert st2["est_call_from"] != first_est and st2["estimate_is_approximate"]


def test_reschedule_reuses_intake_and_releases_token(client, H):
    doc = doctor_by_email("dr.gm.adyar@example.com")
    d1, d2 = timeutil.today() + timedelta(days=1), timeutil.today() + timedelta(days=3)
    a = book_routine(client, H("asha"), session_of(doc.id, d1).id)
    r = client.post(f"/booking/{a['id']}/reschedule", json={"session_id": session_of(doc.id, d2).id}, headers=H("asha"))
    assert r.status_code == 200, r.text
    new = r.json()["appointment"]
    assert new["intake_id"] == a["intake_id"] and new["date"] == d2.isoformat()
    mine = client.get("/booking/mine", headers=H("asha")).json()
    assert any(p["id"] == a["id"] and p["status"] == "cancelled" for p in mine["past"])


def test_ics_download(client, H):
    doc = doctor_by_email("dr.gm.adyar@example.com")
    a = book_routine(client, H("asha"), session_of(doc.id, timeutil.today() + timedelta(days=1)).id)
    r = client.get(f"/booking/{a['id']}/ics", headers=H("asha"))
    assert r.status_code == 200 and "BEGIN:VCALENDAR" in r.text and "approximate" in r.text
