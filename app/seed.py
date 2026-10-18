"""
Demo seed data. ALL PEOPLE, HOSPITALS AND RECORDS HERE ARE FAKE (synthetic).

    SEED_DEMO=true python -m app.seed            # seed an empty database
    SEED_DEMO=true python -m app.seed --reset    # drop all tables first

Passwords: SEED_PASSWORD from env, otherwise one random password is generated
and printed once.
"""

from __future__ import annotations

import argparse
import json
import random
import secrets
import sys
from datetime import date, datetime, timedelta

from sqlmodel import Session, SQLModel, select

from app.auth.security import UNUSABLE_PASSWORD, hash_password
from app.common import timeutil
from app.common.ids import token_label
from app.common.schemas import IntakeResult, TriageDecision
from app.config import settings
from app.db import get_engine, init_db
from app.models import (Appointment, ClinicSession, Doctor, Encounter, Hospital, IntakeRecord, Patient, Prescription,
                        QueueEntryRow, TriageDecisionRow, User)
from app.triage.summary import template_summary

HOSPITALS = [
    dict(name="LifeLine Adyar Hospital (demo)", area="Adyar", address="12 Demo Main Road, Adyar, {city} 600020 (demo address)",
         lat=13.0012, lon=80.2565, opd_hours="Mon-Sat 09:00-17:00", walk_in_window_text="Walk-in OPD: 08:30-11:30 and 14:00-16:00",
         er_phone="044-0000-1001 (demo)", er_note="Emergency department open 24x7 at the east gate (demo)."),
    dict(name="Marina Care Hospital (demo)", area="Mylapore", address="45 Sample Street, Mylapore, {city} 600004 (demo address)",
         lat=13.0339, lon=80.2619, opd_hours="Mon-Sat 09:00-17:00", walk_in_window_text="Walk-in OPD: 09:00-12:00",
         er_phone="044-0000-2002 (demo)", er_note="Emergency entrance on the beach road side (demo)."),
    dict(name="Anna Nagar City Hospital (demo)", area="Anna Nagar", address="7 Example Avenue, Anna Nagar, {city} 600040 (demo address)",
         lat=13.0850, lon=80.2101, opd_hours="Mon-Sun 08:00-18:00", walk_in_window_text="Walk-in OPD: 08:00-12:00 and 15:00-17:00",
         er_phone="044-0000-3003 (demo)", er_note="Emergency department next to the main lobby (demo)."),
]

SPECIALTY_MINUTES = {"General Medicine": 8, "Cardiology": 12, "Neurology": 15, "Orthopaedics": 10, "ENT": 8, "Paediatrics": 10,
                     "Gynaecology": 12, "Dermatology": 8}

FIRST = ["Meena", "Arjun", "Kavitha", "Suresh", "Lakshmi", "Prakash", "Divya", "Karthik", "Revathi", "Vijay", "Anitha", "Ganesh",
         "Nithya", "Ramesh", "Sangeetha", "Harish", "Deepa", "Senthil", "Gayathri", "Balaji", "Priyanka", "Mohan", "Shalini", "Ashok"]
LAST = ["Raghavan", "Iyer", "Subramanian", "Natarajan", "Krishnan", "Venkatesh", "Sundaram", "Balan", "Murugan", "Pillai",
        "Chandran", "Rajan"]

# Doctors with login accounts: (hospital index, specialty, email local part)
DOCTOR_ACCOUNTS = [
    (0, "General Medicine", "dr.gm.adyar"), (0, "Cardiology", "dr.cardio.adyar"), (0, "Dermatology", "dr.derm.adyar"),
    (0, "Paediatrics", "dr.paeds.adyar"), (0, "Neurology", "dr.neuro.adyar"), (1, "General Medicine", "dr.gm.mylapore"),
]
DOMAIN = "example.com"

FILLER_COMPLAINTS = [
    ("cough and mild fever for two days", ["cough", "fever"], "2 days"),
    ("knee pain when climbing stairs", ["joint_pain"], "3 weeks"),
    ("itchy rash on both arms", ["rash", "itching"], "1 week"),
    ("follow-up for blood sugar", ["other"], "routine follow-up"),
    ("ear pain since yesterday", ["ear_problem"], "1 day"),
    ("lower back pain after lifting", ["back_pain"], "4 days"),
]


def _password() -> tuple[str, bool]:
    if settings.seed_password:
        return settings.seed_password, False
    return secrets.token_urlsafe(9), True


def _sessions_for(db: Session, doc: Doctor, day: date, rng: random.Random, filler: list[int], issue_today: bool) -> None:
    for label, win in (("morning", settings.morning_window), ("afternoon", settings.afternoon_window)):
        start, end = win.split("-")
        if day == timeutil.today() and label == "afternoon" and timeutil.now().time() >= timeutil.parse_hhmm(end):
            # Demo convenience: seeding after today's sessions ended keeps today's afternoon open until late.
            end = "23:30"
        minutes = (datetime.combine(day, timeutil.parse_hhmm(end)) - datetime.combine(day, timeutil.parse_hhmm(start))).seconds // 60
        max_tokens = max(4, minutes // doc.consult_minutes)
        s = ClinicSession(doctor_id=doc.id, date=day, label=label, window_start=start, window_end=end, max_tokens=max_tokens,
                          reserved_urgent=min(settings.reserved_urgent, max_tokens // 4))
        db.add(s)
        db.flush()
        # Some tokens already issued so numbers look realistic (always leaves open + reserved tokens).
        issued = rng.randint(1, min(6, max(1, (max_tokens - s.reserved_urgent) // 3)))
        if day == timeutil.today() and not issue_today:
            issued = 0
        for _ in range(issued):
            pid = rng.choice(filler)
            n = s.next_token_seq
            s.next_token_seq += 1
            appt = Appointment(patient_id=pid, doctor_id=doc.id, hospital_id=doc.hospital_id, session_id=s.id, date=day,
                               token_number=n, token_label=token_label(label, n), type="booked", status="booked")
            db.add(appt)
            db.flush()
            if day == timeutil.today():
                text, tags, dur = rng.choice(FILLER_COMPLAINTS)
                intake = IntakeResult(patient_id=str(pid), chief_complaint=text, duration=dur, symptoms=[t.replace("_", " ") for t in tags],
                                      raw_transcript=text, input_confidence="medium", symptom_tags=tags, safety_screen=["none"])
                rec = IntakeRecord(patient_id=pid, appointment_id=appt.id, intake_json=intake.model_dump_json())
                db.add(rec)
                db.flush()
                d = TriageDecision(patient_id=str(pid), priority="routine", decided_by="llm", confidence="medium", escalation_required=False,
                                   priority_rationale="Seeded demo booking: mild, stable symptoms.", timestamp=timeutil.now().isoformat(),
                                   audit_notes=["seed_data"], suggested_department=doc.specialty)
                db.add(TriageDecisionRow(intake_id=rec.id, decision_json=d.model_dump_json()))
                from app.models import SummaryRow
                db.add(SummaryRow(intake_id=rec.id, summary_json=template_summary(intake, d).model_dump_json()))
                appt.intake_id = rec.id
            db.add(QueueEntryRow(appointment_id=appt.id, doctor_id=doc.id, session_id=s.id, session_label=label, date=day,
                                 token_number=n, token_label=appt.token_label))
        db.add(s)


def seed(db: Session) -> dict:
    rng = random.Random(42)
    password, generated = _password()
    pw_hash = hash_password(password)
    city = settings.demo_city
    hospitals = []
    for h in HOSPITALS:
        row = Hospital(**{**h, "address": h["address"].format(city=city)})
        db.add(row)
        hospitals.append(row)
    db.flush()

    # 24 doctors: every specialty at every hospital. Fake names.
    doctors: dict[tuple[int, str], Doctor] = {}
    i = 0
    for hi, h in enumerate(hospitals):
        for spec, minutes in SPECIALTY_MINUTES.items():
            name = f"Dr. {FIRST[i % len(FIRST)]} {LAST[(i * 7) % len(LAST)]}"
            d = Doctor(hospital_id=h.id, name=name, specialty=spec, area=h.area, lat=h.lat + rng.uniform(-0.004, 0.004),
                       lon=h.lon + rng.uniform(-0.004, 0.004), consult_minutes=minutes,
                       bio=f"{spec} (synthetic demo profile).")
            db.add(d)
            doctors[(hi, spec)] = d
            i += 1
    db.flush()

    accounts = []
    for hi, spec, local in DOCTOR_ACCOUNTS:
        d = doctors[(hi, spec)]
        u = User(email=f"{local}@{DOMAIN}", password_hash=pw_hash, role="doctor", full_name=d.name, hospital_id=d.hospital_id)
        db.add(u)
        db.flush()
        d.user_id = u.id
        db.add(d)
        accounts.append(("doctor", u.email, f"{d.name}, {spec}, {hospitals[hi].name}"))
    for hi, local in ((0, "nurse.adyar"), (1, "nurse.mylapore")):
        u = User(email=f"{local}@{DOMAIN}", password_hash=pw_hash, role="nurse", full_name=f"Nurse {FIRST[hi + 10]} (demo)",
                 hospital_id=hospitals[hi].id)
        db.add(u)
        accounts.append(("nurse", u.email, hospitals[hi].name))

    patients = []
    for email, name, age, lang, area, consent, (lat, lon) in [
        ("asha", "Asha Kumar (demo)", "34", "en", "Adyar", True, (13.004, 80.255)),
        ("ravi", "Ravi Shankar (demo)", "67", "ta", "Mylapore", False, (13.033, 80.268)),
        ("priya", "Priya Selvam (demo)", "25", "en", "Anna Nagar", False, (13.087, 80.212)),
    ]:
        u = User(email=f"{email}@{DOMAIN}", password_hash=pw_hash, role="patient", full_name=name)
        db.add(u)
        db.flush()
        db.add(Patient(user_id=u.id, dob_or_age=age, language=lang, area=area, lat=lat, lon=lon, share_history_consent=consent))
        patients.append(u)
        accounts.append(("patient", u.email, f"{name}, consent {'ON' if consent else 'OFF'}"))

    filler = []
    for k in range(10):
        u = User(email=f"filler{k}@walkin.invalid", password_hash=UNUSABLE_PASSWORD, role="patient", full_name=f"Demo Patient {k + 1}")
        db.add(u)
        db.flush()
        db.add(Patient(user_id=u.id, dob_or_age=str(rng.randint(18, 75)), language=rng.choice(["en", "ta"]), area=rng.choice(["Adyar", "Mylapore"])))
        filler.append(u.id)
    db.flush()

    # Prior encounters (doctor-written, synthetic). Asha: two doctors, consent ON. Ravi: two doctors, consent OFF.
    today = timeutil.today()
    prior = [
        (patients[0], doctors[(0, "Cardiology")], 95, "Palpitations, benign (doctor's assessment)", "R00.2",
         "ECG normal. Advised to limit caffeine. Review if recurs.", [{"drug": "Propranolol", "dose": "10 mg", "frequency": "when needed, max twice daily", "duration": "2 weeks", "instructions": "Only if palpitations are bothersome."}]),
        (patients[0], doctors[(1, "General Medicine")], 40, "Viral fever", "B34.9", "Fever 3 days, no warning signs. Fluids and rest.",
         [{"drug": "Paracetamol", "dose": "500 mg", "frequency": "every 6 hours if fever", "duration": "3 days", "instructions": "After food."}]),
        (patients[1], doctors[(0, "General Medicine")], 60, "Type 2 diabetes, review", "E11.9", "HbA1c 7.8. Diet counselling done.",
         [{"drug": "Metformin", "dose": "500 mg", "frequency": "twice daily", "duration": "3 months", "instructions": "With meals."}]),
        (patients[1], doctors[(0, "Neurology")], 20, "Tension-type headache", "G44.2", "Normal neuro exam. Sleep hygiene discussed.",
         [{"drug": "Ibuprofen", "dose": "400 mg", "frequency": "when needed", "duration": "5 days", "instructions": "After food. Not more than 3 a day."}]),
    ]
    for pat, doc, days_ago, dx, code, notes, items in prior:
        day = today - timedelta(days=days_ago)
        appt = Appointment(patient_id=pat.id, doctor_id=doc.id, hospital_id=doc.hospital_id, date=day, token_number=3,
                           token_label="M-03", type="booked", status="completed")
        db.add(appt)
        db.flush()
        enc = Encounter(patient_id=pat.id, doctor_id=doc.id, appointment_id=appt.id, date=day, diagnosis_text=dx, diagnosis_code=code,
                        clinical_notes=notes)
        db.add(enc)
        db.flush()
        db.add(Prescription(encounter_id=enc.id, items_json=json.dumps(items)))

    # Sessions: today + next 6 days for every doctor; today's filler tokens only for the account doctors.
    account_doc_ids = {doctors[(hi, spec)].id for hi, spec, _ in DOCTOR_ACCOUNTS}
    for doc in doctors.values():
        for k in range(7):
            _sessions_for(db, doc, today + timedelta(days=k), rng, filler, issue_today=doc.id in account_doc_ids)
    db.commit()
    return {"password": password, "generated": generated, "accounts": accounts}


def seed_if_empty(verbose: bool = True) -> dict | None:
    init_db()
    with Session(get_engine()) as db:
        if db.exec(select(Hospital)).first():
            return None
        out = seed(db)
    if verbose:
        print_accounts(out)
    return out


def print_accounts(out: dict) -> None:
    print("\nLifeLine demo data seeded (SYNTHETIC). Demo logins:")
    for role, email, note in out["accounts"]:
        print(f"  {role:8s} {email:32s} {note}")
    if out["generated"]:
        print(f"\n  Password for every demo account (shown once): {out['password']}")
        print("  Set SEED_PASSWORD in .env to choose your own.\n")
    else:
        print("\n  Password: the SEED_PASSWORD value from your environment.\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reset", action="store_true", help="drop and recreate all tables first")
    args = ap.parse_args(argv)
    if not settings.seed_demo:
        print("Refusing to seed: set SEED_DEMO=true (demo data is synthetic and for local use only).")
        return 1
    if args.reset:
        import app.models  # noqa: F401
        SQLModel.metadata.drop_all(get_engine())
    out = seed_if_empty(verbose=True)
    if out is None:
        print("Database already has data; use --reset to start over.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
