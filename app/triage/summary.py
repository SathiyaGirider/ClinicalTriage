"""
DoctorSummary generator (5 lines: chief complaint, duration, red flags,
relevant history, priority + rationale).

Deterministic template first (Person C's build_doctor_summary). An LLM may
reword chief complaint / duration / history into plain English (e.g. to
translate Tamil words), but every item it returns must be traceable to the
intake data; otherwise the template is used. Red flags and the rationale are
never LLM-written: the rationale is the triage rationale verbatim.
"""

import json
import re

from app.common.llm import LLMClient, LLMError, get_llm_client
from app.common.schemas import DoctorSummary, IntakeResult, TriageDecision
from app.explain.explain import build_doctor_summary
from app.triage.prompts import SUMMARY_SYSTEM, wrap_data
from app.triage.safety_filter import violations
from app.triage.sanitizer import clean_text

_STOP = {"the", "a", "an", "of", "and", "with", "in", "on", "for", "to", "my", "is", "since", "about", "or", "at", "has", "have"}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[\w']+", (text or "").lower()) if w not in _STOP and len(w) > 2}


def _traceable(item: str, source_text: str, source_words: set[str]) -> bool:
    words = _words(item)
    if not words:
        return False
    if item.strip().lower() in source_text:
        return True
    return len(words & source_words) / len(words) >= 0.6


def template_summary(intake: IntakeResult, decision: TriageDecision) -> DoctorSummary:
    s = build_doctor_summary(intake, decision)
    s.decided_by = decision.decided_by
    s.audit_notes = list(decision.audit_notes)
    s.input_confidence = intake.input_confidence
    s.summary_source = "template"
    if intake.addenda:
        s.audit_notes = list(dict.fromkeys(s.audit_notes + ["patient_reported_change"]))
    return s


def generate_summary(intake: IntakeResult, decision: TriageDecision, client: LLMClient | None = None, use_llm: bool = True) -> DoctorSummary:
    base = template_summary(intake, decision)
    if not use_llm or intake.language == "en":
        return base  # English intake: template is already faithful
    client = client or get_llm_client()
    payload = {
        "chief_complaint": clean_text(intake.chief_complaint, 160),
        "duration": clean_text(intake.duration, 60),
        "known_conditions": intake.known_conditions,
        "patient_words": clean_text(intake.raw_transcript, 600),
    }
    try:
        data = json.loads(re.search(r"\{.*\}", client.complete(SUMMARY_SYSTEM, wrap_data(payload), 300, "summary"), re.DOTALL).group(0))
        cc = str(data.get("chief_complaint", "")).strip()[:160]
        du = str(data.get("duration", "")).strip()[:60]
        hist = [str(h).strip()[:80] for h in (data.get("relevant_history") or []) if str(h).strip()]
    except (LLMError, AttributeError, ValueError, TypeError):
        return base
    source_text = " ".join([intake.chief_complaint, intake.duration, " ".join(intake.known_conditions), " ".join(intake.symptoms)]).lower()
    source_words = _words(source_text)
    known = {k.lower() for k in intake.known_conditions}
    # Reject invented items: history must be one of the stated known conditions.
    if any(h.lower() not in known for h in hist):
        return base
    if not cc or not _traceable(cc, source_text, source_words):
        return base
    if du and not (_traceable(du, source_text, source_words) or re.search(r"\d", du) and re.search(r"\d", intake.duration or "")):
        return base
    if any(violations(x) for x in [cc, du]):
        return base
    base.chief_complaint = cc
    base.duration = du or base.duration
    base.relevant_history = hist or base.relevant_history
    base.summary_source = "llm"
    return base


def render_lines(s: DoctorSummary) -> list[str]:
    return [
        f"Chief complaint: {s.chief_complaint}",
        f"Duration: {s.duration}",
        f"Red flags: {', '.join(s.red_flags) if s.red_flags else 'None'}",
        f"Relevant history: {', '.join(s.relevant_history) if s.relevant_history else 'None'}",
        f"Priority: {s.priority} - {s.priority_rationale}",
    ]
