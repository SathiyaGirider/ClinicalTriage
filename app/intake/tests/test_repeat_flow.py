"""
Tests for 'repeat the question' intent handling in the kiosk conversation flow.

Verifies:
1. Intent detection of common English, Tamil, and transliterated repeat phrases.
2. Clinical phrasing safety (e.g. 'fever again' is NOT treated as a repeat request).
3. State machine flow: re-speaking the current question up to 2 times without advancing or extracting.
4. Capping repeats at 2 attempts: 3rd repeat request proceeds with 'unspecified' without looping indefinitely.
5. Successful recovery when patient provides a clinical answer after requesting a repeat.
"""

import pytest
from app.intake.conversation import (
    is_repeat_request,
    ConversationManager,
    INITIAL_CHIEF_COMPLAINT_PROMPT,
    AGE_QUESTION_PROMPT,
)


class TestRepeatIntentDetection:
    """Unit tests for is_repeat_request pattern matching."""

    @pytest.mark.parametrize(
        "phrase",
        [
            "please repeat",
            "Please repeat",
            "repeat please",
            "repeat",
            "repeat the question",
            "can you repeat",
            "can you please repeat that",
            "could you repeat that",
            "say again",
            "say that again",
            "could you say that again",
            "tell me again",
            "once more",
            "one more time",
            "again",
            "pardon",
            "pardon me",
            "beg your pardon",
            "what was that",
            "what did you say",
            "i didn't hear",
            "could not hear",
            "didn't catch that",
            "sorry what",
            "come again",
        ],
    )
    def test_english_repeat_phrases(self, phrase: str):
        assert is_repeat_request(phrase) is True, f"Failed to recognize English repeat phrase: '{phrase}'"

    @pytest.mark.parametrize(
        "phrase",
        [
            "திருப்பியும் சொல்லுங்க",
            "திருப்பியும் சொல்லு",
            "திருப்பியும்",
            "மறுபடியும் சொல்லுங்க",
            "மறுபடியும் சொல்லு",
            "மறுபடியும்",
            "திரும்பவும் சொல்லுங்க",
            "திரும்ப சொல்லுங்க",
            "மீண்டும் சொல்லுங்கள்",
            "மீண்டும் சொல்லுங்க",
            "இன்னொரு முறை சொல்லுங்க",
            "இன்னொரு தடவை சொல்லுங்க",
            "இன்னொரு வாட்டி சொல்லுங்க",
            "கேட்கவில்லை",
            "கேக்கல",
            "சரியா கேக்கல",
            "என்ன சொன்னீங்க",
            "என்ன கேட்டீங்க",
            "எனக்கு கேக்கல",
        ],
    )
    def test_tamil_repeat_phrases(self, phrase: str):
        assert is_repeat_request(phrase) is True, f"Failed to recognize Tamil repeat phrase: '{phrase}'"

    @pytest.mark.parametrize(
        "phrase",
        [
            "marupadiyum sollunga",
            "marubadiyum sollunga",
            "thiruppiyum sollunga",
            "thirumba sollunga",
            "innoru thadava sollunga",
            "enna sonninga",
            "seriya kekala",
        ],
    )
    def test_transliterated_tamil_repeat_phrases(self, phrase: str):
        assert is_repeat_request(phrase) is True, f"Failed to recognize transliterated phrase: '{phrase}'"

    @pytest.mark.parametrize(
        "clinical_phrase",
        [
            "I have fever again",
            "fever started again yesterday",
            "severe headache and pain again",
            "pain again since yesterday",
            "காய்ச்சல் மறுபடியும் வந்தது",
            "ரெண்டு நாளா காய்ச்சல் இருக்கு",
            "தலைவலி",
            "3 days",
            "45 years old",
            "45",
            "chest pain for two hours",
            "vomiting since morning",
        ],
    )
    def test_clinical_phrases_not_repeat_request(self, clinical_phrase: str):
        assert is_repeat_request(clinical_phrase) is False, f"Clinical phrase falsely matched as repeat: '{clinical_phrase}'"


class TestConversationManagerRepeatFlow:
    """Integration tests for kiosk state machine repeat handling."""

    def test_chief_complaint_repeat_and_continue(self):
        mgr = ConversationManager()
        start = mgr.start_kiosk(language="en")
        session_id = start["session_id"]
        assert start["question_index"] == 1
        assert start["spoken_text"] == INITIAL_CHIEF_COMPLAINT_PROMPT["en"]

        # Attempt 1: Patient asks to repeat
        rep1 = mgr.process_patient_speech(session_id, user_speech="please repeat")
        assert rep1["is_repeat"] is True
        assert rep1["repeat_count"] == 1
        assert rep1["question_index"] == 1
        assert rep1["spoken_text"] == INITIAL_CHIEF_COMPLAINT_PROMPT["en"]
        assert rep1["category"] == "chief_complaint"

        session = mgr._sessions[session_id]
        # Transcripts must NOT accumulate the repeat phrase
        assert "please repeat" not in session.accumulated_transcripts
        assert "chief_complaint" not in session.follow_up_answers

        # Attempt 2: Patient asks to repeat again
        rep2 = mgr.process_patient_speech(session_id, user_speech="say again")
        assert rep2["is_repeat"] is True
        assert rep2["repeat_count"] == 2
        assert rep2["question_index"] == 1

        # Patient now answers the question
        ans = mgr.process_patient_speech(session_id, user_speech="severe headache and fever for 2 days")
        assert ans.get("is_repeat") is not True
        assert ans["question_index"] == 2
        assert ans["category"] == "age"
        assert ans["spoken_text"] == AGE_QUESTION_PROMPT["en"]

        # Verified clean data
        assert session.accumulated_transcripts == ["severe headache and fever for 2 days"]
        assert session.follow_up_answers["chief_complaint"] == "severe headache and fever for 2 days"
        assert session.repeat_count == 0

    def test_repeat_cap_at_two_attempts_advances_without_looping(self):
        mgr = ConversationManager()
        start = mgr.start_kiosk(language="en")
        session_id = start["session_id"]

        # Repeat 1
        rep1 = mgr.process_patient_speech(session_id, user_speech="please repeat")
        assert rep1["is_repeat"] is True
        assert rep1["repeat_count"] == 1

        # Repeat 2
        rep2 = mgr.process_patient_speech(session_id, user_speech="one more time")
        assert rep2["is_repeat"] is True
        assert rep2["repeat_count"] == 2

        # Repeat 3 (exceeds cap of 2) -> advances with unspecified
        step3 = mgr.process_patient_speech(session_id, user_speech="repeat again")
        assert step3.get("is_repeat") is not True
        # Must advance to age question rather than repeating indefinitely
        assert step3["category"] == "age"
        assert step3["question_index"] == 2
        assert step3["spoken_text"] == AGE_QUESTION_PROMPT["en"]

        session = mgr._sessions[session_id]
        assert session.repeat_count == 0
        assert session.follow_up_answers["chief_complaint"] == "unspecified"

    def test_tamil_followup_repeat_flow(self):
        mgr = ConversationManager()
        start = mgr.start_kiosk(language="ta")
        session_id = start["session_id"]
        assert start["category"] == "chief_complaint"

        # Answer chief complaint in Tamil
        step1 = mgr.process_patient_speech(session_id, user_speech="காய்ச்சல் மற்றும் இருமல்")
        assert step1["category"] == "age"
        assert step1["spoken_text"] == AGE_QUESTION_PROMPT["ta"]

        # Answer age
        step2 = mgr.process_patient_speech(session_id, user_speech="40")
        assert step2["category"] != "age"
        followup_q_text = step2["spoken_text"]
        followup_category = step2["category"]

        # Patient asks to repeat the follow-up question in Tamil
        rep = mgr.process_patient_speech(session_id, user_speech="மறுபடியும் சொல்லுங்க")
        assert rep["is_repeat"] is True
        assert rep["repeat_count"] == 1
        assert rep["spoken_text"] == followup_q_text
        assert rep["category"] == followup_category

        # Patient answers the follow-up question
        ans = mgr.process_patient_speech(session_id, user_speech="மூன்று நாட்களாக")
        assert ans.get("is_repeat") is not True
        session = mgr._sessions[session_id]
        assert "மறுபடியும் சொல்லுங்க" not in session.accumulated_transcripts
        assert session.follow_up_answers[followup_category] == "மூன்று நாட்களாக"
