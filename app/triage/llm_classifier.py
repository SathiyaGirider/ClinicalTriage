"""
LLM-based urgency estimate for cases where NO hardcoded rule fired.

Originally a Groq HTTP call (Person B); now goes through the shared client
wrapper in app/common/llm.py (Anthropic SDK, model + key from env, timeout,
no retries, fake client in tests). The public function keeps its
(priority, confidence, reason) return shape.

The LLM only sees a sanitised structured subset (tags, duration, age, known
conditions, follow-up answers, short chief complaint) inside a data block.
Any failure raises RuntimeError so the caller takes the fail-safe path.
"""

import json
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.common.llm import LLMClient, LLMError, get_llm_client
from app.common.schemas import IntakeResult
from app.triage.prompts import TRIAGE_SYSTEM, wrap_data
from app.triage.sanitizer import structured_subset


class LLMTriageOutput(BaseModel):
    priority: Literal["emergency", "same-day", "routine"]
    confidence: Literal["high", "medium", "low"]
    rationale: str = Field(min_length=1, max_length=400)


def _parse(raw: str) -> LLMTriageOutput:
    text = (raw or "").strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("no JSON object in LLM output")
    data = json.loads(m.group(0))
    if "rationale" not in data and "reason" in data:  # tolerate the legacy key
        data["rationale"] = data.pop("reason")
    return LLMTriageOutput.model_validate(data)


def classify_with_llm(
    intake_result: IntakeResult,
    max_retries: int = 0,
    client: LLMClient | None = None,
    tags: list[str] | None = None,
) -> tuple[str, str, str]:
    """Return (priority, confidence, rationale). Raises RuntimeError on any failure."""
    client = client or get_llm_client()
    payload = structured_subset(intake_result, tags if tags is not None else list(intake_result.symptom_tags or []))
    try:
        raw = client.complete(TRIAGE_SYSTEM, wrap_data(payload), max_tokens=200, purpose="triage")
        out = _parse(raw)
    except (LLMError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"llm_unusable:{type(exc).__name__}") from exc
    return out.priority, out.confidence, out.rationale.strip()
