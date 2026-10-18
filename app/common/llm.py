"""
Small LLM client wrapper.

- AnthropicClient: Anthropic SDK, model and key from env (LLM_MODEL,
  ANTHROPIC_API_KEY), a hard timeout, and retries OFF.
- UnavailableClient: used when no key/model is configured. Every call raises
  LLMUnavailable so callers take their fail-safe path.
- FakeLLMClient: for tests and the CLI. Returns canned text, a callable's
  result, or raises a given exception.

Callers never see SDK types; they get a string back or an LLMError.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Protocol

from app.config import settings

logger = logging.getLogger("lifeline.llm")


class LLMError(RuntimeError):
    pass


class LLMUnavailable(LLMError):
    pass


class LLMTimeout(LLMError):
    pass


class LLMClient(Protocol):
    name: str

    def complete(self, system: str, user: str, max_tokens: int = 300, purpose: str = "") -> str: ...


class UnavailableClient:
    name = "unavailable"

    def complete(self, system: str, user: str, max_tokens: int = 300, purpose: str = "") -> str:
        raise LLMUnavailable("LLM not configured (ANTHROPIC_API_KEY / LLM_MODEL missing)")


class AnthropicClient:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout: float):
        import anthropic

        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=0)
        self._model = model

    def complete(self, system: str, user: str, max_tokens: int = 300, purpose: str = "") -> str:
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except self._anthropic.APITimeoutError as exc:
            raise LLMTimeout("LLM timed out") from exc
        except self._anthropic.APIError as exc:
            # Log the class only: the error body could echo the prompt.
            logger.warning("llm call failed purpose=%s error=%s", purpose, type(exc).__name__)
            raise LLMError(type(exc).__name__) from exc
        parts = [getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"]
        return "".join(parts)


class FakeLLMClient:
    """
    responses: either a single string, a dict purpose -> string, a callable
    (system, user, purpose) -> string, or an Exception instance to raise.
    """

    name = "fake"

    def __init__(self, responses: str | dict | Callable | Exception | None = None):
        self.responses = responses
        self.calls: list[dict] = []

    def complete(self, system: str, user: str, max_tokens: int = 300, purpose: str = "") -> str:
        self.calls.append({"system": system, "user": user, "purpose": purpose})
        r = self.responses
        if isinstance(r, dict):
            r = r.get(purpose, r.get("*"))
        if isinstance(r, Exception):
            raise r
        if callable(r):
            r = r(system, user, purpose)
            if isinstance(r, Exception):
                raise r
        if r is None:
            raise LLMUnavailable("fake client has no response for purpose=" + purpose)
        return r


class DemoStandInClient:
    """
    OPT-IN demo stand-in used ONLY when no real model is configured and
    DEMO_LLM_STANDIN=true. It is a fixed keyword heuristic, not AI: it answers
    "routine" only when every recognised symptom tag is in a short mild list,
    otherwise "same-day". Decisions it makes carry the audit note
    "demo_llm_standin". Rules still run first and are still authoritative.
    """

    name = "demo_standin"
    MILD = {"cold_symptoms", "cough", "sore_throat", "rash", "itching", "skin_problem", "joint_pain", "back_pain", "ear_problem",
            "headache", "fatigue", "body_pain", "nose_problem", "eye_problem"}

    def complete(self, system: str, user: str, max_tokens: int = 300, purpose: str = "") -> str:
        if purpose != "triage":
            raise LLMUnavailable("demo stand-in only rates urgency")
        import json
        import re
        m = re.search(r"\{.*\}", user, re.DOTALL)
        data = json.loads(m.group(0)) if m else {}
        tags = [t for t in data.get("symptom_tags", []) if t != "other"]
        mild = bool(tags) and all(t in self.MILD for t in tags)
        if mild:
            return json.dumps({"priority": "routine", "confidence": "medium",
                               "rationale": "Demo stand-in (no AI model configured): only mild, common symptoms were reported."})
        return json.dumps({"priority": "same-day", "confidence": "medium",
                           "rationale": "Demo stand-in (no AI model configured): symptoms not on the mild list, so a nurse should review today."})


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        if os.getenv("USE_MOCK_LLM", "false").lower() == "true":
            # Legacy switch from the original triage module.
            _client = FakeLLMClient('{"priority": "same-day", "confidence": "medium", "rationale": "MOCKED response - real LLM not called."}')
        elif settings.llm_configured:
            try:
                _client = AnthropicClient(settings.anthropic_api_key, settings.llm_model, settings.llm_timeout_seconds)
            except Exception as exc:  # SDK missing or bad config: fail safe
                logger.warning("anthropic client init failed: %s", type(exc).__name__)
                _client = UnavailableClient()
        elif os.getenv("DEMO_LLM_STANDIN", "false").lower() == "true":
            _client = DemoStandInClient()
        else:
            _client = UnavailableClient()
    return _client


def set_llm_client(client: LLMClient | None) -> None:
    """Override the process-wide client (tests, CLI). None resets to env-based."""
    global _client
    _client = client
