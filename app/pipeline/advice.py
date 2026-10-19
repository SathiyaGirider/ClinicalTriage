"""
Fixed, localised, NON-diagnostic patient advice. The patient never sees a
priority label, score, rationale, or anything that names a condition.
Tamil wording needs review by a native speaker (docs/DEMO_SCRIPT.md).
"""

from app.common.schemas import PatientAdvice, TriageDecision
from app.config import settings

OUTCOME_ROUTINE = "wait_in_queue"
OUTCOME_CONCERNING = "staff_will_check_on_you"
OUTCOME_EMERGENCY = "seek_emergency_now"

TEXT = {
    OUTCOME_ROUTINE: {
        "en": ("Your booking can go ahead", "Please come during your session. The app shows which token is being served."),
        "ta": ("உங்கள் முன்பதிவைத் தொடரலாம்", "உங்கள் அமர்வு நேரத்தில் வாருங்கள். எந்த டோக்கன் அழைக்கப்படுகிறது என்பதை ஆப் காட்டும்."),
    },
    OUTCOME_CONCERNING: {
        "en": ("Please visit the hospital today", "From your answers, a nurse should check on you today. Tell the front desk a nurse should check you first."),
        "ta": ("இன்றே மருத்துவமனைக்கு வாருங்கள்", "உங்கள் பதில்களின்படி, இன்று ஒரு செவிலியர் உங்களைப் பார்க்க வேண்டும். முதலில் செவிலியர் பார்க்க வேண்டும் என்று வரவேற்பில் சொல்லுங்கள்."),
    },
    OUTCOME_EMERGENCY: {
        "en": ("Please go to the Emergency department now.", "Do not wait for an appointment. If you cannot travel safely, call an emergency number now."),
        "ta": ("உடனே அவசர சிகிச்சைப் பிரிவுக்குச் செல்லுங்கள்.", "முன்பதிவுக்காகக் காத்திருக்க வேண்டாம். பாதுகாப்பாகப் பயணிக்க முடியாவிட்டால், உடனே அவசர எண்ணை அழையுங்கள்."),
    },
}
DEPT_TEXT = {"en": "This kind of problem is usually seen by: {dept}", "ta": "இந்த வகை பிரச்சனையை வழக்கமாகப் பார்ப்பவர்: {dept}"}


def outcome_for(decision: TriageDecision) -> str:
    if decision.priority == "emergency":
        return OUTCOME_EMERGENCY
    if decision.priority == "same-day" or decision.escalation_required:
        return OUTCOME_CONCERNING
    return OUTCOME_ROUTINE


def make_advice(decision: TriageDecision, language: str, intake_id: int | None = None) -> PatientAdvice:
    lang = "ta" if language == "ta" else "en"
    outcome = outcome_for(decision)
    title, message = TEXT[outcome][lang]
    dept = decision.suggested_department if outcome != OUTCOME_EMERGENCY else None
    return PatientAdvice(
        outcome=outcome, title=title, message=message, language=lang, suggested_department=dept,
        department_text=DEPT_TEXT[lang].format(dept=dept) if dept else None, intake_id=intake_id,
        emergency_numbers=settings.emergency_numbers if outcome == OUTCOME_EMERGENCY else [],
    )
