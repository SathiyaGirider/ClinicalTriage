import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.common.schemas import DoctorSummary, IntakeResult, TriageDecision

PRIORITY_LABELS = {
    "emergency": "EMERGENCY",
    "same-day": "SAME-DAY",
    "routine": "ROUTINE",
}


def build_doctor_summary(intake: IntakeResult, triage: TriageDecision) -> DoctorSummary:
    if intake.patient_id != triage.patient_id:
        raise ValueError(
            "Patient ID mismatch: "
            f"intake={intake.patient_id!r}, triage={triage.patient_id!r}"
        )

    return DoctorSummary(
        patient_id=triage.patient_id,
        chief_complaint=intake.chief_complaint,
        duration=intake.duration,
        red_flags=list(triage.red_flags_matched),
        relevant_history=list(intake.known_conditions),
        priority=triage.priority,
        priority_rationale=triage.priority_rationale,
        timestamp=triage.timestamp,
    )


def render_dashboard(summary: DoctorSummary) -> str:
    return "\n".join(
        [
            f"Patient: {summary.patient_id}",
            "",
            "Chief complaint:",
            summary.chief_complaint,
            "",
            "Duration:",
            summary.duration,
            "",
            "Red flags:",
            format_list(summary.red_flags),
            "",
            "Relevant history:",
            format_list(summary.relevant_history),
            "",
            "Priority:",
            PRIORITY_LABELS[summary.priority],
            "",
            "Why:",
            summary.priority_rationale,
        ]
    )


def format_list(items: list[str]) -> str:
    return "\n".join(items) if items else "None"