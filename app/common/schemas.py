from pydantic import BaseModel, Field
from typing import Optional, Literal


# ============================================================
# A → B
# INTAKE RESULT
# ============================================================

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


# ============================================================
# B → C
# TRIAGE DECISION
# ============================================================

class TriageDecision(BaseModel):
    patient_id: str

    priority: Literal["emergency", "same-day", "routine"]

    red_flags_matched: list[str] = Field(default_factory=list)

    decided_by: Literal["rule", "llm", "rule+llm"]

    confidence: Literal["high", "medium", "low"]

    escalation_required: bool

    priority_rationale: str

    timestamp: str


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

    priority: Literal["emergency", "same-day", "routine"]

    priority_rationale: str

    timestamp: str