"""
Deterministic Input Confidence Scoring.

Computes input_confidence ("high", "medium", "low") strictly through rule-based
matrix evaluation of transcript clarity, required-field completeness, and detail level.

LLMs are strictly prohibited from self-reporting or influencing this score.
"""

from typing import Literal, Optional


_UNKNOWN_VALUES = {
    "",
    "unknown",
    "none",
    "n/a",
    "not specified",
    "unspecified",
    "unspecified complaint",
    "not provided",
    "null",
    "unable to capture — no response",
    "unable to capture - no response",
    "unable to capture",
    "no response captured",
    "[no response captured — silence timeout]",
    "தெரியவில்லை",
    "குறிப்பிடப்படவில்லை",
}


def is_meaningful_field(value: Optional[str]) -> bool:
    """Check if a string field contains meaningful clinical data."""
    if not value or not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    return len(normalized) > 1 and normalized not in _UNKNOWN_VALUES


def compute_input_confidence(
    raw_transcript: str,
    chief_complaint: str,
    duration: str,
    symptoms: list[str],
    has_injection_attempt: bool = False,
) -> Literal["high", "medium", "low"]:
    """
    Deterministically compute confidence score for the intake extraction.

    Scoring Criteria:
    - LOW:
      * Transcript is extremely short (< 15 characters)
      * Chief complaint is missing, empty, or an unknown/unresponsive placeholder
      * Obvious adversarial prompt-injection attempt detected
      * Zero symptoms identified (or irrelevant speech without clinical symptoms)

    - MEDIUM:
      * Chief complaint and at least 1 valid symptom are present, but duration is missing
      * Moderate transcript length with incomplete clinical dimensions

    - HIGH:
      * Chief complaint is clearly specified
      * Duration is specified (e.g. '2 days', 'since morning')
      * At least 1 symptom is identified
      * Transcript contains sufficient context (>= 25 characters)
      * No adversarial contamination detected
    """
    clean_transcript = (raw_transcript or "").strip()
    transcript_len = len(clean_transcript)

    # 1. Immediate LOW conditions
    if has_injection_attempt:
        return "low"

    if transcript_len < 15:
        return "low"

    has_cc = is_meaningful_field(chief_complaint)
    if not has_cc:
        return "low"

    valid_symptoms = [s for s in (symptoms or []) if is_meaningful_field(s)]
    has_symp = len(valid_symptoms) > 0

    # Irrelevant speech & missing symptom shield: if no symptoms identified, force LOW
    if not has_symp:
        return "low"

    has_dur = is_meaningful_field(duration)
    # If symptoms present but duration is missing/vague, confidence is MEDIUM
    if not has_dur:
        return "medium"

    # 2. HIGH condition: All 3 core dimensions present + sufficient transcript depth
    if transcript_len >= 25:
        return "high"

    return "medium"
