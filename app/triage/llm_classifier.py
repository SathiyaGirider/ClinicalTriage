"""
LLM-based classification for non-emergency cases.

Only runs when check_red_flags() returned None — i.e., no hardcoded
red flag matched. Classifies the case as "same-day" or "routine" using
an LLM, and reports the LLM's own confidence in that call.
"""

import json
import os

import requests
from dotenv import load_dotenv

from app.common.schemas import IntakeResult

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.6-flash"
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

USE_MOCK_LLM = os.getenv("USE_MOCK_LLM", "false").lower() == "true"

SYSTEM_INSTRUCTIONS = """
You are a medical triage assistant helping classify patient urgency.
You do NOT diagnose. You only classify into one of two categories:

- "same-day": Concerning symptoms needing medical attention within 24 hours.
  Examples: persistent high fever, worsening infection, moderate uncontrolled pain,
  worsening chronic condition symptoms.

- "routine": Mild, stable symptoms that can wait for a normal appointment.
  Examples: mild cold, minor ache, routine checkup request, low-grade short-term fever.

Never suggest medication. Never state a diagnosis.
If symptoms are vague, contradictory, or don't clearly match either category,
set confidence to "low" rather than guessing.

Respond ONLY in this exact JSON format, nothing else:
{"priority": "same-day" or "routine", "confidence": "high" or "medium" or "low", "reason": "short plain-language reason"}
"""


def _build_patient_text(intake: IntakeResult) -> str:
    """Format intake data into a plain-text patient summary for the LLM."""
    symptoms_str = ", ".join(intake.symptoms) if intake.symptoms else "none reported"
    conditions_str = (
        ", ".join(intake.known_conditions) if intake.known_conditions else "none"
    )
    return (
        f"Chief complaint: {intake.chief_complaint}\n"
        f"Duration: {intake.duration}\n"
        f"Symptoms: {symptoms_str}\n"
        f"Known conditions: {conditions_str}"
    )


def classify_with_llm(intake_result: IntakeResult) -> tuple[str, str, str]:
    """Call the Gemini API to classify patient urgency.

    Args:
        intake_result: Structured intake data for the patient.

    Returns:
        A tuple of (priority, confidence, reason) parsed from the LLM response.

    Raises:
        RuntimeError: If the API key is missing, the API call fails,
                      or the response cannot be parsed.
    """
    if USE_MOCK_LLM:
        return "same-day", "medium", "MOCKED response — real LLM not called."

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to your .env file."
        )

    patient_text = _build_patient_text(intake_result)

    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_INSTRUCTIONS}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": patient_text}],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }

    response = requests.post(
        GEMINI_API_URL,
        params={"key": GEMINI_API_KEY},
        json=payload,
        timeout=30,
    )

    if not response.ok:
        raise RuntimeError(
            f"Gemini API request failed [{response.status_code}]: {response.text}"
        )

    response_data = response.json()

    try:
        raw_text = (
            response_data["candidates"][0]["content"]["parts"][0]["text"]
        )
        result = json.loads(raw_text)
        priority: str = result["priority"]
        confidence: str = result["confidence"]
        reason: str = result["reason"]
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Failed to parse Gemini response: {exc}\nRaw response: {response_data}"
        ) from exc

    return priority, confidence, reason