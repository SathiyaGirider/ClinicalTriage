"""
Input sanitising and prompt-injection detection.

Patient text is DATA. Detection here can only ever RAISE caution: the caller
adds the audit note "injection_suspected" and escalates. Rules always run on
the ORIGINAL text, never on the sanitised copy.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

MAX_FIELD_CHARS = 300
MAX_TOTAL_CHARS = 15000  # anything longer is "absurd length"

_INJECTION_PATTERNS = [
    # English
    r"ignore\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|rules|prompts?|messages?)",
    r"disregard\s+(?:all\s+|the\s+|your\s+)?(?:previous\s+|prior\s+)?(?:instructions|rules|guidelines|prompt)",
    r"forget\s+(?:all\s+|your\s+)?(?:previous\s+)?(?:instructions|rules)",
    r"(?:mark|classify|set|label|put|make|triage)\s+(?:me|this|him|her|it|the\s+patient)\s+(?:\w+\s+){0,3}(?:as\s+)?(?:routine|low\s+priority|non[- ]?urgent|not\s+urgent|emergency|high\s+priority)",
    r"\bsystem\s*prompt\b", r"^\s*system\s*:", r"\bassistant\s*:", r"\bdeveloper\s+mode\b",
    r"you\s+are\s+now\b", r"pretend\s+(?:to\s+be|you\s+are)", r"act\s+as\s+(?:a|an|the)\b", r"role\s*-?\s*play",
    r"\bjailbreak\b", r"bypass\s+(?:the\s+)?(?:triage|rules|safety|filter)", r"override\s+(?:the\s+)?(?:rules|triage|priority|safety)",
    r"new\s+instructions?\s*:", r"</?\s*(?:patient_data|system|instructions?)\s*>", r"\[\s*(?:inst|system)\s*\]",
    # Tamil script
    r"முந்தைய\s*(?:அறிவுறுத்தல்|வழிமுறை|கட்டளை)\S*\s*(?:புறக்கணி|மற)",
    r"(?:அறிவுறுத்தல்|வழிமுறை|கட்டளை)\S*\s*(?:புறக்கணி|மறந்துவிடு)",
    r"(?:என்னை|இதை)\s*(?:சாதாரண|அவசரமில்லாத|routine)\S*\s*(?:என்று|ஆக|ஆ)?\s*(?:குறி|மாற்று|போடு|வகைப்படுத்து)",
    r"routine\s*(?:ஆக|ஆ|என்று)\s*(?:குறி|மாற்று|போடு)",
    # Tamil transliterated
    r"(?:munthaiya|previous)\s+(?:instructions?|kattalai)\s+(?:ellam\s+)?(?:marandhu|marandu|ignore)",
    r"routine\s*(?:nu|aa|aaga|ah)\s+(?:podu|pottu|mark|maathu|mathu)",
    r"ignore\s+pannu",
]
_INJECTION_RX = [re.compile(p, re.IGNORECASE | re.UNICODE | re.MULTILINE) for p in _INJECTION_PATTERNS]
_ENCODED_BLOB = re.compile(r"(?:[A-Za-z0-9+/]{40,}={0,2})|(?:(?:\\x|%)[0-9a-fA-F]{2}){10,}|(?:[01]{8}\s?){8,}")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f​-‏‪-‮⁦-⁩]")
_TAGLIKE = re.compile(r"<[^>]{0,40}>")


@dataclass
class InjectionReport:
    suspected: bool = False
    reasons: list[str] = field(default_factory=list)


def detect_injection(*texts: str) -> InjectionReport:
    rep = InjectionReport()
    joined = "\n".join(t or "" for t in texts)
    if len(joined) > MAX_TOTAL_CHARS:
        rep.suspected = True
        rep.reasons.append("absurd_length")
    for rx in _INJECTION_RX:
        if rx.search(joined):
            rep.suspected = True
            rep.reasons.append("instruction_like_text")
            break
    if _ENCODED_BLOB.search(joined):
        rep.suspected = True
        rep.reasons.append("encoded_blob")
    return rep


def clean_text(text: str, limit: int = MAX_FIELD_CHARS) -> str:
    """Normalise, strip control chars and tag-like markup, collapse spaces, truncate."""
    t = unicodedata.normalize("NFC", str(text or ""))
    t = _CONTROL.sub(" ", t)
    t = _TAGLIKE.sub(" ", t)
    t = t.replace("```", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:limit]


def intake_texts(intake) -> list[str]:
    texts = [intake.raw_transcript or "", intake.chief_complaint or ""]
    texts += [str(v) for v in (intake.follow_up_answers or {}).values()]
    texts += [str(k) for k in (intake.follow_up_answers or {}).keys()]
    for add in getattr(intake, "addenda", []) or []:
        texts.append(add.text or "")
        texts += [str(v) for v in (add.answers or {}).values()]
    return texts


def structured_subset(intake, tags: list[str]) -> dict:
    """The ONLY patient data the triage LLM sees: no raw transcript, no names."""
    return {
        "symptom_tags": tags,
        "duration": clean_text(intake.duration, 60),
        "age": intake.age,
        "known_conditions": [clean_text(c, 60) for c in (intake.known_conditions or [])][:10],
        "follow_up_answers": {clean_text(k, 40): clean_text(v, 120) for k, v in list((intake.follow_up_answers or {}).items())[:8]},
        "chief_complaint": clean_text(intake.chief_complaint, 120),
        "changes_since_booking": [clean_text(a.text, 200) for a in (getattr(intake, "addenda", []) or [])][:3],
    }
