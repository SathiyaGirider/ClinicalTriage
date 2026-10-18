"""
Output filter for ANY LLM-written text (triage rationale, summary lines,
adaptive questions). Diagnosis or medication language is replaced by a safe
template and the caller adds the audit note "output_filtered".
"""

from __future__ import annotations

import re

SAFE_RATIONALE = "AI-assisted urgency estimate based on the reported symptoms, their duration and the patient's age. Please review."

_DIAGNOSIS = [
    r"\byou\s+(?:have|'ve\s+got|have\s+got|are\s+suffering\s+from)\b", r"\bdiagnos", r"\bconsistent\s+with\b", r"\bsuggestive\s+of\b",
    r"\bsounds\s+like\b", r"\b(?:likely|probably|possibly)\s+(?:has|have|is|a|an)\b", r"\bindicative\s+of\b", r"\bcaused\s+by\b",
    r"\b(?:dengue|malaria|typhoid|appendicitis|stroke|heart\s+attack|myocardial|infarction|angina|pneumonia|covid|influenza|\bflu\b|"
    r"tuberculosis|\btb\b|cancer|tumou?r|sepsis|meningitis|anaphylaxis|asthma\s+attack|fracture|ectopic|gastritis|ulcer|"
    r"diabetes|hypertension|infection|viral|bacterial)\b",
    r"டெங்கு", r"மாரடைப்பு", r"பக்கவாதம்", r"நோய்\s*உள்ளது",
]
_MEDICATION = [
    r"\b\d+(?:\.\d+)?\s?(?:mg|mcg|µg|ml|g|iu|units?|tabs?|tablets?|capsules?|puffs?|drops?)\b",
    r"\b(?:paracetamol|acetaminophen|ibuprofen|aspirin|amoxicillin|azithromycin|metformin|insulin|cetirizine|dolo|crocin|"
    r"omeprazole|pantoprazole|ranitidine|salbutamol|prednisolone|diclofenac|epinephrine|adrenaline|antibiotics?|"
    r"antihistamines?|painkillers?|ors|steroids?|nitroglycerin|atorvastatin|amlodipine|losartan|clopidogrel)\b",
    r"மாத்திரை", r"மருந்து\s*(?:எடு|சாப்பிடு|கொடு)",
]
# Generic treatment words: banned in rationales/summaries, allowed in questions
# ("Are you taking any medicine?" is a question, not advice).
_MED_GENERIC = [
    r"\b(?:take|took|use|apply|start|prescrib\w*|dose|dosage|tablet|medicine|medication|drug|treatment|treat\s+with)\b",
]
_DIAG_RX = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in _DIAGNOSIS]
_MED_RX = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in _MEDICATION]
_MED_GENERIC_RX = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in _MED_GENERIC]


def violations(text: str, allow_generic_medicine_words: bool = False) -> list[str]:
    found = []
    if any(rx.search(text or "") for rx in _DIAG_RX):
        found.append("diagnosis_language")
    med = _MED_RX if allow_generic_medicine_words else _MED_RX + _MED_GENERIC_RX
    if any(rx.search(text or "") for rx in med):
        found.append("medication_language")
    return found


def filter_text(text: str, fallback: str = SAFE_RATIONALE, question: bool = False) -> tuple[str, bool]:
    """Return (safe_text, was_filtered)."""
    if violations(text, allow_generic_medicine_words=question):
        return fallback, True
    return text, False
