"""
SQLite tables (SQLModel). Names follow docs/BUILD_PLAN.md section 7.
JSON payloads (IntakeResult, TriageDecision, DoctorSummary) are stored as text.
"""

import datetime as dt
from datetime import datetime
from typing import Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, SQLModel

from app.common import timeutil


def _now() -> datetime:
    return timeutil.now()


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    role: str  # patient | nurse | doctor
    full_name: str
    hospital_id: Optional[int] = Field(default=None, foreign_key="hospitals.id")  # staff only
    created_at: NaiveDatetime = Field(default_factory=_now)


class Patient(SQLModel, table=True):
    __tablename__ = "patients"
    user_id: int = Field(primary_key=True, foreign_key="users.id")
    dob_or_age: Optional[str] = None
    language: str = "en"
    area: Optional[str] = None
    lat: Optional[float] = None
    share_history_consent: bool = False  # Legacy fallback; superseded by ConsentRequest in Phase 3B
    is_walk_in: bool = False
    abha_address: Optional[str] = None  # Synthetic simulation e.g. asha@abdm (never real IDs)


class Hospital(SQLModel, table=True):
    __tablename__ = "hospitals"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    area: str
    address: str
    lat: float
    lon: float
    opd_hours: str
    walk_in_window_text: str
    er_phone: str
    er_note: str = ""


class Doctor(SQLModel, table=True):
    __tablename__ = "doctors"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    hospital_id: int = Field(foreign_key="hospitals.id")
    name: str
    specialty: str = Field(index=True)
    area: str
    lat: float
    lon: float
    consult_minutes: int = 8
    bio: str = ""
    room: str = Field(default="Room 1")


class NurseAssignment(SQLModel, table=True):
    __tablename__ = "nurse_assignments"
    id: Optional[int] = Field(default=None, primary_key=True)
    nurse_id: int = Field(foreign_key="users.id", unique=True, index=True)
    doctor_id: int = Field(foreign_key="doctors.id", unique=True, index=True)
    created_at: NaiveDatetime = Field(default_factory=_now)


class ClinicSession(SQLModel, table=True):
    __tablename__ = "sessions"
    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="doctors.id", index=True)
    date: dt.date = Field(index=True)
    label: str  # morning | afternoon
    window_start: str  # "09:00"
    window_end: str
    max_tokens: int
    reserved_urgent: int = 2
    next_token_seq: int = 1
    status: str = "open"  # open | closed


class BookingHold(SQLModel, table=True):
    __tablename__ = "booking_holds"
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="sessions.id", index=True)
    patient_id: int = Field(foreign_key="users.id")
    held_until: NaiveDatetime
    released: bool = False
    finalized: bool = False


class Appointment(SQLModel, table=True):
    __tablename__ = "appointments"
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="users.id", index=True)
    doctor_id: int = Field(foreign_key="doctors.id", index=True)
    hospital_id: int = Field(foreign_key="hospitals.id")
    session_id: Optional[int] = Field(default=None, foreign_key="sessions.id")
    date: dt.date
    token_number: Optional[int] = None
    token_label: Optional[str] = None
    est_call_from: Optional[NaiveDatetime] = None
    est_call_to: Optional[NaiveDatetime] = None
    type: str = "booked"  # booked | same_day | walk_in
    status: str = "booked"  # booked|expected_today|checked_in|with_doctor|completed|cancelled|no_show|escalated
    intake_id: Optional[int] = Field(default=None, foreign_key="intake_records.id")
    created_at: NaiveDatetime = Field(default_factory=_now)


class IntakeRecord(SQLModel, table=True):
    __tablename__ = "intake_records"
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="users.id", index=True)
    appointment_id: Optional[int] = None
    intake_json: str
    created_at: NaiveDatetime = Field(default_factory=_now)


class IntakeSessionRow(SQLModel, table=True):
    """Adaptive question flow state (app/intake/session.py)."""
    __tablename__ = "intake_sessions"
    id: str = Field(primary_key=True)
    patient_id: int = Field(foreign_key="users.id")
    created_by: int = Field(foreign_key="users.id")
    mode: str = "booking"  # booking | symptom_first | assisted | recheck
    state_json: str
    intake_id: Optional[int] = None
    created_at: NaiveDatetime = Field(default_factory=_now)


class TriageDecisionRow(SQLModel, table=True):
    __tablename__ = "triage_decisions"
    id: Optional[int] = Field(default=None, primary_key=True)
    intake_id: int = Field(foreign_key="intake_records.id", index=True)
    decision_json: str
    created_at: NaiveDatetime = Field(default_factory=_now)


class SummaryRow(SQLModel, table=True):
    __tablename__ = "summaries"
    id: Optional[int] = Field(default=None, primary_key=True)
    intake_id: int = Field(foreign_key="intake_records.id", index=True)
    summary_json: str


class QueueEntryRow(SQLModel, table=True):
    __tablename__ = "queue_entries"
    id: Optional[int] = Field(default=None, primary_key=True)
    appointment_id: int = Field(foreign_key="appointments.id", index=True)
    doctor_id: int = Field(foreign_key="doctors.id", index=True)
    session_id: Optional[int] = Field(default=None, foreign_key="sessions.id")
    session_label: Optional[str] = None
    date: dt.date = Field(index=True)
    token_number: Optional[int] = None
    token_label: Optional[str] = None
    presence: str = "booked_not_arrived"  # booked_not_arrived|self_reported_arrived|present|called_absent
    checked_in_by: Optional[int] = None
    check_in_ts: Optional[NaiveDatetime] = None
    self_reported_ts: Optional[NaiveDatetime] = None
    checkin_change: Optional[str] = None  # none|better|worse|new_symptom
    status: str = "waiting"  # waiting|fast_tracked|sent_to_er|with_doctor|done|no_show
    flagged: bool = False
    flag_source: Optional[str] = None  # ai | nurse
    flag_reason: Optional[str] = None
    flagged_at: Optional[NaiveDatetime] = None
    acknowledged_at: Optional[NaiveDatetime] = None
    nurse_position: Optional[int] = None
    late_arrival: bool = False
    fast_tracked_at: Optional[NaiveDatetime] = None
    called_at: Optional[NaiveDatetime] = None
    done_at: Optional[NaiveDatetime] = None


class QueueOrderMode(SQLModel, table=True):
    __tablename__ = "queue_order_modes"
    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="doctors.id")
    date: dt.date
    session_label: str
    mode: str = "token"  # token | nurse


class Vitals(SQLModel, table=True):
    __tablename__ = "vitals"
    id: Optional[int] = Field(default=None, primary_key=True)
    queue_entry_id: int = Field(foreign_key="queue_entries.id", index=True)
    bp_sys: Optional[int] = None
    bp_dia: Optional[int] = None
    temp_c: Optional[float] = None
    spo2: Optional[int] = None
    pulse: Optional[int] = None
    entered_by: int = Field(foreign_key="users.id")
    ts: NaiveDatetime = Field(default_factory=_now)


class ActionLog(SQLModel, table=True):
    __tablename__ = "action_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    actor_user_id: Optional[int] = None
    actor_role: str
    patient_id: Optional[int] = None
    action: str
    original_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: Optional[str] = None
    hospital_id: Optional[int] = None
    ts: NaiveDatetime = Field(default_factory=_now)


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    viewer_user_id: int
    patient_id: int = Field(index=True)
    scope: str
    ts: NaiveDatetime = Field(default_factory=_now)


class Encounter(SQLModel, table=True):
    __tablename__ = "encounters"
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="users.id", index=True)
    doctor_id: int = Field(foreign_key="doctors.id")
    appointment_id: Optional[int] = Field(default=None, foreign_key="appointments.id")
    date: dt.date
    diagnosis_text: str
    diagnosis_code: Optional[str] = None
    clinical_notes: str = ""
    follow_up_date: Optional[dt.date] = None
    created_at: NaiveDatetime = Field(default_factory=_now)


class Prescription(SQLModel, table=True):
    __tablename__ = "prescriptions"
    id: Optional[int] = Field(default=None, primary_key=True)
    encounter_id: int = Field(foreign_key="encounters.id", index=True)
    items_json: str
    created_at: NaiveDatetime = Field(default_factory=_now)


# ===========================================================================
# Phase 3B: ABDM Simulation Models & Staff Feedback
# ===========================================================================

class ConsentRequest(SQLModel, table=True):
    """
    ABDM Consent Request Artefact (SIMULATION).
    Replaces permanent boolean share_history_consent.
    Statuses: REQUESTED | GRANTED | DENIED | REVOKED | EXPIRED
    """
    __tablename__ = "consent_requests"
    id: Optional[int] = Field(default=None, primary_key=True)
    doctor_id: int = Field(foreign_key="doctors.id", index=True)
    hospital_id: int = Field(foreign_key="hospitals.id")
    patient_id: int = Field(foreign_key="users.id", index=True)
    purpose: str = "Care and treatment"
    hi_types_json: str = '["OPConsultNote", "Prescription"]'
    date_from: dt.date
    date_to: dt.date
    duration_hours: int = 24
    expires_at: Optional[NaiveDatetime] = None
    status: str = "REQUESTED"
    created_at: NaiveDatetime = Field(default_factory=_now)
    updated_at: NaiveDatetime = Field(default_factory=_now)


class ConsentStatusHistory(SQLModel, table=True):
    """Append-only audit trail of consent status transitions."""
    __tablename__ = "consent_status_history"
    id: Optional[int] = Field(default=None, primary_key=True)
    consent_request_id: int = Field(foreign_key="consent_requests.id", index=True)
    status: str
    actor_user_id: int
    actor_role: str
    note: Optional[str] = None
    created_at: NaiveDatetime = Field(default_factory=_now)


class SummaryFeedback(SQLModel, table=True):
    """One-tap staff feedback control for AI triage summaries."""
    __tablename__ = "summary_feedback"
    id: Optional[int] = Field(default=None, primary_key=True)
    summary_id: int = Field(foreign_key="summaries.id", index=True)
    user_id: int = Field(foreign_key="users.id")
    role: str
    useful: bool
    reason: Optional[str] = None
    rules_version: str = "1.0"
    prompt_version: str = "1.0"
    created_at: NaiveDatetime = Field(default_factory=_now)

