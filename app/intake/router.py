"""
FastAPI APIRouter for the Intake module.

Exposes:
- POST /intake: Main intake endpoint returning a valid IntakeResult
  strictly conforming to app.common.schemas.IntakeResult.
- POST /intake/envelope: Extended endpoint returning IntakeResult alongside
  suggested adaptive follow-up questions and deterministic red-flags.
- POST /intake/questions: Dedicated adaptive follow-up question generator.
- GET /intake/health: Liveness and status check.
"""

from fastapi import APIRouter, HTTPException, status
from app.common.schemas import IntakeResult
from app.intake.schemas import (
    IntakeRequest,
    IntakeResponseEnvelope,
    FollowUpRequest,
    FollowUpResponse,
)
from app.intake.extractor import extract_intake
from app.intake.redflag_scan import scan_red_flags
from app.intake.followup import generate_followup_questions

router = APIRouter(prefix="/intake", tags=["Patient Intake"])


@router.post(
    "",
    response_model=IntakeResult,
    status_code=status.HTTP_200_OK,
    summary="Process patient intake transcript",
    description=(
        "Receives verbatim raw speech transcript (in English or Tamil), executes "
        "hybrid LLM + deterministic extraction with red-flag guardrails, computes "
        "deterministic input_confidence, and returns a valid IntakeResult matching schemas.py."
    ),
)
async def process_intake(request: IntakeRequest) -> IntakeResult:
    if not request.raw_transcript or not request.raw_transcript.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="raw_transcript cannot be empty.",
        )
    result = extract_intake(request)
    save_record(result)
    return result


@router.post(
    "/envelope",
    response_model=IntakeResponseEnvelope,
    status_code=status.HTTP_200_OK,
    summary="Process intake with adaptive follow-ups and red-flag preview",
    description=(
        "Returns the strict IntakeResult along with 4-6 adaptive follow-up questions "
        "and detected red-flag terms for UI or client orchestration."
    ),
)
async def process_intake_envelope(request: IntakeRequest) -> IntakeResponseEnvelope:
    if not request.raw_transcript or not request.raw_transcript.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="raw_transcript cannot be empty.",
        )

    intake_res = extract_intake(request)
    red_flag_keys = scan_red_flags(request.raw_transcript)
    followups = generate_followup_questions(
        chief_complaint=intake_res.chief_complaint,
        duration=intake_res.duration,
        symptoms=intake_res.symptoms,
        known_conditions=intake_res.known_conditions,
        language=request.language,
        raw_transcript=request.raw_transcript,
    )

    return IntakeResponseEnvelope(
        intake_result=intake_res,
        suggested_followups=followups,
        red_flags_detected=red_flag_keys,
    )


@router.post(
    "/questions",
    response_model=FollowUpResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate adaptive follow-up questions",
    description="Generates 4-6 constrained follow-up questions in the chosen language (en/ta).",
)
async def generate_questions(request: FollowUpRequest) -> FollowUpResponse:
    questions = generate_followup_questions(
        chief_complaint=request.chief_complaint,
        duration=request.duration,
        symptoms=request.symptoms,
        language=request.language,
        raw_transcript=request.raw_transcript,
    )
    return FollowUpResponse(questions=questions)


@router.get(
    "/health",
    summary="Intake service health check",
    description="Returns module operational health and supported capabilities.",
)
async def health_check():
    return {
        "status": "healthy",
        "module": "intake",
        "supported_languages": ["en", "ta"],
        "speech_stt": "Web Speech API (client-side passthrough)",
        "speech_tts": "Web SpeechSynthesis API (client-side voice)",
        "interface": "voice_first_conversational_kiosk",
        "extraction_pipeline": "hybrid_llm_deterministic_guardrails",
    }


# ============================================================
# Conversational Kiosk State Machine Endpoints & Demo Store
# ============================================================

from typing import Literal
from pydantic import BaseModel
from app.intake.conversation import conversation_manager
from app.intake.records import get_records, save_record


class KioskStartRequest(BaseModel):
    session_id: str | None = None
    language: Literal["en", "ta"] = "en"


class KioskStepRequest(BaseModel):
    session_id: str
    user_speech: str = ""
    is_silence_freeze: bool = False


@router.post(
    "/kiosk/start",
    summary="Start new conversational kiosk session with locked language",
    description="Initializes kiosk session in chosen language ('en' or 'ta') and begins question loop.",
)
async def kiosk_start(req: KioskStartRequest | None = None):
    sid = req.session_id if req else None
    lang = req.language if req else "en"
    return conversation_manager.start_kiosk(session_id=sid, language=lang)


@router.post(
    "/kiosk/step",
    summary="Advance conversational kiosk state machine",
    description="Processes patient voice input according to current state (question loop).",
)
async def kiosk_step(req: KioskStepRequest):
    try:
        session = conversation_manager.get_or_create_session(req.session_id)
        if session.state == "question_loop":
            return conversation_manager.process_patient_speech(
                req.session_id,
                req.user_speech,
                is_silence_freeze=req.is_silence_freeze,
            )
        elif session.state == "closing":
            return conversation_manager.finalize_kiosk(req.session_id)
        else:
            return conversation_manager.start_kiosk(req.session_id, language=session.language)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error in kiosk_step endpoint: {e}", exc_info=True)
        # Never return raw 500 error to the kiosk; recover safely
        return conversation_manager.finalize_kiosk(req.session_id)


@router.post(
    "/kiosk/reset",
    summary="Reset kiosk session to idle",
)
async def kiosk_reset(req: KioskStartRequest):
    if req.session_id:
        conversation_manager._sessions.pop(req.session_id, None)
    return {"status": "reset", "state": "idle"}


@router.get(
    "/records",
    summary="List completed intake records (Demo Store)",
    description="Returns an in-memory chronological list of all captured IntakeResult entries (most recent first).",
)
async def list_records():
    return get_records()


@router.get(
    "/tts",
    summary="Audio TTS proxy for clinical kiosk speech",
)
async def audio_tts(text: str, lang: str = "ta"):
    import requests
    from fastapi.responses import Response
    
    clean_text = text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    target_lang = "ta" if lang.startswith("ta") else "en"
    try:
        url = "https://translate.google.com/translate_tts"
        params = {
            "ie": "UTF-8",
            "tl": target_lang,
            "client": "tw-ob",
            "q": clean_text[:250],
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://translate.google.com/",
        }
        r = requests.get(url, params=params, headers=headers, timeout=5)
        if r.status_code == 200 and len(r.content) > 100:
            return Response(content=r.content, media_type="audio/mpeg")
    except Exception as err:
        import logging
        logging.getLogger(__name__).warning(f"Audio TTS fetch fallback triggered: {err}")

    raise HTTPException(status_code=502, detail="TTS service unavailable")



@router.get(
    "/run-scenario-tests",
    summary="Execute test suites and return scenario report",
)
async def run_scenario_tests():
    import io
    import sys
    import unittest

    # Force complete fresh import of all intake modules and tests from disk
    intake_keys = [k for k in list(sys.modules.keys()) if k.startswith("app.intake")]
    for k in intake_keys:
        del sys.modules[k]

    import app.intake.tests.test_intake as test_intake
    import app.intake.tests.test_shared_scenarios as test_shared_scenarios

    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)

    loader = unittest.TestLoader()
    suite1 = loader.loadTestsFromModule(test_intake)
    res1 = runner.run(suite1)

    suite2 = loader.loadTestsFromModule(test_shared_scenarios)
    res2 = runner.run(suite2)

    scenario_reports = test_shared_scenarios.generate_scenario_report()

    return {
        "test_intake": {


            "was_successful": res1.wasSuccessful(),
            "tests_run": res1.testsRun,
            "failures": len(res1.failures),
            "errors": len(res1.errors),
        },
        "test_shared_scenarios": {
            "was_successful": res2.wasSuccessful(),
            "tests_run": res2.testsRun,
            "failures": len(res2.failures),
            "errors": len(res2.errors),
        },
        "log_output": stream.getvalue(),
        "scenarios": scenario_reports,
    }


