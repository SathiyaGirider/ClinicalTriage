"""
Escalation logic — decides whether a triage case needs human review,
independent of what priority (Emergency/Same-day/Routine) was assigned.

Escalation can be triggered by:
1. Unclear patient input at intake (input_confidence == "low")
2. The LLM itself being unsure of its classification (llm_confidence == "low")
"""

from app.common.schemas import IntakeResult

def apply_escalation(intake_result: IntakeResult, llm_confidence: str) -> bool:
    """
    Returns True if the case needs human review (escalated),
    False otherwise.
    """

    # 1. If input was unclear at the intake stage → escalate
    if intake_result.input_confidence == "low":
        return True

    # 2. If the LLM itself was unsure → escalate
    if llm_confidence == "low":
        return True

    return False