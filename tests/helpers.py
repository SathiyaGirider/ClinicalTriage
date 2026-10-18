"""Flow helpers shared by the API tests."""

from sqlmodel import Session, select

from app.db import get_engine
from app.models import ClinicSession, Doctor


def doctor_by_email(email: str) -> Doctor:
    from app.models import User
    with Session(get_engine()) as db:
        u = db.exec(select(User).where(User.email == email)).first()
        return db.exec(select(Doctor).where(Doctor.user_id == u.id)).first()


def session_of(doctor_id: int, day, label: str = "morning") -> ClinicSession:
    with Session(get_engine()) as db:
        return db.exec(select(ClinicSession).where(ClinicSession.doctor_id == doctor_id, ClinicSession.date == day,
                                                   ClinicSession.label == label)).first()


def run_intake(client, h, complaint, safety=("none",), duration="1_3_days", conditions=("none",), adaptive="mild, getting better",
               mode="booking", age=None):
    r = client.post("/intake/session/start", json={"mode": mode}, headers=h)
    assert r.status_code == 200, r.text
    st = r.json()
    sid = st["session_id"]
    answers = {"complaint": complaint, "safety_screen": list(safety), "duration": duration, "conditions": list(conditions), "age": age}
    guard = 0
    while not st["done"]:
        key = st["current"]["key"]
        val = answers.get(key, adaptive) if not key.startswith("adaptive") else adaptive
        r = client.post(f"/intake/session/{sid}/answer", json={"key": key, "answer": val}, headers=h)
        assert r.status_code == 200, r.text
        st = r.json()
        guard += 1
        assert guard < 10
    return sid, st


def submit(client, h, sid, hold_id=None):
    r = client.post("/pipeline/submit", json={"intake_session_id": sid, "hold_id": hold_id}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def hold(client, h, session_id):
    r = client.post("/booking/hold", json={"session_id": session_id}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["hold_id"]


def book_routine(client, h, session_id, complaint="mild cold and runny nose since yesterday"):
    hid = hold(client, h, session_id)
    sid, _ = run_intake(client, h, complaint)
    res = submit(client, h, sid, hid)
    assert res["advice"]["outcome"] == "wait_in_queue", res
    r = client.post("/booking/finalize", json={"hold_id": hid, "intake_id": res["intake_id"]}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["appointment"]


def entry_id_for(appointment_id: int) -> int:
    from app.models import QueueEntryRow
    with Session(get_engine()) as db:
        return db.exec(select(QueueEntryRow).where(QueueEntryRow.appointment_id == appointment_id)).first().id
