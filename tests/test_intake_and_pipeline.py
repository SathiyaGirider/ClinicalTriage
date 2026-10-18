"""Adaptive intake flow, pipeline fail-safe, and no patient text in logs."""

import json
import logging

from app.common.llm import FakeLLMClient, set_llm_client
from tests.helpers import run_intake, submit


def test_question_count_and_fixed_safety_screen(client, H):
    sid, st = run_intake(client, H("asha"), "runny nose")  # short complaint -> 2 adaptive
    res = client.get(f"/intake/session/{sid}/result", headers=H("asha")).json()
    keys = [a["key"] for a in res["understood"]["answers"]]
    assert keys[0] == "complaint" and "safety_screen" in keys and "duration" in keys and "conditions" in keys
    assert "age" not in keys  # prefilled from profile
    assert 4 <= len(keys) <= 6
    screen = next(a for a in res["understood"]["answers"] if a["key"] == "safety_screen")
    assert screen["options"][0] == "none" and len(screen["options"]) == 8


def test_age_asked_when_profile_has_none(client, H, db):
    from app.models import Patient
    from tests.test_authz import uid
    p = db.get(Patient, uid("priya@example.com"))
    p.dob_or_age = None
    db.add(p)
    db.commit()
    sid, st = run_intake(client, H("priya"), "itchy rash on both arms for a week now", age=25)
    keys = [a["key"] for a in client.get(f"/intake/session/{sid}/result", headers=H("priya")).json()["understood"]["answers"]]
    assert "age" in keys and len(keys) <= 6


def test_emergency_ends_intake_early(client, H):
    sid, st = run_intake(client, H("asha"), "my father's face is drooping and his speech is slurred")
    assert st["ended_early_for_safety"] and st["question_number"] == 1


def test_adaptive_question_from_llm_and_filtered(client, H, fake_llm):
    calls = {"n": 0}

    def llm(system, user, purpose):
        if purpose == "question":
            calls["n"] += 1
            return "You have dengue, did you take paracetamol?" if calls["n"] == 1 else "Is it worse at night?"
        if purpose == "triage":
            return json.dumps({"priority": "routine", "confidence": "high", "rationale": "Mild."})
        return None
    set_llm_client(FakeLLMClient(llm))
    sid, st = run_intake(client, H("asha"), "cough")
    qs = [a["question"] for a in client.get(f"/intake/session/{sid}/result", headers=H("asha")).json()["understood"]["answers"]]
    assert "Is it worse at night?" in qs
    assert not any("dengue" in q for q in qs)


def test_confirm_screen_edit(client, H):
    sid, st = run_intake(client, H("asha"), "mild cold since yesterday")
    r = client.post(f"/intake/session/{sid}/answer", json={"key": "complaint", "answer": "mild cold and sneezing since yesterday"}, headers=H("asha"))
    assert r.status_code == 200
    res = client.get(f"/intake/session/{sid}/result", headers=H("asha")).json()
    assert "sneezing" in res["understood"]["your_words"]
    assert "priority" not in json.dumps(res)


def test_patient_advice_never_shows_priority(client, H):
    sid, _ = run_intake(client, H("asha"), "I fainted twice this week")
    out = submit(client, H("asha"), sid)
    text = json.dumps(out)
    assert out["advice"]["outcome"] == "staff_will_check_on_you"
    for word in ("same-day", "emergency\"", "priority", "rationale", "red_flag"):
        assert word not in text


def test_tamil_advice(client, H):
    r = client.post("/intake/session/start", json={"mode": "booking", "language": "ta"}, headers=H("ravi")).json()
    assert r["current"]["question"] == "உங்களுக்கு என்ன தொந்தரவு?"
    sid, _ = run_intake(client, H("ravi"), "நெஞ்சு வலி மற்றும் மூச்சு திணறல்")
    out = submit(client, H("ravi"), sid)
    assert out["advice"]["outcome"] == "seek_emergency_now" and out["advice"]["language"] == "ta"


def test_pipeline_fail_safe_on_forced_exception(client, H, monkeypatch):
    import app.pipeline.service as ps
    monkeypatch.setattr(ps, "triage", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    sid, _ = run_intake(client, H("asha"), "mild cold since yesterday")
    out = submit(client, H("asha"), sid)
    assert out["advice"]["outcome"] == "staff_will_check_on_you"


def test_triage_internal_failure_via_api_is_flagged(client, H, monkeypatch):
    import app.triage.service as ts
    monkeypatch.setattr(ts, "_triage", lambda *a, **k: 1 / 0)
    sid, _ = run_intake(client, H("asha"), "mild cold since yesterday")
    out = submit(client, H("asha"), sid)
    assert out["advice"]["outcome"] == "staff_will_check_on_you"


def test_no_patient_text_or_email_in_logs(client, caplog):
    caplog.set_level(logging.DEBUG)
    r = client.post("/auth/register", json={"full_name": "Logcheck Person", "email": "logcheck@example.com", "password": "long-password-1", "age": 40})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    secret = "zebra-unicorn chest pain and my secret words"
    sid, _ = run_intake(client, h, secret)
    submit(client, h, sid)
    client.post("/auth/login", json={"email": "logcheck@example.com", "password": "wrong-password"})
    logs = "\n".join(rec.getMessage() for rec in caplog.records)
    assert "zebra-unicorn" not in logs and "secret words" not in logs
    assert "logcheck@example.com" not in logs and "Logcheck Person" not in logs
    assert "triage patient=" in logs  # ids and decisions are logged


def test_redact_filter_scrubs_emails():
    from app.common.logging_setup import RedactFilter
    rec = logging.LogRecord("x", logging.INFO, "f", 1, "user %s failed", ("someone@example.com",), None)
    RedactFilter().filter(rec)
    assert "someone@example.com" not in rec.getMessage()
