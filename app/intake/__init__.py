"""
ClinicalTriage — Intake Module (Person A).

Provides bilingual (English/Tamil) voice and text patient intake with:
- Browser-native Web Speech API passthrough
- Hybrid LLM + deterministic guardrail extraction
- Deterministic emergency red-flag scanner
- Constrained adaptive follow-up generator
- Fully deterministic input_confidence calculation
- Strict IntakeResult schema conformity (A -> B contract)
"""

from app.intake.extractor import extract_intake
from app.intake.redflag_scan import scan_red_flags, get_canonical_red_flag_symptoms
from app.intake.confidence import compute_input_confidence
from app.intake.followup import generate_followup_questions
from app.intake.stt import get_transcript, SpeechToTextProvider
from app.intake.tts import speak, TTSProvider
from app.intake.conversation import conversation_manager, ConversationManager
from app.intake.records import get_records, save_record, clear_records
from app.intake.schemas import IntakeRequest, IntakeResponseEnvelope, FollowUpQuestion
from app.intake.router import router

__all__ = [
    "extract_intake",
    "scan_red_flags",
    "get_canonical_red_flag_symptoms",
    "compute_input_confidence",
    "generate_followup_questions",
    "get_transcript",
    "SpeechToTextProvider",
    "speak",
    "TTSProvider",
    "conversation_manager",
    "ConversationManager",
    "get_records",
    "save_record",
    "clear_records",
    "IntakeRequest",
    "IntakeResponseEnvelope",
    "FollowUpQuestion",
    "router",
]
