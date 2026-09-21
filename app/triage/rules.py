"""
Hardcoded red-flag detection rules, based on the ESI (Emergency Severity Index)
triage framework, collapsed into a 3-tier system (Emergency/Same-day/Routine).

This is a deterministic rule layer — no AI involved. It runs BEFORE any LLM
call in the triage pipeline, and its decisions cannot be overridden by the LLM.

Matching is substring-based (not exact match), since real patient symptom
text is messy (e.g. "difficulty breathing (airway compromise)" should still
match "difficulty breathing").
"""


def _matches(symptoms: list[str], phrase: str) -> bool:
    """Return True if `phrase` appears as a substring in any symptom string."""
    return any(phrase in s for s in symptoms)


def check_red_flags(symptoms: list[str], age: int | None = None) -> str | None:
    """
    symptoms = list of words/phrases from the patient, e.g.
    ["chest pain", "shortness of breath", "fever"]
    age = patient's age, if known (used for pediatric-specific rules)

    Returns the matched red flag name if found, else None.
    """

    symptoms = [s.lower() for s in symptoms]  # avoid "Fever" vs "fever" mismatches

    # 1. Cardiac / breathing emergency
    if _matches(symptoms, "chest pain") and _matches(symptoms, "shortness of breath"):
        return "chest_pain_with_breathlessness"

    # 2. Not breathing properly at all
    if _matches(symptoms, "difficulty breathing") or _matches(symptoms, "gasping"):
        return "respiratory_distress"

    # 3. Unconscious / unresponsive
    if _matches(symptoms, "unconscious") or _matches(symptoms, "unresponsive"):
        return "unresponsive"

    # 4. Stroke signs
    if (
        _matches(symptoms, "slurred speech")
        or _matches(symptoms, "face drooping")
        or _matches(symptoms, "facial drooping")
        or _matches(symptoms, "one-sided weakness")
    ):
        return "stroke_signs"

    # 5. Uncontrolled bleeding
    if _matches(symptoms, "heavy bleeding") or _matches(symptoms, "uncontrolled bleeding"):
        return "severe_bleeding"

    # 6. Severe allergic reaction
    if (
        _matches(symptoms, "throat swelling") or _matches(symptoms, "difficulty swallowing")
    ) and _matches(symptoms, "rash"):
        return "anaphylaxis"

    # 7. Active seizure right now
    if _matches(symptoms, "seizure") and _matches(symptoms, "ongoing"):
        return "active_seizure"

    # 7b. Recent/resolved seizure in a child — still a red flag, different rule
    if _matches(symptoms, "seizure") and age is not None and age < 18:
        return "pediatric_seizure"

    # 8. Major trauma
    if _matches(symptoms, "head injury") or _matches(symptoms, "severe accident"):
        return "major_trauma"

    # 9. Suspected poisoning/overdose
    if _matches(symptoms, "poisoning") or _matches(symptoms, "overdose"):
        return "poisoning"

    # 10. Abdominal pain + fainting (possible internal bleeding)
    if _matches(symptoms, "abdominal pain") and _matches(symptoms, "fainting"):
        return "abdominal_pain_with_instability"

    return None  # no red flag matched, safe to let the LLM decide