"""
Triage pipeline:  sanitize -> RULES -> (only if no rule fired) LLM ->
safety filter -> fail-safe wrapper.

Guarantees (tests in tests/test_triage_*.py):
- Rules are authoritative; the LLM can keep or raise, never lower.
- Uncertainty (low confidence, low input confidence, LLM error/timeout/
  malformed, injection suspected, internal error) => at least same-day,
  escalation_required=True, flag_for_nurse=True. Never routine on an error path.
- Never raises: unknown errors return a valid flagged same-day decision.
"""

import logging
from datetime import datetime

from app.common.llm import LLMClient
from app.common.schemas import PRIORITY_RANK, IntakeResult, TriageDecision, max_priority
from app.common.symptom_vocab import department_for
from app.triage.escalation import apply_escalation
from app.triage.llm_classifier import classify_with_llm
from app.triage.rules import RuleResult, VitalsInput, evaluate_rules
from app.triage.safety_filter import filter_text
from app.triage.sanitizer import detect_injection, intake_texts

logger = logging.getLogger("lifeline.triage")

FALLBACK_RATIONALE = "Automated urgency estimate unavailable. Escalated so a nurse reviews this patient today."
LOW_CONFIDENCE_RATIONALE = "The information given was unclear or the estimate was uncertain. Escalated so a nurse reviews this patient today."
INJECTION_RATIONALE_SUFFIX = " Unusual instruction-like text was found in the patient's answers; escalated for review."
INTERNAL_ERROR_RATIONALE = "The triage system hit an internal error. Escalated so a nurse reviews this patient today."


def _now() -> str:
    from app.common import timeutil
    return timeutil.now().isoformat()


def _rule_decision(intake: IntakeResult, rr: RuleResult, notes: list[str], dept: str) -> TriageDecision:
    priority = "emergency" if rr.tier == "emergency" else "same-day"
    return TriageDecision(
        patient_id=intake.patient_id,
        priority=priority,
        red_flags_matched=rr.flags,
        decided_by="rule",
        confidence="high",
        escalation_required=True,
        priority_rationale=rr.rationale,
        timestamp=_now(),
        flag_for_nurse=True,
        audit_notes=notes,
        suggested_department=dept,
        rule_tier=rr.tier,
    )


def _enforce_invariants(d: TriageDecision) -> TriageDecision:
    if d.escalation_required:
        d.priority = max_priority(d.priority, "same-day")
    if d.priority != "routine":
        d.flag_for_nurse = True
    if d.priority == "emergency":
        d.escalation_required = True
    return d


def _triage(intake: IntakeResult, vitals: VitalsInput | None, client: LLMClient | None) -> TriageDecision:
    notes: list[str] = []
    inj = detect_injection(*intake_texts(intake))
    if inj.suspected:
        notes.append("injection_suspected")
    if intake.input_confidence == "low":
        notes.append("low_input_confidence")

    # Rules run on the ORIGINAL intake text.
    rr = evaluate_rules(intake, vitals)
    tags = [t for t in rr.signals if not t.startswith("vital_") and t != "safety_screen_positive"]
    dept = department_for(tags, intake.age)
    if rr.fired:
        return _enforce_invariants(_rule_decision(intake, rr, notes, dept))

    decided_by = "llm"
    try:
        priority, confidence, rationale = classify_with_llm(intake, client=client, tags=tags)
        rationale, filtered = filter_text(rationale)
        if filtered:
            notes.append("output_filtered")
    except RuntimeError:
        priority, confidence, rationale = "same-day", "low", FALLBACK_RATIONALE
        decided_by = "fallback"
        notes.append("llm_fallback_used")

    escalate = apply_escalation(intake, confidence)
    if confidence == "low" and decided_by == "llm":
        notes.append("llm_fallback_used")
        rationale = LOW_CONFIDENCE_RATIONALE + " " + rationale
    if inj.suspected:
        escalate = True
        rationale += INJECTION_RATIONALE_SUFFIX
    if decided_by == "fallback":
        escalate = True
    if escalate:
        priority = max_priority(priority, "same-day")

    return _enforce_invariants(TriageDecision(
        patient_id=intake.patient_id,
        priority=priority,
        red_flags_matched=[],
        decided_by=decided_by,
        confidence=confidence,
        escalation_required=escalate,
        priority_rationale=rationale,
        timestamp=_now(),
        flag_for_nurse=priority != "routine" or escalate,
        audit_notes=notes,
        suggested_department=dept,
    ))


def failsafe_decision(patient_id: str, note: str = "internal_error") -> TriageDecision:
    return TriageDecision(
        patient_id=patient_id,
        priority="same-day",
        red_flags_matched=[],
        decided_by="fallback",
        confidence="low",
        escalation_required=True,
        priority_rationale=INTERNAL_ERROR_RATIONALE,
        timestamp=_now(),
        flag_for_nurse=True,
        audit_notes=[note, "llm_fallback_used"],
    )


def triage(intake_result: IntakeResult, vitals: VitalsInput | None = None, client: LLMClient | None = None) -> TriageDecision:
    """Public entry point (signature kept from Person B's version). Never raises."""
    try:
        decision = _triage(intake_result, vitals, client)
    except Exception as exc:  # fail safe, never 500, never routine
        logger.error("triage internal error patient=%s error=%s", getattr(intake_result, "patient_id", "?"), type(exc).__name__)
        decision = failsafe_decision(getattr(intake_result, "patient_id", "unknown"))
    logger.info("triage patient=%s priority=%s decided_by=%s", decision.patient_id, decision.priority, decision.decided_by)
    return decision


def reclassify(
    intake: IntakeResult,
    previous: TriageDecision,
    vitals: VitalsInput | None = None,
    client: LLMClient | None = None,
    use_llm: bool = True,
) -> tuple[TriageDecision, bool, list[str]]:
    """
    Re-run triage after vitals or a re-check addendum. Can only RAISE.
    Returns (decision, raised, raise_reasons). Vitals-only reruns use rules only.
    """
    try:
        if use_llm:
            new = triage(intake, vitals, client)
        else:
            rr = evaluate_rules(intake, vitals)
            new = _rule_decision(intake, rr, [], previous.suggested_department or "General Medicine") if rr.fired else None
    except Exception:
        new = failsafe_decision(previous.patient_id)

    merged = previous.model_copy(deep=True)
    merged.audit_notes = list(dict.fromkeys(previous.audit_notes + (new.audit_notes if new else []) + ["reclassified"]))
    raised = False
    reasons: list[str] = []
    if new is not None:
        merged.red_flags_matched = list(dict.fromkeys(previous.red_flags_matched + new.red_flags_matched))
        merged.flag_for_nurse = previous.flag_for_nurse or new.flag_for_nurse
        merged.escalation_required = previous.escalation_required or new.escalation_required
        if PRIORITY_RANK[new.priority] > PRIORITY_RANK[previous.priority]:
            raised = True
            merged.priority = new.priority
            merged.priority_rationale = new.priority_rationale
            merged.decided_by = new.decided_by
            merged.confidence = new.confidence
            merged.rule_tier = new.rule_tier
            from app.triage.rules import RULES_BY_ID
            reasons = [RULES_BY_ID[f].short for f in new.red_flags_matched if f in RULES_BY_ID] or ["re-check"]
    merged.timestamp = _now()
    return _enforce_invariants(merged), raised, reasons
