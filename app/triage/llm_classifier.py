"""
LLM-based classification for non-emergency cases.

Only runs when check_red_flags() returned None — i.e., no hardcoded
red flag matched. Classifies the case as "same-day" or "routine" using
an LLM (via Groq), and reports the LLM's own confidence in that call.
"""

import json
import os
import time

import requests
from dotenv import load_dotenv

from app.common.schemas import IntakeResult

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "openai/gpt-oss-20b"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

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


def classify_with_llm(intake_result: IntakeResult, max_retries: int = 2) -> tuple[str, str, str]:
    """Call the Groq API to classify patient urgency.

    Args:
        intake_result: Structured intake data for the patient.
        max_retries: Number of retry attempts on timeout/connection errors.

    Returns:
        A tuple of (priority, confidence, reason) parsed from the LLM response.

    Raises:
        RuntimeError: If the API key is missing, the API call fails after
                      retries, or the response cannot be parsed.
    """
    if USE_MOCK_LLM:
        return "same-day", "medium", "MOCKED response — real LLM not called."

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to your .env file."
        )

    patient_text = _build_patient_text(intake_result)

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": patient_text},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                GROQ_API_URL,
                headers=headers,
                json=payload,
                timeout=60,
            )

            if not response.ok:
                raise RuntimeError(
                    f"Groq API request failed [{response.status_code}]: {response.text}"
                )

            response_data = response.json()
            raw_text = response_data["choices"][0]["message"]["content"]
            result = json.loads(raw_text)

            return result["priority"], result["confidence"], result["reason"]

        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(2)
                continue
            raise RuntimeError(
                f"Groq API failed after {max_retries + 1} attempts: {last_error}"
            ) from last_error

        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Failed to parse Groq response: {exc}\nRaw response: {response_data}"
            ) from exc