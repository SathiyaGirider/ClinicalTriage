"""Queue rules: presence, ordering modes, walk-ins, late arrivals, nurse actions, flags, alerts."""

from datetime import datetime, timedelta

import pytest
from sqlmodel import Session

from app.common import timeutil
from app.db import get_engine
from app.models import QueueEntryRow
from app.queue.ordering import order_queue
from tests.helpers import book_routine, doctor_by_email, entry_id_for, run_intake, session_of, submit
from tests.test_booking import _small_session

NURSE = "nurse.adyar"


@pytest.fixture
def three_booked(client, H):
    doc = doctor_by_email("dr.gm.adyar@example.com")
    sid = _small_session(doc.id, timeutil.today(), label="morning", max_tokens=15, reserved=2)
    appts = [book_routine(client, H(p), sid) for p in ("asha", "ravi", "priya")]
    return doc, sid, appts


def ids(entries):
    return [e["id"] for e in entries]


def queue_of(client, H, doc):
    return client.get(f"/queue?doctor_id={doc.id}&session=morning", headers=H(NURSE)).json()["doctors"][0]


def checkin(client, H, appt, outcome="none", note=None):
    r = client.post(f"/queue/{entry_id_for(appt['id'])}/check-in", json={"outcome": outcome, "note": note}, headers=H(NURSE))
    assert r.status_code == 200, r.text
    return r.json()


def act(client, H, appt_or_eid, action, **kw):
    eid = appt_or_eid if isinstance(appt_or_eid, int) else entry_id_for(appt_or_eid["id"])
    return client.post("/queue/action", json={"entry_id": eid, "action": action, **kw}, headers=H(NURSE))


def test_only_present_in_doctor_queue_and_token_order(client, H, three_booked):
    doc, _, (a1, a2, a3) = three_booked
    checkin(client, H, a3)
    checkin(client, H, a1)
    q = queue_of(client, H, doc)
    assert ids(q["present_waiting"]) == [entry_id_for(a1["id"]), entry_id_for(a3["id"])]  # token order, not arrival
    assert entry_id_for(a2["id"]) in ids(q["booked_not_arrived"])
    today = client.get("/doctor/today", headers=H("dr.gm.adyar")).json()
    assert ids(today["present"]) == ids(q["present_waiting"]) and today["not_arrived_count"] >= 1


def test_im_here_needs_nurse_confirmation(client, H, three_booked):
    doc, _, (a1, _, _) = three_booked
    r = client.post(f"/booking/{a1['id']}/arrived", json={"change": "none"}, headers=H("asha"))
    assert r.json()["message"] == "Waiting for the nurse to confirm."
    q = queue_of(client, H, doc)
    assert entry_id_for(a1["id"]) not in ids(q["present_waiting"])
    checkin(client, H, a1)
    assert entry_id_for(a1["id"]) in ids(queue_of(client, H, doc)["present_waiting"])


def test_patient_worse_with_text_flags_and_retriages(client, H, three_booked):
    doc, _, (a1, _, _) = three_booked
    client.post(f"/booking/{a1['id']}/arrived", json={"change": "worse", "text": "now I have chest pain"}, headers=H("asha"))
    checkin(client, H, a1, "worse")
    q = queue_of(client, H, doc)
    att = [e for e in q["needs_attention"] if e["id"] == entry_id_for(a1["id"])]
    assert att and att[0]["priority"] == "same-day" and "chest_pain" in att[0]["red_flags"]


def test_nurse_checkin_worse_only_raises(client, H, three_booked):
    doc, _, (a1, _, _) = three_booked
    res = checkin(client, H, a1, "worse", note="feels better actually, mild")
    assert res["recheck_recommended"] and res["entry"]["flagged"] and res["entry"]["flag_source"] == "nurse"
    assert res["entry"]["priority"] in ("routine", "same-day", "emergency")
    # re-check flow with a red flag raises to emergency
    r = client.post(f"/queue/{entry_id_for(a1['id'])}/recheck/start?change=worse", headers=H(NURSE)).json()
    sid = r["session_id"]
    st = r
    while not st["done"]:
        key = st["current"]["key"]
        ans = {"change": "now has trouble breathing and chest pain", "change_when": "just_now"}.get(key, "worse")
        st = client.post(f"/intake/session/{sid}/answer", json={"key": key, "answer": ans}, headers=H(NURSE)).json()
    out = client.post("/pipeline/submit", json={"intake_session_id": sid}, headers=H(NURSE)).json()
    assert out["priority_raised"] and out["decision"]["priority"] == "emergency"


def test_ai_flag_never_reorders(client, H, three_booked):
    doc, _, (a1, a2, a3) = three_booked
    for a in (a1, a2, a3):
        checkin(client, H, a)
    before = ids(queue_of(client, H, doc)["present_waiting"])
    # vitals that raise priority -> AI flag only, order unchanged
    r = client.post("/queue/vitals", json={"entry_id": entry_id_for(a3["id"]), "spo2": 88}, headers=H(NURSE)).json()
    assert r["priority_raised"] and r["message"] == "Priority raised: SpO2 below safe threshold."
    q = queue_of(client, H, doc)
    assert ids(q["present_waiting"]) == before
    assert entry_id_for(a3["id"]) in ids(q["needs_attention"])


def test_nurse_mode_move_and_switch_back(client, H, three_booked):
    doc, _, (a1, a2, a3) = three_booked
    for a in (a1, a2, a3):
        checkin(client, H, a)
    base = ids(queue_of(client, H, doc)["present_waiting"])
    assert act(client, H, a3, "move_up").status_code == 409  # token mode: no manual moves
    client.post("/queue/order", json={"doctor_id": doc.id, "session": "morning", "mode": "nurse"}, headers=H(NURSE))
    assert act(client, H, a3, "move_to", position=0, reason="frail").status_code == 200
    q = queue_of(client, H, doc)
    assert q["mode"] == "nurse" and ids(q["present_waiting"])[0] == entry_id_for(a3["id"])
    client.post("/queue/order", json={"doctor_id": doc.id, "session": "morning", "mode": "token"}, headers=H(NURSE))
    assert ids(queue_of(client, H, doc)["present_waiting"]) == base


def test_fast_track_and_return_to_queue(client, H, three_booked):
    doc, _, (a1, a2, a3) = three_booked
    for a in (a1, a2, a3):
        checkin(client, H, a)
    act(client, H, a1, "mark_with_doctor")
    act(client, H, a3, "fast_track")
    q = queue_of(client, H, doc)
    assert q["now_serving"] == a1["token_label"]
    assert ids(q["present_waiting"])[0] == entry_id_for(a3["id"])  # right after the patient with the doctor
    act(client, H, a3, "return_to_queue")
    assert ids(queue_of(client, H, doc)["present_waiting"]) == [entry_id_for(a2["id"]), entry_id_for(a3["id"])]


def test_called_absent_joins_after_present(client, H, three_booked):
    doc, _, (a1, a2, a3) = three_booked
    checkin(client, H, a2)
    checkin(client, H, a3)
    act(client, H, a3, "mark_with_doctor")  # token 1 (a1) has passed while absent
    with Session(get_engine()) as db:
        assert db.get(QueueEntryRow, entry_id_for(a1["id"])).presence == "called_absent"
    act(client, H, a3, "mark_done")
    timeutil.advance(minutes=5)
    res = checkin(client, H, a1)
    assert res["entry"]["late_arrival"]
    assert ids(queue_of(client, H, doc)["present_waiting"]) == [entry_id_for(a2["id"]), entry_id_for(a1["id"])]


def test_walkins_after_booked_and_no_show(client, H, three_booked):
    doc, _, (a1, a2, a3) = three_booked
    checkin(client, H, a1)
    w = client.post("/queue/walk-in", json={"full_name": "Walk In Demo", "age": 40, "language": "ta", "doctor_id": doc.id}, headers=H(NURSE))
    assert w.status_code == 201, w.text
    wid = w.json()["entry"]["id"]
    assert w.json()["entry"]["token_label"] == "W-01"
    checkin(client, H, a2)
    assert ids(queue_of(client, H, doc)["present_waiting"]) == [entry_id_for(a1["id"]), entry_id_for(a2["id"]), wid]
    assert act(client, H, a1, "mark_no_show").status_code == 409  # present patients cannot be no-show
    assert act(client, H, a3, "mark_no_show").status_code == 200


class E:
    def __init__(self, id, token, walk=False, late=False, ts=0):
        self.id, self.presence, self.status = id, "present", "waiting"
        self.token_number, self.token_label = token, (f"W-{token:02d}" if walk else f"M-{token:02d}")
        self.check_in_ts = datetime(2026, 1, 1, 9) + timedelta(minutes=ts)
        self.late_arrival, self.fast_tracked_at, self.nurse_position = late, None, None


def test_interleave_policy():
    booked = [E(i, i, ts=i) for i in range(1, 7)]
    walk = [E(100 + i, i, walk=True, ts=10 + i) for i in range(1, 3)]
    assert [e.id for e in order_queue(booked + walk, "token", "after_booked")] == [1, 2, 3, 4, 5, 6, 101, 102]
    assert [e.id for e in order_queue(booked + walk, "token", "interleave")] == [1, 2, 3, 101, 4, 5, 6, 102]


def test_nurse_positions_keep_relative_order_of_unplaced():
    es = [E(i, i) for i in range(1, 5)]
    es[3].nurse_position = 0  # token 4 placed first
    assert [e.id for e in order_queue(es, "nurse")] == [4, 1, 2, 3]
    assert [e.id for e in order_queue(es, "token")] == [1, 2, 3, 4]


def test_reasons_required(client, H, three_booked):
    doc, _, (a1, _, _) = three_booked
    eid = entry_id_for(a1["id"])
    assert client.post("/queue/flag", json={"entry_id": eid, "flagged": True, "reason": ""}, headers=H(NURSE)).status_code == 422
    assert act(client, H, a1, "change_priority", priority="emergency").status_code == 422
    assert act(client, H, a1, "change_priority", priority="emergency", reason="looks unwell").status_code == 200
    assert client.post("/doctor/override", json={"appointment_id": a1["id"], "priority": "routine", "reason": ""},
                       headers=H("dr.gm.adyar")).status_code == 422
    log = client.get("/queue/action-log", headers=H(NURSE)).json()
    assert any(r["action"] == "change_priority" and r["reason"] == "looks unwell" and r["new_value"] == "emergency" for r in log)


def test_alert_escalation_states(client, H, three_booked):
    doc, _, (a1, _, _) = three_booked
    eid = entry_id_for(a1["id"])
    checkin(client, H, a1)
    client.post("/queue/flag", json={"entry_id": eid, "flagged": True, "reason": "pale"}, headers=H(NURSE))

    def state():
        return next(e for e in queue_of(client, H, doc)["needs_attention"] if e["id"] == eid)["alert_state"]
    assert state() == "normal"
    timeutil.advance(seconds=181)
    assert state() == "amber"
    timeutil.advance(seconds=120)
    assert state() == "red"
    client.post(f"/queue/{eid}/ack", headers=H(NURSE))
    assert state() == "none"


def test_assisted_intake_for_walk_in(client, H):
    doc = doctor_by_email("dr.gm.adyar@example.com")
    w = client.post("/queue/walk-in", json={"full_name": "Assisted Demo", "age": 70, "language": "en", "doctor_id": doc.id}, headers=H(NURSE)).json()
    r = client.post("/queue/assisted-intake/start", json={"entry_id": w["entry"]["id"]}, headers=H(NURSE)).json()
    sid, st = r["session_id"], r
    assert st["age_prefilled"] == 70
    while not st["done"]:
        key = st["current"]["key"]
        ans = {"complaint": "fainted at home this morning", "safety_screen": ["fainting"], "duration": "today", "conditions": ["none"]}.get(key, "no")
        st = client.post(f"/intake/session/{sid}/answer", json={"key": key, "answer": ans}, headers=H(NURSE)).json()
    out = client.post("/pipeline/submit", json={"intake_session_id": sid}, headers=H(NURSE)).json()
    assert out["decision"]["priority"] == "same-day" and out["decision"]["decided_by"] == "rule"
    q = queue_of(client, H, doc)
    assert w["entry"]["id"] in ids(q["needs_attention"])


def test_walk_in_omits_doctor_id_and_assigns_nurse_doctor(client, H):
    doc = doctor_by_email("dr.gm.adyar@example.com")
    w = client.post("/queue/walk-in", json={"full_name": "No Doc Param", "age": 45, "language": "en"}, headers=H(NURSE)).json()
    assert w["entry"]["token_label"].startswith("W-")
    appt_id = w["appointment_id"]
    from app.models import Appointment
    with Session(get_engine()) as s:
        appt = s.get(Appointment, appt_id)
        assert appt.doctor_id == doc.id
