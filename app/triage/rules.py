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

# ===========================================================================
# LifeLine declarative rule engine (extends the legacy check above)
#
# A rule fires if its condition holds over the SIGNAL set, which is built
# from ALL of: canonical symptom tags, keyword patterns over the raw
# transcript / chief complaint / symptom strings / follow-up answers /
# addenda (English, Tamil script, transliteration), the fixed safety-screen
# chips, and vitals thresholds. An extractor miss therefore cannot hide a red
# flag. Deterministic: no LLM, no randomness. Rationales are fixed templates.
#
# PROTOTYPE RULES. Every rule needs clinician review (docs/RED_FLAG_RULES.md).
# ===========================================================================

from dataclasses import dataclass, field  # noqa: E402
from typing import Callable, Optional  # noqa: E402

from app.common.symptom_vocab import detect_tags, normalise_tags, safety_screen_tags  # noqa: E402

AFFIRMATIVE = {"yes", "y", "true", "yes (epipen)", "ஆம்", "ஆமா", "aam", "aama", "haan"}

SPO2_EMERGENCY_BELOW = 92
TEMP_HIGH_FEVER_C = 39.0
PULSE_HIGH = 130
PULSE_LOW = 40
BP_SYS_HIGH = 180
BP_SYS_LOW = 90


@dataclass(frozen=True)
class Rule:
    id: str
    tier: str  # "emergency" | "urgent"
    short: str  # nurse-facing label, e.g. "SpO2 below safe threshold"
    rationale: str  # fixed template, never LLM-written, never a diagnosis
    when: Callable[[set, Optional[int]], bool]


def _any(s: set, *tags: str) -> bool:
    return any(t in s for t in tags)


BREATH = ("breathlessness", "severe_breathing_difficulty")

RULES: list[Rule] = [
    # ---------------- Emergency tier ----------------
    Rule("chest_pain_with_breathlessness", "emergency", "Chest pain with breathing difficulty",
         "Fixed safety rule: chest pain reported together with breathing difficulty. Needs immediate emergency assessment.",
         lambda s, a: "chest_pain" in s and _any(s, *BREATH)),
    Rule("stroke_signs", "emergency", "One-sided weakness, facial droop or slurred speech",
         "Fixed safety rule: sudden one-sided weakness or numbness, facial droop, or slurred speech reported. Needs immediate emergency assessment.",
         lambda s, a: _any(s, "one_sided_weakness", "facial_droop", "slurred_speech")),
    Rule("severe_bleeding", "emergency", "Severe bleeding",
         "Fixed safety rule: severe or uncontrolled bleeding reported. Needs immediate emergency assessment.",
         lambda s, a: "severe_bleeding" in s),
    Rule("unresponsive", "emergency", "Unconscious or not responding",
         "Fixed safety rule: patient described as unconscious or not responding. Needs immediate emergency assessment.",
         lambda s, a: "unconscious" in s),
    Rule("active_seizure", "emergency", "Seizure happening now",
         "Fixed safety rule: a seizure is reported as happening now. Needs immediate emergency assessment.",
         lambda s, a: "seizure_now" in s),
    Rule("pediatric_seizure", "emergency", "Seizure in a child",
         "Fixed safety rule: a seizure was reported in a child. Needs immediate emergency assessment.",
         lambda s, a: "seizure" in s and a is not None and a < 18),
    Rule("respiratory_distress", "emergency", "Severe breathing difficulty",
         "Fixed safety rule: severe difficulty breathing reported. Needs immediate emergency assessment.",
         lambda s, a: "severe_breathing_difficulty" in s),
    Rule("swelling_with_breathing_trouble", "emergency", "Face/lip/throat swelling with breathing trouble",
         "Fixed safety rule: swelling of the face, lips or throat together with breathing trouble. Needs immediate emergency assessment.",
         lambda s, a: "face_lip_swelling" in s and _any(s, *BREATH)),
    Rule("vomiting_blood", "emergency", "Vomiting blood",
         "Fixed safety rule: vomiting blood reported. Needs immediate emergency assessment.",
         lambda s, a: "vomiting_blood" in s),
    Rule("head_injury_with_confusion", "emergency", "Head injury with confusion",
         "Fixed safety rule: head injury reported together with confusion or reduced responsiveness. Needs immediate emergency assessment.",
         lambda s, a: "head_injury" in s and _any(s, "confusion", "unconscious")),
    Rule("low_oxygen", "emergency", "SpO2 below safe threshold",
         f"Fixed safety rule: measured SpO2 below {SPO2_EMERGENCY_BELOW}%. Needs immediate emergency assessment.",
         lambda s, a: "vital_spo2_low" in s),
    Rule("poisoning", "emergency", "Possible poisoning or overdose",
         "Fixed safety rule: swallowing poison, pesticide or an overdose of tablets reported. Needs immediate emergency assessment.",
         lambda s, a: "poisoning" in s),
    Rule("abdominal_pain_with_instability", "emergency", "Abdominal pain with fainting",
         "Fixed safety rule: abdominal pain reported together with fainting. Needs immediate emergency assessment.",
         lambda s, a: "abdominal_pain" in s and "fainting" in s),
    # ---------------- Urgent tier (same-day, flagged) ----------------
    Rule("repeated_fainting", "urgent", "Repeated fainting",
         "Fixed safety rule: fainting more than once reported. A nurse should see the patient today.",
         lambda s, a: "repeated_fainting" in s),
    Rule("fainting_older_adult", "urgent", "Fainting at age 60 or above",
         "Fixed safety rule: fainting reported in a patient aged 60 or above. A nurse should see the patient today.",
         lambda s, a: "fainting" in s and a is not None and a >= 60),
    Rule("chest_pain", "urgent", "Chest pain",
         "Fixed safety rule: chest pain reported. A nurse should see the patient today.",
         lambda s, a: "chest_pain" in s),
    Rule("palpitations_with_dizziness", "urgent", "Palpitations with dizziness",
         "Fixed safety rule: palpitations reported together with dizziness or fainting. A nurse should see the patient today.",
         lambda s, a: "palpitations" in s and _any(s, "dizziness", "fainting")),
    Rule("sudden_severe_headache", "urgent", "Sudden severe headache",
         "Fixed safety rule: a sudden, severe headache reported. A nurse should see the patient today.",
         lambda s, a: "sudden_severe_headache" in s),
    Rule("black_stool", "urgent", "Black stool",
         "Fixed safety rule: black or tarry stool reported. A nurse should see the patient today.",
         lambda s, a: "black_stool" in s),
    Rule("high_fever_vulnerable_age", "urgent", "High fever in a young child or older adult",
         "Fixed safety rule: high fever reported in a child under 5 or an adult aged 65 or above. A nurse should see the patient today.",
         lambda s, a: "high_fever" in s and a is not None and (a < 5 or a >= 65)),
    Rule("pregnancy_bleeding", "urgent", "Bleeding in pregnancy",
         "Fixed safety rule: bleeding reported during pregnancy. A nurse should see the patient today.",
         lambda s, a: "pregnant" in s and _any(s, "bleeding", "severe_bleeding")),
    Rule("seizure_reported", "urgent", "Seizure reported",
         "Fixed safety rule: a recent seizure was reported. A nurse should see the patient today.",
         lambda s, a: "seizure" in s),
    Rule("abnormal_vitals", "urgent", "Pulse or blood pressure outside safe range",
         "Fixed safety rule: measured pulse or blood pressure outside the safe range. A nurse should see the patient today.",
         lambda s, a: "vital_abnormal" in s),
    Rule("safety_screen_positive", "urgent", "Safety screen answered yes",
         "Fixed safety rule: the patient ticked at least one item on the safety screen. A nurse should see the patient today.",
         lambda s, a: "safety_screen_positive" in s),
]

RULES_BY_ID = {r.id: r for r in RULES}
LEGACY_FLAG_TIER = "emergency"


@dataclass
class VitalsInput:
    bp_sys: Optional[int] = None
    bp_dia: Optional[int] = None
    temp_c: Optional[float] = None
    spo2: Optional[int] = None
    pulse: Optional[int] = None


@dataclass
class RuleResult:
    tier: Optional[str] = None  # None | "urgent" | "emergency"
    flags: list[str] = field(default_factory=list)
    rationale: str = ""
    signals: list[str] = field(default_factory=list)

    @property
    def fired(self) -> bool:
        return self.tier is not None

    def short_labels(self) -> list[str]:
        return [RULES_BY_ID[f].short if f in RULES_BY_ID else f.replace("_", " ") for f in self.flags]


def vitals_signals(v: Optional[VitalsInput]) -> set[str]:
    s: set[str] = set()
    if v is None:
        return s
    if v.spo2 is not None and v.spo2 < SPO2_EMERGENCY_BELOW:
        s.add("vital_spo2_low")
    if v.temp_c is not None and v.temp_c >= TEMP_HIGH_FEVER_C:
        s.update({"high_fever", "fever"})
    if v.pulse is not None and (v.pulse > PULSE_HIGH or v.pulse < PULSE_LOW):
        s.add("vital_abnormal")
    if v.bp_sys is not None and (v.bp_sys >= BP_SYS_HIGH or v.bp_sys < BP_SYS_LOW):
        s.add("vital_abnormal")
    return s


def collect_signals(intake, vitals: Optional[VitalsInput] = None) -> set[str]:
    """Union of every deterministic source of evidence for one intake."""
    s: set[str] = set()
    s.update(t for t in normalise_tags(getattr(intake, "symptom_tags", []) or []) if t != "other")
    texts = [intake.raw_transcript or "", intake.chief_complaint or ""]
    texts += list(intake.symptoms or [])
    for key, value in (intake.follow_up_answers or {}).items():
        val = str(value or "")
        texts.append(val)
        if val.strip().lower() in AFFIRMATIVE:
            texts.append(str(key).replace("_", " "))
    for add in getattr(intake, "addenda", []) or []:
        texts.append(add.text or "")
        texts += [str(v) for v in (add.answers or {}).values()]
        s.update(t for t in normalise_tags(add.symptom_tags or []) if t != "other")
    for t in texts:
        s.update(detect_tags(t))
    chips = [c for c in (getattr(intake, "safety_screen", []) or []) if c != "none"]
    screen = safety_screen_tags(chips)
    if screen:
        s.update(screen)
        s.add("safety_screen_positive")
    s.update(vitals_signals(vitals))
    return s


def evaluate_rules(intake, vitals: Optional[VitalsInput] = None) -> RuleResult:
    signals = collect_signals(intake, vitals)
    age = intake.age
    emergency = [r for r in RULES if r.tier == "emergency" and r.when(signals, age)]
    urgent = [r for r in RULES if r.tier == "urgent" and r.when(signals, age)]

    # The original substring rules still run; anything they catch is emergency.
    legacy = check_red_flags(list(intake.symptoms or []), age)
    legacy_ids = [legacy] if legacy and legacy not in {r.id for r in emergency} else []

    if emergency or legacy_ids:
        flags = [r.id for r in emergency] + legacy_ids
        if emergency:
            rationale = emergency[0].rationale
        elif legacy in RULES_BY_ID:
            rationale = RULES_BY_ID[legacy].rationale
        else:
            rationale = f"Fixed safety rule: warning sign '{legacy.replace('_', ' ')}' reported. Needs immediate emergency assessment."
        return RuleResult("emergency", flags, rationale, sorted(signals))
    if urgent:
        return RuleResult("urgent", [r.id for r in urgent], urgent[0].rationale, sorted(signals))
    return RuleResult(None, [], "", sorted(signals))
