"""
Adaptive Follow-up Question Generator.

Produces adaptive follow-up clinical questions based on missing or ambiguous
dimensions in the intake data. Constrained to fixed allowed clinical categories:
- onset
- associated_symptoms
- history
- medications

Generates questions in the selected language (en / ta).
Includes robust deterministic bilingual fallback question banks.
"""

import re
import json
import logging
from typing import Literal, Optional
from app.intake.schemas import FollowUpQuestion
from app.intake.confidence import is_meaningful_field
from app.intake.redflag_scan import scan_red_flags

logger = logging.getLogger(__name__)

CategoryType = Literal[
    "onset",
    "associated_symptoms",
    "history",
    "medications",
]

ALLOWED_CATEGORIES: list[CategoryType] = [
    "onset",
    "associated_symptoms",
    "history",
    "medications",
]

# Canonical deterministic question banks by category and language (specific closed-form)
DETERMINISTIC_QUESTIONS: dict[CategoryType, dict[str, str]] = {
    "onset": {
        "en": "When did this start — today, yesterday, or longer ago?",
        "ta": "இது எப்போது தொடங்கியது — இன்றா, நேற்றா, அல்லது அதற்கு முன்பா?",
    },
    "associated_symptoms": {
        "en": "Do you have fever, vomiting, or dizziness along with this?",
        "ta": "இதனுடன் காய்ச்சல், வாந்தி அல்லது மயக்கம் உள்ளதா?",
    },
    "history": {
        "en": "Do you have diabetes, blood pressure, or any other ongoing condition?",
        "ta": "உங்களுக்கு சர்க்கரை நோய், ரத்த அழுத்தம் அல்லது வேறு ஏதேனும் நீண்டகால பிரச்சனை உள்ளதா?",
    },
    "medications": {
        "en": "Are you currently taking any medicine for this?",
        "ta": "இதற்காக தற்போது ஏதேனும் மருந்து உட்கொள்கிறீர்களா?",
    },
}

ROUTINE_MINOR_PATTERNS = [
    r"\bcold\b", r"\bcough\b", r"\brunny\s+nose\b", r"\bmild\b", r"\bslight\b",
    r"\bsneeze\b", r"\bsneezing\b", r"\bitchy\s+throat\b", r"\bsore\s+throat\b",
    r"\bheadache\b",
    r"இருமல்", r"சளி", r"தும்மல்", r"லேசான", r"மூக்கடைப்பு", r"தொண்டை\s*கரகரப்பு",
]

SIGNIFICANT_PATTERNS = [
    r"\bchest\b", r"\bbreath\b", r"\bbreathing\b", r"\bshortness\b",
    r"\bfaint\b", r"\bdizzy\b", r"\bdizziness\b", r"\bvomit\b", r"\bvomiting\b",
    r"\bblood\b", r"\bbleed\b", r"\bsevere\b", r"\bheart\b", r"\bstomach\b",
    r"\babdominal\b", r"\babdomen\b", r"\bfracture\b", r"\baccident\b",
    r"\btrauma\b", r"\bfall\b", r"\bfever\b", r"\bhigh\s+temperature\b",
    r"மார்பு", r"மூச்சு", r"திணறல்", r"மயக்கம்", r"வாந்தி", r"ரத்தம்",
    r"கடுமையான", r"விபத்து", r"காயம்", r"வயிற்று\s*வலி", r"காய்ச்சல்",
]


def is_category_already_answered(
    category: CategoryType,
    duration: Optional[str] = None,
    symptoms: Optional[list[str]] = None,
    known_conditions: Optional[list[str]] = None,
    text_to_check: str = "",
) -> bool:
    """
    Check if the clinical dimension for a category is already stated in the transcript/fields
    to prevent asking redundant questions.
    """
    safe_text = (text_to_check or "").lower()
    if category == "onset":
        return is_meaningful_field(duration)
    elif category == "associated_symptoms":
        # Check if the specific triad (fever, vomiting, dizziness) was already stated
        return bool(re.search(
            r"\b(?:fever|high\s+temp|temperature|vomit|vomiting|dizzy|dizziness|faint|nausea)\b|"
            r"காய்ச்சல்|வாந்தி|மயக்கம்",
            safe_text,
            re.IGNORECASE | re.UNICODE,
        ))
    elif category == "history":
        if known_conditions and len(known_conditions) > 0:
            return True
        return bool(re.search(
            r"\b(?:diabetes|diabetic|sugar|bp|blood\s+pressure|hypertension|asthma|cardiac|heart\s+disease)\b|"
            r"சர்க்கரை|பிரஷர்|ரத்த\s*அழுத்தம்|ஆஸ்துமா|இதய\s*நோய்",
            safe_text,
            re.IGNORECASE | re.UNICODE,
        ))
    elif category == "medications":
        return bool(re.search(
            r"\b(?:medicine|medication|pill|tablet|syrup|paracetamol|taking\s+drugs)\b|"
            r"மருந்து|மாத்திரை|டேப்லெட்",
            safe_text,
            re.IGNORECASE | re.UNICODE,
        ))
    return False


def select_adaptive_categories(
    chief_complaint: Optional[str] = None,
    duration: Optional[str] = None,
    symptoms: Optional[list[str]] = None,
    known_conditions: Optional[list[str]] = None,
    raw_transcript: str = "",
) -> list[CategoryType]:
    """
    Select at most 3 clinically relevant follow-up question categories based on complaint,
    strictly deduplicating any category whose information was already provided in the
    chief complaint or raw transcript.
    - Routine/minor complaints (cold, mild cough): prioritize onset, associated_symptoms, medications.
    - Significant complaints or red flags: prioritize associated_symptoms, history, onset, medications.
    Always returns at most 3 categories (0 to 3 categories).
    """
    symptoms_list = symptoms or []
    known_cond_list = known_conditions or []
    text_to_check = f"{chief_complaint or ''} {' '.join(symptoms_list)} {raw_transcript}".lower()

    # 1. Check for red flags using deterministic scanner
    red_flags = scan_red_flags(raw_transcript) if raw_transcript else []

    # Check if significant
    is_significant = bool(red_flags) or any(
        re.search(pat, text_to_check, re.IGNORECASE | re.UNICODE) for pat in SIGNIFICANT_PATTERNS
    )

    # Check if clearly routine / minor
    is_routine = (not is_significant) and any(
        re.search(pat, text_to_check, re.IGNORECASE | re.UNICODE) for pat in ROUTINE_MINOR_PATTERNS
    )

    candidate_order: list[CategoryType] = []

    if is_significant:
        # Prioritize associated_symptoms and history for significant/red-flag complaints
        candidate_order.extend(["associated_symptoms", "history", "onset", "medications"])
    elif is_routine:
        # Prioritize onset and associated symptoms for routine/minor complaints
        candidate_order.extend(["onset", "associated_symptoms", "medications"])
    else:
        # General / intermediate complaints
        candidate_order.extend(["onset", "associated_symptoms", "history", "medications"])

    # Deduplicate: only include categories that have NOT already been answered
    selected: list[CategoryType] = []
    for cat in candidate_order:
        if not is_category_already_answered(cat, duration, symptoms_list, known_cond_list, text_to_check):
            if cat not in selected:
                selected.append(cat)
        if len(selected) >= 3:
            break

    return selected[:3]


def generate_deterministic_followups(
    categories: list[CategoryType],
    language: Literal["en", "ta"] = "en",
) -> list[FollowUpQuestion]:
    """
    Build follow-up questions from the deterministic bilingual bank.
    """
    lang_key = "ta" if language == "ta" else "en"
    questions: list[FollowUpQuestion] = []

    for cat in categories[:3]:
        q_text = DETERMINISTIC_QUESTIONS.get(cat, {}).get(
            lang_key,
            DETERMINISTIC_QUESTIONS[cat]["en"],
        )
        questions.append(
            FollowUpQuestion(
                category=cat,
                question=q_text,
                language=language,
            )
        )

    return questions


def generate_followup_questions(
    chief_complaint: Optional[str] = None,
    duration: Optional[str] = None,
    symptoms: Optional[list[str]] = None,
    known_conditions: Optional[list[str]] = None,
    language: Literal["en", "ta"] = "en",
    raw_transcript: str = "",
    llm_client: Optional[object] = None,
) -> list[FollowUpQuestion]:
    """
    Generate at most 3 adaptive follow-up questions selected by relevance.
    Uses LLM when available, strictly constrained to allowed categories,
    with an immediate deterministic fallback on error or missing client.
    """
    symptoms_list = symptoms or []
    conditions_list = known_conditions or []

    categories = select_adaptive_categories(
        chief_complaint=chief_complaint,
        duration=duration,
        symptoms=symptoms_list,
        known_conditions=conditions_list,
        raw_transcript=raw_transcript,
    )

    # Ensure at least 1-2 categories if available without re-adding answered ones
    if len(categories) < 2:
        combined_text = f"{chief_complaint or ''} {' '.join(symptoms_list)} {raw_transcript}".lower()
        for cat in ["onset", "associated_symptoms", "history", "medications"]:
            if cat not in categories and not is_category_already_answered(
                cat, duration, symptoms_list, conditions_list, combined_text
            ):
                categories.append(cat)  # type: ignore
            if len(categories) >= 2:
                break
    categories = categories[:3]

    # Attempt LLM contextual adaptation if client is available
    if llm_client:
        try:
            prompt_lang = "Tamil" if language == "ta" else "English"
            prompt = (
                f"You are a clinical triage intake assistant. Given the patient's statement:\n"
                f"\"{raw_transcript}\"\n\n"
                f"Generate exactly {len(categories)} adaptive follow-up questions in {prompt_lang}.\n"
                f"You MUST use each of these categories exactly once: {', '.join(categories)}.\n"
                f"Format your response as a JSON array of objects with keys 'category' and 'question'.\n"
                f"Example: [{{\"category\": \"onset\", \"question\": \"...\"}}]\n"
                f"Do not include diagnosis or recommendations. Output only valid JSON."
            )
            if hasattr(llm_client, "models") and hasattr(llm_client.models, "generate_content"):
                resp = llm_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                )
                raw_text = resp.text if hasattr(resp, "text") else str(resp)
            elif hasattr(llm_client, "generate_content"):
                resp = llm_client.generate_content(prompt)
                raw_text = resp.text if hasattr(resp, "text") else str(resp)
            else:
                raw_text = ""

            cleaned_text = raw_text.strip()
            if "```json" in cleaned_text:
                cleaned_text = cleaned_text.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_text:
                cleaned_text = cleaned_text.split("```")[1].split("```")[0].strip()
            parsed = json.loads(cleaned_text)
            if isinstance(parsed, list) and len(parsed) >= 2:
                llm_questions: list[FollowUpQuestion] = []
                for item in parsed[:3]:
                    cat = item.get("category")
                    q = item.get("question")
                    if cat in ALLOWED_CATEGORIES and q and isinstance(q, str):
                        llm_questions.append(
                            FollowUpQuestion(
                                category=cat,  # type: ignore
                                question=q.strip(),
                                language=language,
                            )
                        )
                if len(llm_questions) >= 2:
                    return llm_questions[:3]
        except Exception as e:
            logger.warning(f"LLM follow-up generation failed, falling back to deterministic bank: {e}")

    # Deterministic fallback
    return generate_deterministic_followups(categories=categories, language=language)
