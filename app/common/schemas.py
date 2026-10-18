from pydantic import BaseModel, Field
from typing import Optional, Literal


# Shared contracts between the modules. The original fields (A -> B -> C) are
# unchanged; every addition is optional with a default and listed in
# docs/schema.md so older payloads and the 8 mock scenarios still validate.

Priority = Literal["emergency", "same-day", "routine"]
PRIORITY_RANK = {"routine": 0, "same-day": 1, "emergency": 2}


def max_priority(a: str, b: str) -> str:
    return a if PRIORITY_RANK[a] >= PRIORITY_RANK[b] else b


# ============================================================
# A → B
# INTAKE RESULT
# ============================================================

class IntakeAddendum(BaseModel):
    """Short re-check (check-in "worse"/"new symptom") merged into an intake."""
    ts: str
    change: Literal["worse", "new_symptom", "better", "none"] = "worse"
    text: str = ""
    answers: dict[str, str] = Field(default_factory=dict)
    symptom_tags: list[str] = Field(default_factory=list)
    source: Literal["patient", "nurse"] = "patient"


class IntakeResult(BaseModel):
    patient_id: str

    chief_complaint: str
    duration: str
    symptoms: list[str]

    age: Optional[int] = None
    known_conditions: list[str] = Field(default_factory=list)

    follow_up_answers: dict[str, str] = Field(default_factory=dict)

    raw_transcript: str

    input_confidence: Literal["high", "medium", "low"]

    # --- additions (LifeLine) ---
    symptom_tags: list[str] = Field(default_factory=list)
    safety_screen: list[str] = Field(default_factory=list)
    language: Literal["en", "ta"] = "en"
    assisted: bool = False
    addenda: list[IntakeAddendum] = Field(default_factory=list)


# ============================================================
# B → C
# TRIAGE DECISION
# ============================================================

class TriageDecision(BaseModel):
    patient_id: str

    priority: Priority

    red_flags_matched: list[str] = Field(default_factory=list)

    decided_by: Literal["rule", "llm", "rule+llm", "fallback", "human"]

    confidence: Literal["high", "medium", "low"]

    escalation_required: bool

    priority_rationale: str

    timestamp: str

    # --- additions (LifeLine) ---
    flag_for_nurse: bool = False
    audit_notes: list[str] = Field(default_factory=list)
    suggested_department: Optional[str] = None
    rule_tier: Optional[Literal["emergency", "urgent"]] = None


# ============================================================
# A + B → C
# DOCTOR SUMMARY
# ============================================================

class DoctorSummary(BaseModel):
    patient_id: str

    chief_complaint: str
    duration: str

    red_flags: list[str] = Field(default_factory=list)
    relevant_history: list[str] = Field(default_factory=list)

    priority: Priority

    priority_rationale: str

    timestamp: str

    # --- additions (LifeLine) ---
    decided_by: Optional[str] = None
    audit_notes: list[str] = Field(default_factory=list)
    input_confidence: Optional[str] = None
    summary_source: Literal["template", "llm"] = "template"


# ============================================================
# Patient-facing advice (never shows priority or anything diagnostic)
# ============================================================

class PatientAdvice(BaseModel):
    outcome: Literal["wait_in_queue", "staff_will_check_on_you", "seek_emergency_now"]
    title: str
    message: str
    language: Literal["en", "ta"] = "en"
    suggested_department: Optional[str] = None
    department_text: Optional[str] = None
    intake_id: Optional[int] = None
    emergency_numbers: list[str] = Field(default_factory=list)


class DoctorRecommendation(BaseModel):
    doctor_id: int
    name: str
    specialty: str
    hospital_id: int
    hospital_name: str
    area: str
    distance_km: Optional[float] = None
    next_session: Optional[dict] = None


class QueueEntry(BaseModel):
    id: int
    appointment_id: int
    patient_id: int
    patient_name: str
    doctor_id: int
    date: str
    session_label: Optional[str] = None
    token_number: Optional[int] = None
    token_label: Optional[str] = None
    appointment_type: str
    presence: str
    status: str
    flagged: bool = False
    flag_source: Optional[str] = None
    flag_reason: Optional[str] = None
    acknowledged: bool = False
    alert_state: Literal["none", "normal", "amber", "red"] = "none"
    checkin_change: Optional[str] = None
    check_in_ts: Optional[str] = None
    late_arrival: bool = False
    fast_tracked: bool = False
    nurse_position: Optional[int] = None
    waiting_seconds: Optional[int] = None
    chief_complaint: Optional[str] = None
    priority: Optional[str] = None
    priority_rationale: Optional[str] = None
    decided_by: Optional[str] = None
    red_flags: list[str] = Field(default_factory=list)
    rule_based: bool = False
    audit_notes: list[str] = Field(default_factory=list)
