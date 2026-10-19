"""
Tests for GroqClient (app/common/llm.py).

All tests monkeypatch requests.post; no real network call is made.
"""

import json
import types
import pytest

from app.common.llm import GroqClient, LLMError, LLMTimeout

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
API_KEY = "test-key"
MODEL = "test-model"
TIMEOUT = 8.0


def _make_client():
    return GroqClient(api_key=API_KEY, model=MODEL, timeout=TIMEOUT, url=GROQ_URL)


def _fake_response(status_code: int, body: dict):
    """Build a minimal fake requests.Response."""
    resp = types.SimpleNamespace()
    resp.status_code = status_code
    resp.json = lambda: body
    return resp


# ---------------------------------------------------------------------------
# Test 1: 200 OK → returns text content; validates request shape
# ---------------------------------------------------------------------------

def test_successful_completion(monkeypatch):
    """A 200 response with valid JSON returns the message content."""
    body = {"choices": [{"message": {"content": "hello"}}]}
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json
        return _fake_response(200, body)

    client = _make_client()
    monkeypatch.setattr(client._requests, "post", fake_post)

    result = client.complete(system="sys", user="usr")

    assert result == "hello"
    assert captured["url"] == GROQ_URL
    assert captured["headers"]["Authorization"] == f"Bearer {API_KEY}"
    messages = captured["body"]["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "model" in captured["body"]


# ---------------------------------------------------------------------------
# Test 2: requests.exceptions.Timeout → raises LLMTimeout
# ---------------------------------------------------------------------------

def test_timeout_raises_llm_timeout(monkeypatch):
    """A requests Timeout exception is re-raised as LLMTimeout."""
    client = _make_client()
    import requests

    def fake_post(*args, **kwargs):
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr(client._requests, "post", fake_post)

    with pytest.raises(LLMTimeout):
        client.complete(system="sys", user="usr")


# ---------------------------------------------------------------------------
# Test 3: HTTP 500 → raises LLMError
# ---------------------------------------------------------------------------

def test_http_500_raises_llm_error(monkeypatch):
    """A non-200 HTTP status code is raised as LLMError."""
    client = _make_client()

    def fake_post(*args, **kwargs):
        return _fake_response(500, {"error": "internal"})

    monkeypatch.setattr(client._requests, "post", fake_post)

    with pytest.raises(LLMError):
        client.complete(system="sys", user="usr")


# ---------------------------------------------------------------------------
# Test 4: 200 with malformed body ({}) → raises LLMError
# ---------------------------------------------------------------------------

def test_malformed_response_raises_llm_error(monkeypatch):
    """A 200 response with an unexpected body shape raises LLMError."""
    client = _make_client()

    def fake_post(*args, **kwargs):
        return _fake_response(200, {})

    monkeypatch.setattr(client._requests, "post", fake_post)

    with pytest.raises(LLMError):
        client.complete(system="sys", user="usr")


# ---------------------------------------------------------------------------
# Test 5: End-to-end fail-safe — triage() with a GroqClient that raises
#          ConnectionError returns a safe same-day / fallback decision
# ---------------------------------------------------------------------------

def test_triage_failsafe_with_groq_connection_error(monkeypatch):
    """
    When GroqClient.complete() raises a ConnectionError the triage pipeline
    must fall back to decided_by='fallback', priority='same-day',
    escalation_required=True.  No red-flag rule fires on this mild transcript.
    """
    import requests

    client = _make_client()

    def fake_post(*args, **kwargs):
        raise requests.exceptions.ConnectionError("no route to host")

    monkeypatch.setattr(client._requests, "post", fake_post)

    from app.common.schemas import IntakeResult
    from app.triage.service import triage

    intake = IntakeResult(
        patient_id="test-001",
        chief_complaint="mild itching",
        duration="1 week",
        symptoms=["Skin rash"],
        age=30,
        known_conditions=[],
        follow_up_answers={},
        raw_transcript="mild itching on my arm for a week",
        input_confidence="medium",
    )

    decision = triage(intake, vitals=None, client=client)

    assert decision.priority == "same-day"
    assert decision.escalation_required is True
    assert decision.decided_by == "fallback"
