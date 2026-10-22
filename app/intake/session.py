"""
Adaptive intake session (LifeLine patient app, nurse assisted mode, check-in re-check).

Booking / symptom-first / assisted flow, 4-6 questions in total:
  1. complaint      "What is troubling you?"            (always first, free text)
  2. safety_screen  fixed 7-chip multi-select + "None"  (always asked, never LLM-chosen)
  3. duration       chips + free text                   (always)
  4. age            number, ONLY if the profile has none (prefilled otherwise)
  5. conditions     chips + free text                   (always)
  6+ adaptive       LLM chooses the question text only; fixed bank if the LLM fails
Re-check flow (Worse / New symptom at check-in), 2-3 questions:
  what changed, when it started, one adaptive.

If an emergency rule fires after any answer the flow ends at once, so the
patient sees the emergency screen without answering more questions.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from app.common import timeutil
from app.common.ids import new_id
from app.common.llm import LLMError, get_llm_client
from app.common.schemas import IntakeAddendum, IntakeResult
from app.common.symptom_vocab import SAFETY_SCREEN_CHIPS, detect_tags
from app.intake.confidence import compute_input_confidence
from app.intake.extractor import extract_intake
from app.intake.followup import DETERMINISTIC_QUESTIONS, select_adaptive_categories
from app.intake.schemas import IntakeRequest
from app.triage.prompts import QUESTION_SYSTEM, wrap_data
from app.triage.rules import evaluate_rules
from app.triage.safety_filter import filter_text
from app.triage.sanitizer import clean_text, detect_injection

MAX_QUESTIONS = 6
MAX_RECHECK_QUESTIONS = 3

DURATION_CHIPS = ["today", "1_3_days", "4_7_days", "1_4_weeks", "over_month"]
DURATION_TEXT = {
    "today": "since today", "1_3_days": "1-3 days", "4_7_days": "4-7 days", "1_4_weeks": "1-4 weeks", "over_month": "more than a month",
}
CONDITION_CHIPS = ["diabetes", "high_bp", "asthma", "heart_problem", "pregnancy", "kidney_problem", "none"]
CONDITION_TEXT = {
    "diabetes": "diabetes", "high_bp": "high blood pressure", "asthma": "asthma", "heart_problem": "heart problem",
    "pregnancy": "pregnant", "kidney_problem": "kidney problem",
}
CHANGE_WHEN_CHIPS = ["just_now", "today", "yesterday", "earlier"]

# Fixed question text (frontend translates by key via i18n; these are for API clients).
FIXED_TEXT = {
    "complaint": {"en": "What is troubling you?", "ta": "உங்களுக்கு என்ன தொந்தரவு?"},
    "safety_screen": {"en": "Right now, do any of these apply to you?", "ta": "இப்போது, இவற்றில் ஏதேனும் உங்களுக்கு உள்ளதா?"},
    "duration": {"en": "How long have you had this?", "ta": "இது எவ்வளவு நாட்களாக உள்ளது?"},
    "age": {"en": "What is your age?", "ta": "உங்கள் வயது என்ன?"},
    "conditions": {"en": "Do you have any long-term conditions?", "ta": "உங்களுக்கு நீண்டகால உடல்நலப் பிரச்சனை ஏதேனும் உள்ளதா?"},
    "change": {"en": "What has changed since you booked?", "ta": "முன்பதிவு செய்ததிலிருந்து என்ன மாறியுள்ளது?"},
    "change_when": {"en": "When did this change start?", "ta": "இந்த மாற்றம் எப்போது தொடங்கியது?"},
}
SEVERITY_Q = {"en": "How bad is it now: mild, moderate or very bad?", "ta": "இப்போது எவ்வளவு கடுமையாக உள்ளது: லேசான, மிதமான, அல்லது மிகவும் கடுமையான?"}
WORSE_Q = {"en": "Does anything make it better or worse?", "ta": "எதனால் இது குறைகிறது அல்லது அதிகமாகிறது?"}


class IntakeFlowError(ValueError):
    pass


def _q(key: str, kind: str, lang: str, text: str | None = None, options: list[str] | None = None, source: str = "fixed") -> dict:
    return {"key": key, "kind": kind, "question": text or FIXED_TEXT[key][lang], "options": options or [], "source": source}


def new_state(mode: str, language: str, profile_age: Optional[int], profile_conditions: list[str] | None = None,
              base_intake: Optional[dict] = None) -> dict:
    lang = "ta" if language == "ta" else "en"
    state = {
        "id": new_id("is_"),
        "mode": mode,
        "language": lang,
        "age": profile_age,
        "profile_conditions": profile_conditions or [],
        "answers": {},  # key -> answer (str or list)
        "asked": [],  # list of question dicts, in order
        "current": None,
        "done": False,
        "emergency_short_circuit": False,
        "llm_questions_failed": 0,
        "base_intake": base_intake,
        "started_at": timeutil.now().isoformat(),
    }
    if mode == "recheck":
        state["current"] = _q("change", "text", lang)
    else:
        state["current"] = _q("complaint", "text", lang)
    return state


def _cap(state: dict) -> int:
    return MAX_RECHECK_QUESTIONS if state["mode"] == "recheck" else MAX_QUESTIONS


def _all_text(state: dict) -> str:
    parts = []
    for q in state["asked"]:
        a = state["answers"].get(q["key"])
        if isinstance(a, str) and q["kind"] in ("text", "adaptive"):
            parts.append(a)
    return " . ".join(p for p in parts if p)


def _provisional_intake(state: dict, patient_id: str = "provisional") -> IntakeResult:
    return build_intake_result(state, patient_id, run_extractor=False)


def _is_emergency(state: dict) -> bool:
    try:
        intake = _provisional_intake(state)
        if state["mode"] == "recheck" and state.get("base_intake"):
            base = IntakeResult.model_validate(state["base_intake"])
            base.addenda = intake.addenda
            intake = base
        return evaluate_rules(intake).tier == "emergency"
    except Exception:
        return False


def _adaptive_question(state: dict) -> dict:
    lang = state["language"]
    asked_text = [q["question"] for q in state["asked"]]
    client = get_llm_client()
    payload = {
        "language": "Tamil" if lang == "ta" else "English",
        "symptom_tags": detect_tags(_all_text(state)),
        "patient_words": clean_text(_all_text(state), 400),
        "already_asked": asked_text,
    }
    n = sum(1 for q in state["asked"] if q["source"] in ("llm", "bank"))
    key = f"adaptive_{n + 1}"
    try:
        if getattr(client, "name", "") == "fake":
            raise LLMError("fake client must not generate patient-facing questions")
        if detect_injection(_all_text(state)).suspected:
            raise LLMError("injection suspected: use fixed bank")
        text = client.complete(QUESTION_SYSTEM, wrap_data(payload), max_tokens=60, purpose="question").strip().strip('"')
        text = text.splitlines()[0].strip() if text else ""
        text, filtered = filter_text(text, fallback="", question=True)
        tamil = any("஀" <= ch <= "௿" for ch in text)
        if filtered or not text or len(text) > 140 or (lang == "ta" and not tamil) or (lang == "en" and tamil) or text in asked_text:
            raise LLMError("unusable question")
        return _q(key, "adaptive", lang, text=text, source="llm")
    except LLMError:
        state["llm_questions_failed"] += 1
    # Fixed fallback bank (Person A's bilingual questions + two of ours)
    cats = select_adaptive_categories(raw_transcript=_all_text(state), duration=str(state["answers"].get("duration", "")),
                                      known_conditions=state["profile_conditions"])
    bank = [DETERMINISTIC_QUESTIONS[c][lang] for c in cats if c not in ("onset", "history")]
    bank += [SEVERITY_Q[lang], WORSE_Q[lang], DETERMINISTIC_QUESTIONS["medications"][lang]]
    for text in bank:
        if text not in asked_text:
            return _q(key, "adaptive", lang, text=text, source="bank")
    return _q(key, "adaptive", lang, text=SEVERITY_Q[lang], source="bank")


def _next_question(state: dict) -> Optional[dict]:
    lang = state["language"]
    answered = set(state["answers"])
    total = len(state["asked"])
    if total >= _cap(state):
        return None
    if state["mode"] == "recheck":
        if "change_when" not in answered:
            return _q("change_when", "chips", lang, options=CHANGE_WHEN_CHIPS)
        if total < _cap(state):
            return _adaptive_question(state)
        return None
    if "safety_screen" not in answered:
        return _q("safety_screen", "multi", lang, options=["none"] + list(SAFETY_SCREEN_CHIPS))
    if "duration" not in answered:
        return _q("duration", "chips", lang, options=DURATION_CHIPS)
    if state["age"] is None and "age" not in answered:
        return _q("age", "number", lang)
    if "conditions" not in answered:
        return _q("conditions", "multi", lang, options=CONDITION_CHIPS)
    # Adaptive: 2 if the complaint was short, else 1; never past the cap of 6.
    complaint_words = len(str(state["answers"].get("complaint", "")).split())
    wanted_adaptive = 2 if complaint_words < 8 else 1
    asked_adaptive = sum(1 for q in state["asked"] if q["kind"] == "adaptive")
    if asked_adaptive < wanted_adaptive:
        return _adaptive_question(state)
    return None


def _validate_answer(q: dict, answer: Any) -> Any:
    kind = q["kind"]
    if kind in ("text", "adaptive"):
        if not isinstance(answer, str):
            raise IntakeFlowError("answer must be text")
        a = answer.strip()[:2000]
        if q["key"] in ("complaint", "change") and not a:
            raise IntakeFlowError("Please describe the problem")
        return a
    if kind == "number":
        try:
            n = int(str(answer).strip())
        except ValueError:
            raise IntakeFlowError("age must be a number")
        if not 0 <= n <= 125:
            raise IntakeFlowError("age out of range")
        return n
    if kind == "chips":
        if isinstance(answer, list):
            answer = answer[0] if answer else ""
        a = str(answer).strip()
        if a not in q["options"]:
            return a[:200]  # free text allowed alongside chips
        return a
    if kind == "multi":
        if isinstance(answer, str):
            answer = [answer] if answer else []
        items = [str(x).strip()[:100] for x in answer if str(x).strip()]
        if q["key"] == "safety_screen":
            items = [x for x in items if x in q["options"]]
            if not items:
                raise IntakeFlowError("Choose 'None of these' or at least one item")
            if "none" in items and len(items) > 1:
                items = [x for x in items if x != "none"]
        return items
    raise IntakeFlowError("unknown question kind")


def answer(state: dict, key: str, value: Any) -> dict:
    """Record an answer. Answering an earlier key edits it (confirm screen)."""
    if state["done"] and key not in state["answers"]:
        raise IntakeFlowError("This intake is already complete")
    cur = state["current"]
    previous = next((q for q in state["asked"] if q["key"] == key), None)
    if previous is not None:
        state["answers"][key] = _validate_answer(previous, value)
        if not state["done"] and _is_emergency(state):
            state["done"], state["emergency_short_circuit"], state["current"] = True, True, None
        return state
    if cur is None or cur["key"] != key:
        raise IntakeFlowError("Unexpected question key")
    state["answers"][key] = _validate_answer(cur, value)
    if key == "age":
        state["age"] = state["answers"][key]
    state["asked"].append(cur)
    if _is_emergency(state):
        state["done"], state["emergency_short_circuit"], state["current"] = True, True, None
        return state
    nxt = _next_question(state)
    state["current"] = nxt
    state["done"] = nxt is None
    return state


def _duration_text(state: dict) -> str:
    d = state["answers"].get("duration")
    if not d:
        return "unspecified"
    return DURATION_TEXT.get(d, str(d))


def _conditions(state: dict) -> list[str]:
    raw = state["answers"].get("conditions") or []
    out = list(state["profile_conditions"])
    for c in raw:
        if c == "none":
            continue
        val = CONDITION_TEXT.get(c, c)
        if val not in out:
            out.append(val)
    return out


def build_intake_result(state: dict, patient_id: str, run_extractor: bool = True) -> IntakeResult:
    lang = state["language"]
    if state["mode"] == "recheck":
        return _build_recheck(state, patient_id)
    complaint = str(state["answers"].get("complaint", "")).strip()
    extra = [str(state["answers"][q["key"]]) for q in state["asked"] if q["kind"] == "adaptive" and state["answers"].get(q["key"])]
    raw_transcript = " | ".join([complaint] + extra) if extra else complaint
    follow_up = {}
    for q in state["asked"]:
        if q["kind"] == "adaptive" and state["answers"].get(q["key"]):
            follow_up[q["key"]] = str(state["answers"][q["key"]])
    follow_up["duration"] = _duration_text(state)
    tags = detect_tags(raw_transcript)
    age = state["age"]
    conditions = _conditions(state)
    safety = list(state["answers"].get("safety_screen") or [])
    if run_extractor and raw_transcript:
        ir = extract_intake(IntakeRequest(raw_transcript=raw_transcript[:4000], language=lang, patient_id=patient_id, age=age,
                                          known_conditions=conditions, follow_up_answers=follow_up))
        extractor_llm = get_llm_client().name != "unavailable"
    else:
        ir = IntakeResult(patient_id=patient_id, chief_complaint=complaint[:120] or "unspecified", duration=_duration_text(state),
                          symptoms=[], age=age, known_conditions=conditions, follow_up_answers=follow_up,
                          raw_transcript=raw_transcript or "", input_confidence="medium")
        extractor_llm = True
    if ir.duration.lower() in ("unspecified", "unknown", ""):
        ir.duration = _duration_text(state)
    if not ir.symptoms and tags:
        ir.symptoms = [t.replace("_", " ") for t in tags]
    ir.symptom_tags = tags or ["other"]
    ir.safety_screen = safety
    ir.language = lang
    ir.assisted = state["mode"] == "assisted"
    if run_extractor:
        conf = compute_input_confidence(ir.raw_transcript, ir.chief_complaint, ir.duration, ir.symptoms,
                                        detect_injection(raw_transcript).suspected)
        if len(complaint.split()) < 3 and not tags:
            conf = "low"
        if not extractor_llm:
            # Deterministic fallback extractor: low unless our vocabulary recognised the words.
            conf = "low" if not tags else conf
        ir.input_confidence = conf
    return ir


def _build_recheck(state: dict, patient_id: str) -> IntakeResult:
    """Recheck: returns the BASE intake with this addendum appended."""
    base = IntakeResult.model_validate(state["base_intake"]) if state.get("base_intake") else IntakeResult(
        patient_id=patient_id, chief_complaint="re-check", duration="unspecified", symptoms=[], raw_transcript="",
        input_confidence="low")
    text = str(state["answers"].get("change", ""))
    extra = {q["key"]: str(state["answers"][q["key"]]) for q in state["asked"] if q["kind"] != "text" and q["key"] in state["answers"]}
    adds = [str(state["answers"][q["key"]]) for q in state["asked"] if q["kind"] == "adaptive" and state["answers"].get(q["key"])]
    full = " . ".join([text] + adds)
    add = IntakeAddendum(ts=timeutil.now().isoformat(), change=state.get("change_kind", "worse"), text=full[:2000],
                         answers=extra, symptom_tags=detect_tags(full), source=state.get("addendum_source", "nurse"))
    base.addenda = list(base.addenda) + [add]
    return base


def understood(state: dict, intake: IntakeResult) -> dict:
    """What the confirm screen shows: the patient's own words and chip keys (no priority, nothing diagnostic)."""
    return {
        "your_words": intake.raw_transcript,
        "duration": state["answers"].get("duration"),
        "safety_screen": intake.safety_screen,
        "conditions": state["answers"].get("conditions") or [],
        "age": intake.age,
        "answers": [{"key": q["key"], "question": q["question"], "kind": q["kind"], "options": q["options"],
                     "answer": state["answers"].get(q["key"])} for q in state["asked"]],
    }


def public_view(state: dict) -> dict:
    return {
        "session_id": state["id"],
        "mode": state["mode"],
        "language": state["language"],
        "done": state["done"],
        "current": state["current"],
        "question_number": len(state["asked"]) + (0 if state["done"] else 1),
        "max_questions": _cap(state),
        "age_prefilled": state["age"] if "age" not in state["answers"] else None,
        "ended_early_for_safety": state["emergency_short_circuit"],
    }


def dumps(state: dict) -> str:
    return json.dumps(state, ensure_ascii=False)


def loads(text: str) -> dict:
    return json.loads(text)


def parse_age(value: Optional[str]) -> Optional[int]:
    """Profile stores age or DOB (YYYY-MM-DD)."""
    if not value:
        return None
    if re.fullmatch(r"\d{1,3}", value.strip()):
        return int(value)
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", value.strip())
    if m:
        t = timeutil.today()
        y, mo, d = map(int, m.groups())
        return t.year - y - ((t.month, t.day) < (mo, d))
    return None
