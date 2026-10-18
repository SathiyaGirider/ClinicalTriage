"""
Conversational Kiosk State Machine.

Orchestrates the voice-first patient intake flow:
    idle -> (tap language button) -> question_loop -> closing -> idle

Eliminates voice-based language guessing: language is selected directly via
two large buttons ("English" / "தமிழ்") on the idle screen, and locked in
consistently for the entire session across TTS, captions, and STT.

Orchestration only: delegates extraction to extractor.py, follow-ups to followup.py,
confidence scoring to confidence.py, and red-flags to redflag_scan.py.
"""

import re
import uuid
import logging
from typing import Literal, Optional, Any
from pydantic import BaseModel, Field

from app.common.schemas import IntakeResult
from app.intake.schemas import IntakeRequest
from app.intake.extractor import extract_intake
from app.intake.followup import generate_followup_questions
from app.intake.redflag_scan import scan_red_flags
from app.intake.records import save_record

logger = logging.getLogger(__name__)

ConversationState = Literal["idle", "question_loop", "closing"]

INITIAL_CHIEF_COMPLAINT_PROMPT = {
    "en": "What is your main problem today?",
    "ta": "இன்று உங்களுக்கு என்ன முக்கிய பிரச்சனை?",
}

AGE_QUESTION_PROMPT = {
    "en": "What is your age?",
    "ta": "உங்கள் வயது என்ன?",
}

CLOSING_PROMPT = {
    "en": "Thank you. Your check-in is complete. Your token number is {token}. Please take a seat in the waiting area.",
    "ta": "நன்றி. உங்கள் பதிவு நிறைவடைந்தது. உங்கள் டோக்கன் எண் {token}. தயவுசெய்து காத்திருப்பு பகுதியில் அமர்ந்திருக்கவும்.",
}

EMERGENCY_CLOSING_PROMPT = {
    "en": "EMERGENCY: Immediate medical attention required. Please report to the health centre staff immediately. Your token number is {token}.",
    "ta": "அவசர எச்சரிக்கை: உடனடியாக நிலையப் பணியாளர்களை அணுகவும்! உங்கள் டோக்கன் எண் {token}.",
}

SILENCE_FREEZE_CLOSING_PROMPT = {
    "en": "Your token number is {token}. Please see the health centre staff for assistance.",
    "ta": "உங்கள் டோக்கன் எண் {token}. தயவுசெய்து நிலையப் பணியாளர்களை அணுகவும்.",
}

SILENCE_STRIKE_ONE_PROMPT = {
    "en": "I did not hear you. If you need help, please see the staff.",
    "ta": "நீங்கள் பேசுவது எனக்கு கேட்கவில்லை. உதவி தேவைப்பட்டால், நிலையப் பணியாளர்களை அணுகவும்.",
}

TAMIL_WORD_NUMBERS = {
    "ஒன்று": 1, "ஒரு": 1, "இரண்டு": 2, "ரெண்டு": 2, "மூன்று": 3, "மூணு": 3,
    "நான்கு": 4, "நாலு": 4, "ஐந்து": 5, "அஞ்சு": 5, "ஆறு": 6, "ஏழு": 7,
    "எட்டு": 8, "ஒன்பது": 9, "பத்து": 10, "இருபது": 20, "முப்பது": 30,
    "நாற்பது": 40, "ஐம்பது": 50, "அறுபது": 60, "எழுபது": 70, "எண்பது": 80,
    "தொண்ணூறு": 90, "நூறு": 100,
}


def parse_spoken_age(text: str) -> Optional[int]:
    """
    Parse numeric age from spoken answer. Returns int between 0 and 125, or None.
    Handles '45', '45 years old', 'வயது 45', '45 வயது', 'I am 32', etc.
    """
    if not text:
        return None
    # Check digits
    digits_match = re.search(r"\b(\d{1,3})\b", text)
    if digits_match:
        try:
            val = int(digits_match.group(1))
            if 0 <= val <= 125:
                return val
        except ValueError:
            pass
    # Check Tamil word numbers
    for word, num in TAMIL_WORD_NUMBERS.items():
        if word in text:
            return num
    return None


_kiosk_token_counter = 0


def get_next_kiosk_token() -> str:
    global _kiosk_token_counter
    _kiosk_token_counter += 1
    if _kiosk_token_counter > 999:
        _kiosk_token_counter = 1
    return f"{_kiosk_token_counter:03d}"


def is_repeat_request(text: str) -> bool:
    """
    Check whether a spoken patient utterance is an intent to repeat / clarify
    the question rather than a clinical answer.

    Supports both English and Tamil (including spoken colloquialisms and common
    transliterations / Tanglish).
    Guards against clinical utterances mentioning 'again' (e.g. 'fever again').
    """
    if not text:
        return False

    clean = text.strip().lower()
    # Strip common enclosing punctuation
    clean = re.sub(r"^[^\w\s\u0B80-\u0BFF]+|[^\w\s\u0B80-\u0BFF]+$", "", clean).strip()
    if not clean:
        return False

    # Standalone single words / short queries indicating repeat intent
    standalone_repeat_words = {
        # English
        "repeat", "again", "pardon", "pardon me", "sorry", "what", "excuse me", "sorry what",
        # Tamil
        "மறுபடியும்", "திருப்பியும்", "திரும்பவும்", "திரும்ப", "மீண்டும்",
        "கேட்கவில்லை", "கேக்கல", "புரியல", "புரியவில்லை", "விளங்கல", "என்ன",
        # Transliterated Tamil
        "marupadiyum", "marubadiyum", "thiruppi", "thiruppiyum", "thirumba",
        "thirumbavum", "meendum", "kekala", "puriyala",
    }
    if clean in standalone_repeat_words:
        return True

    # Multi-word explicit repeat patterns
    repeat_patterns = [
        # English phrases
        r"\b(?:please\s+)?repeat(?:\s+the\s+question|\s+again|\s+please|\s+that)?\b",
        r"\b(?:can|could|would)\s+you\s+(?:please\s+)?repeat(?:\s+the\s+question|\s+that|\s+again)?\b",
        r"\b(?:can|could|would)\s+you\s+(?:please\s+)?say\s+(?:that\s+)?again\b",
        r"\b(?:please\s+)?say\s+(?:it\s+|that\s+)?again\b",
        r"\b(?:please\s+)?tell\s+me\s+again\b",
        r"\b(?:one\s+more\s+time|once\s+more|once\s+again)\b",
        r"\bwhat\s+(?:was\s+that|did\s+you\s+say|did\s+you\s+ask|was\s+the\s+question|is\s+the\s+question)\b",
        r"\b(?:i\s+)?(?:did\s*n['o]?t|could\s*n['o]?t)\s+(?:hear|catch\s+that|understand)\b",
        r"\bcome\s+again\b",
        r"\bbeg\s+your\s+pardon\b",

        # Tamil phrases
        r"திருப்பியு?ம்\s*சொல்லு(?:ங்க|ங்கோ)?",
        r"மறுபடியு?ம்\s*சொல்லு(?:ங்க|ங்கோ)?",
        r"திரும்ப(?:வு)?ம்\s*சொல்லு(?:ங்க|ங்கோ)?",
        r"திரும்ப\s*சொல்லு(?:ங்க|ங்கோ)?",
        r"மீண்டும்\s*சொல்லு(?:ங்கள்|ங்க|ங்கோ)?",
        r"(?:இன்னொரு|ஒரு)\s*(?:முறை|தடவை|தடவ|வாட்டி)\s*சொல்லு(?:ங்க|ங்கோ)?",
        r"என்ன\s*சொன்னீ?ங்க",
        r"என்ன\s*கேட்டீ?ங்க",
        r"எனக்கு(?:க்)?\s*கேட்கவில்லை",
        r"எனக்கு(?:க்)?\s*கேக்கல",
        r"ஒண்ணு?மே\s*கேக்கல",
        r"ஒன்றும்\s*கேட்கவில்லை",
        r"சரியா\s*(?:கேக்கல|கேட்கவில்லை|விளங்கல|புரியல)",
        r"(?:கேக்கல|கேட்கவில்லை|புரியல|விளங்கல)\s*சொல்லு(?:ங்க|ங்கோ)?",

        # Transliterated phrases
        r"\b(?:marupadiyum|marubadiyum|thiruppiyum|thirumba)\s+sollunga\b",
        r"\binnoru\s+(?:thadava|murai|vaatti)\s+sollunga\b",
        r"\benna\s+(?:sonninga|kettinga)\b",
        r"\bseriya\s+kekala\b",
    ]

    for pattern in repeat_patterns:
        if re.search(pattern, clean, re.IGNORECASE):
            return True

    return False


class KioskSession(BaseModel):
    session_id: str
    patient_id: str
    state: ConversationState = "idle"
    language: Literal["en", "ta"] = "en"
    accumulated_transcripts: list[str] = Field(default_factory=list)
    follow_up_answers: dict[str, str] = Field(default_factory=dict)
    age: Optional[int] = None
    current_question_category: Optional[str] = None
    current_question_text: Optional[str] = None
    repeat_count: int = 0
    questions_asked_count: int = 0
    max_questions: int = 3  # max 3 adaptive follow-ups (excluding chief complaint and age)
    current_intake_result: Optional[IntakeResult] = None


class ConversationManager:
    """In-memory orchestration manager for kiosk sessions."""

    def __init__(self):
        self._sessions: dict[str, KioskSession] = {}

    def get_current_question_text(self, session: KioskSession, lang: str) -> str:
        """Return the current question prompt string for re-speaking via TTS."""
        if session.current_question_text:
            return session.current_question_text
        if session.current_question_category == "chief_complaint":
            return INITIAL_CHIEF_COMPLAINT_PROMPT[lang]
        elif session.current_question_category == "age":
            return AGE_QUESTION_PROMPT[lang]
        else:
            return (
                "எவ்வளவு நாட்களாக இந்த பிரச்சனை உள்ளது?"
                if lang == "ta"
                else "How many days have you had these symptoms?"
            )

    def get_current_question_index(self, session: KioskSession) -> int:
        """Return the 1-based question index of the active step."""
        if session.current_question_category == "chief_complaint":
            return 1
        elif session.current_question_category == "age":
            return 2
        else:
            return session.questions_asked_count + 2

    def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        language: Literal["en", "ta"] = "en",
    ) -> KioskSession:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        new_id = session_id or str(uuid.uuid4())
        fresh_patient_id = get_next_kiosk_token()
        session = KioskSession(
            session_id=new_id,
            patient_id=fresh_patient_id,
            language=language,
        )
        self._sessions[new_id] = session
        return session

    def start_kiosk(
        self,
        session_id: Optional[str] = None,
        language: Literal["en", "ta"] = "en",
    ) -> dict[str, Any]:
        """
        Direct language selection via tap button on idle screen.
        Locks in language for the entire session and initiates question loop immediately.
        """
        session = self.get_or_create_session(session_id, language=language)
        session.language = language
        session.state = "question_loop"
        session.accumulated_transcripts.clear()
        session.follow_up_answers.clear()
        session.age = None
        session.questions_asked_count = 0
        session.current_intake_result = None
        session.current_question_category = "chief_complaint"
        session.repeat_count = 0

        initial_q = INITIAL_CHIEF_COMPLAINT_PROMPT[language]
        session.current_question_text = initial_q
        listen_lang = "ta-IN" if language == "ta" else "en-US"

        return {
            "session_id": session.session_id,
            "patient_id": session.patient_id,
            "state": session.state,
            "selected_language": language,
            "spoken_text": initial_q,
            "spoken_lang": language,
            "display_text": initial_q,
            "listen_lang": listen_lang,
            "auto_stop": True,
            "category": "chief_complaint",
            "question_index": 1,
        }

    def handle_silence_freeze(self, session_id: str) -> dict[str, Any]:
        """
        Gracefully handles second-strike silence freeze by generating a
        valid schema-compliant blank IntakeResult and transitioning to closing.
        """
        from app.intake.extractor import create_silent_freeze_intake_result

        session = self.get_or_create_session(session_id)
        full_transcript = " ".join(session.accumulated_transcripts).strip() or "[no response captured — silence timeout]"
        intake_result = create_silent_freeze_intake_result(
            patient_id=session.patient_id,
            raw_transcript=full_transcript,
        )
        if session.age is not None:
            intake_result.age = session.age
        session.current_intake_result = intake_result
        return self.finalize_kiosk(session_id, is_silence_freeze=True)

    def process_patient_speech(
        self,
        session_id: str,
        user_speech: str = "",
        is_silence_freeze: bool = False,
    ) -> dict[str, Any]:
        """
        Process patient voice response, execute extraction pipeline, and advance.
        Guarantees session.language lock-in across TTS, captions, and STT.
        Short-circuits immediately if a red-flag condition is detected mid-conversation.
        """
        if is_silence_freeze:
            return self.handle_silence_freeze(session_id)

        session = self.get_or_create_session(session_id)
        lang = session.language
        listen_lang = "ta-IN" if lang == "ta" else "en-US"

        clean_utterance = user_speech.strip()

        # --- Check for "repeat the question" intent before extraction ---
        if is_repeat_request(clean_utterance):
            if session.repeat_count < 2:
                session.repeat_count += 1
                logger.info(
                    f"Repeat request detected in session {session_id} for '{session.current_question_category}' "
                    f"(attempt {session.repeat_count}/2). Re-speaking current question."
                )
                current_q = self.get_current_question_text(session, lang)
                q_idx = self.get_current_question_index(session)
                return {
                    "session_id": session.session_id,
                    "patient_id": session.patient_id,
                    "state": "question_loop",
                    "selected_language": lang,
                    "spoken_text": current_q,
                    "spoken_lang": lang,
                    "display_text": current_q,
                    "listen_lang": listen_lang,
                    "auto_stop": True,
                    "category": session.current_question_category or "chief_complaint",
                    "question_index": q_idx,
                    "is_repeat": True,
                    "repeat_count": session.repeat_count,
                    "current_confidence": session.current_intake_result.input_confidence if session.current_intake_result else "low",
                }
            else:
                logger.info(
                    f"Max repeat limit (2) reached for question '{session.current_question_category}' in session {session_id}. "
                    f"Proceeding without looping."
                )
                # Cap repeats at 2 attempts per question; proceed with field marked as unspecified
                session.repeat_count = 0
                clean_utterance = "unspecified"
        else:
            # Valid patient response received: reset repeat count for current question
            session.repeat_count = 0

        if clean_utterance:
            session.accumulated_transcripts.append(clean_utterance)

        # Record answer to previous category if applicable
        if session.current_question_category and clean_utterance:
            session.follow_up_answers[session.current_question_category] = clean_utterance

        # Combined raw transcript
        full_transcript = " ".join(session.accumulated_transcripts).strip()
        if not full_transcript:
            return self.handle_silence_freeze(session_id)

        try:
            # Check for mid-conversation red flags in utterance or full transcript
            detected_flags = scan_red_flags(full_transcript) or scan_red_flags(clean_utterance)

            # --- STEP A: Handled Chief Complaint -> Ask Age next ---
            if session.current_question_category == "chief_complaint":
                # Emergency red-flag short-circuit:
                if detected_flags:
                    intake_req = IntakeRequest(
                        raw_transcript=full_transcript,
                        language=lang,
                        patient_id=session.patient_id,
                        follow_up_answers=session.follow_up_answers,
                    )
                    session.current_intake_result = extract_intake(intake_req)
                    logger.warning(
                        f"Mid-conversation red flag detected on chief complaint in session {session_id}. "
                        f"Short-circuiting to emergency closing."
                    )
                    return self.finalize_kiosk(session_id, is_red_flag_alert=True)

                # Extract initial intake result from chief complaint
                intake_req = IntakeRequest(
                    raw_transcript=full_transcript,
                    language=lang,
                    patient_id=session.patient_id,
                    follow_up_answers=session.follow_up_answers,
                )
                session.current_intake_result = extract_intake(intake_req)

                # Set next category to age (separate upfront question; does NOT increment questions_asked_count)
                session.current_question_category = "age"
                session.repeat_count = 0
                age_q = AGE_QUESTION_PROMPT[lang]
                session.current_question_text = age_q
                return {
                    "session_id": session.session_id,
                    "patient_id": session.patient_id,
                    "state": "question_loop",
                    "selected_language": lang,
                    "spoken_text": age_q,
                    "spoken_lang": lang,
                    "display_text": age_q,
                    "listen_lang": listen_lang,
                    "auto_stop": True,
                    "category": "age",
                    "question_index": 2,
                }

            # --- STEP B: Handled Age -> Parse age, run extraction, ask first adaptive follow-up ---
            if session.current_question_category == "age":
                # Parse numeric age (or None if unclear, without blocking/retrying)
                session.age = parse_spoken_age(clean_utterance)

                # Run extraction pipeline
                intake_req = IntakeRequest(
                    raw_transcript=full_transcript,
                    language=lang,
                    patient_id=session.patient_id,
                    age=session.age,
                    follow_up_answers=session.follow_up_answers,
                )
                intake_result = extract_intake(intake_req)
                session.current_intake_result = intake_result

                # Emergency red-flag short-circuit
                if detected_flags:
                    logger.warning(
                        f"Mid-conversation red flag detected after age in session {session_id}. "
                        f"Short-circuiting to emergency closing."
                    )
                    return self.finalize_kiosk(session_id, is_red_flag_alert=True)

                # Generate adaptive follow-ups (progression removed, max 3)
                followups = generate_followup_questions(
                    chief_complaint=intake_result.chief_complaint,
                    duration=intake_result.duration,
                    symptoms=intake_result.symptoms,
                    known_conditions=intake_result.known_conditions,
                    language=lang,
                    raw_transcript=full_transcript,
                )
                unanswered = [
                    q for q in followups
                    if q.category not in session.follow_up_answers
                ]
                if not unanswered:
                    return self.finalize_kiosk(session_id)

                next_q = unanswered[0]
                session.current_question_category = next_q.category
                session.current_question_text = next_q.question
                session.repeat_count = 0
                session.questions_asked_count += 1
                return {
                    "session_id": session.session_id,
                    "patient_id": session.patient_id,
                    "state": "question_loop",
                    "selected_language": lang,
                    "spoken_text": next_q.question,
                    "spoken_lang": lang,
                    "display_text": next_q.question,
                    "listen_lang": listen_lang,
                    "auto_stop": True,
                    "category": next_q.category,
                    "question_index": session.questions_asked_count + 2,
                    "current_confidence": intake_result.input_confidence,
                }

            # --- STEP C: Handled Adaptive Follow-Up Question ---
            intake_req = IntakeRequest(
                raw_transcript=full_transcript,
                language=lang,
                patient_id=session.patient_id,
                age=session.age,
                follow_up_answers=session.follow_up_answers,
            )
            intake_result = extract_intake(intake_req)
            session.current_intake_result = intake_result

            # Mid-conversation red-flag short-circuit:
            if detected_flags:
                logger.warning(
                    f"Mid-conversation red flag detected in session {session_id}. "
                    f"Short-circuiting to emergency closing."
                )
                return self.finalize_kiosk(session_id, is_red_flag_alert=True)

            # Check termination condition:
            # High confidence after at least 2 follow-ups, or maximum 3 follow-ups reached
            is_high_confidence = intake_result.input_confidence == "high" and session.questions_asked_count >= 2
            is_max_reached = session.questions_asked_count >= session.max_questions

            if is_max_reached or is_high_confidence:
                return self.finalize_kiosk(session_id)

            # Generate next follow-up question via existing followup.py (locked to lang)
            followups = generate_followup_questions(
                chief_complaint=intake_result.chief_complaint,
                duration=intake_result.duration,
                symptoms=intake_result.symptoms,
                known_conditions=intake_result.known_conditions,
                language=lang,
                raw_transcript=full_transcript,
            )

            # Filter out questions whose categories have already been answered
            unanswered = [
                q for q in followups
                if q.category not in session.follow_up_answers
            ]

            if not unanswered:
                return self.finalize_kiosk(session_id)

            next_q = unanswered[0]
            session.current_question_category = next_q.category
            session.current_question_text = next_q.question
            session.repeat_count = 0
            session.questions_asked_count += 1

            return {
                "session_id": session.session_id,
                "patient_id": session.patient_id,
                "state": "question_loop",
                "selected_language": lang,
                "spoken_text": next_q.question,
                "spoken_lang": lang,
                "display_text": next_q.question,
                "listen_lang": listen_lang,
                "auto_stop": True,
                "category": next_q.category,
                "question_index": session.questions_asked_count + 2,
                "current_confidence": intake_result.input_confidence,
            }
        except Exception as err:
            logger.error(f"Error processing speech in session {session_id}: {err}", exc_info=True)
            # Graceful recovery: ensure a valid IntakeResult exists and proceed with safe fallback question
            if not session.current_intake_result:
                from app.intake.extractor import create_silent_freeze_intake_result
                session.current_intake_result = create_silent_freeze_intake_result(
                    patient_id=session.patient_id,
                    raw_transcript=full_transcript,
                )
            if session.age is not None:
                session.current_intake_result.age = session.age
            session.questions_asked_count += 1
            if session.questions_asked_count >= session.max_questions:
                return self.finalize_kiosk(session_id)
            fallback_q = (
                "எவ்வளவு நாட்களாக இந்த பிரச்சனை உள்ளது?"
                if lang == "ta"
                else "How many days have you had these symptoms?"
            )
            session.current_question_category = "onset"
            session.current_question_text = fallback_q
            session.repeat_count = 0
            return {
                "session_id": session.session_id,
                "patient_id": session.patient_id,
                "state": "question_loop",
                "selected_language": lang,
                "spoken_text": fallback_q,
                "spoken_lang": lang,
                "display_text": fallback_q,
                "listen_lang": listen_lang,
                "auto_stop": True,
                "category": "onset",
                "question_index": session.questions_asked_count + 2,
                "current_confidence": session.current_intake_result.input_confidence,
            }

    def finalize_kiosk(
        self,
        session_id: str,
        is_red_flag_alert: bool = False,
        is_silence_freeze: bool = False,
    ) -> dict[str, Any]:
        """
        Transition to closing screen.
        Speaks the token number out loud and saves IntakeResult to demo records store.
        """
        session = self.get_or_create_session(session_id)
        session.state = "closing"
        lang = session.language
        patient_id = session.patient_id

        if is_red_flag_alert:
            closing_msg = EMERGENCY_CLOSING_PROMPT[lang].format(token=patient_id)
        elif is_silence_freeze:
            closing_msg = SILENCE_FREEZE_CLOSING_PROMPT[lang].format(token=patient_id)
        else:
            closing_msg = CLOSING_PROMPT[lang].format(token=patient_id)

        result_payload = None
        if session.current_intake_result:
            if session.age is not None:
                session.current_intake_result.age = session.age
            result_payload = session.current_intake_result.model_dump()
            # Save to demo records store
            save_record(session.current_intake_result)

        # Clean up session instance
        self._sessions.pop(session_id, None)

        return {
            "session_id": session.session_id,
            "patient_id": patient_id,
            "state": "closing",
            "selected_language": lang,
            "spoken_text": closing_msg,
            "spoken_lang": lang,
            "display_text": closing_msg,
            "intake_result": result_payload,
            "is_red_flag": is_red_flag_alert,
            "is_silence_freeze": is_silence_freeze,
            "auto_stop": False,
            "reset_delay_ms": 7000,
        }


# Global conversation manager instance
conversation_manager = ConversationManager()
