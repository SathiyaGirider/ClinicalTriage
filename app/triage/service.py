from datetime import datetime

from app.triage.rules import check_red_flags
from app.triage.llm_classifier import classify_with_llm
from app.triage.escalation import apply_escalation
from app.common.schemas import IntakeResult, TriageDecision


def triage(intake_result: IntakeResult) -> TriageDecision:

    symptoms = intake_result.symptoms
    age = intake_result.age
    flag = check_red_flags(symptoms, age)

    if flag:
        return TriageDecision(
            patient_id=intake_result.patient_id,
            priority="emergency",
            red_flags_matched=[flag],
            decided_by="rule",
            confidence="high",
            escalation_required=True,
            priority_rationale=f"Emergency priority due to a serious warning sign: {flag.replace('_', ' ')}",
            timestamp=datetime.now().isoformat()
        )

    try:
        priority, llm_confidence, reason = classify_with_llm(intake_result)
        needs_escalation = apply_escalation(intake_result, llm_confidence)
        decided_by = "llm"

    except RuntimeError:
        # LLM call failed (bad key, network issue, malformed response, etc.)
        # Fail SAFE: don't guess, escalate to a human instead
        priority = "same-day"          # safer default than "routine" when unsure
        llm_confidence = "low"
        reason = "Automated classification unavailable — escalated for manual review."
        needs_escalation = True
        decided_by = "llm"

    return TriageDecision(
        patient_id=intake_result.patient_id,
        priority=priority,
        red_flags_matched=[],
        decided_by=decided_by,
        confidence=llm_confidence,
        escalation_required=needs_escalation,
        priority_rationale=reason,
        timestamp=datetime.now().isoformat()
    )