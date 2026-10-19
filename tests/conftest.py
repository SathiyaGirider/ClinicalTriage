"""
Shared fixtures. Every test gets a fresh SQLite file, seeded synthetic data,
a frozen clock (Monday 2026-10-19 10:00 clinic time) and a FAKE LLM client.
No API key is needed or used.
"""

import json
import os
from datetime import datetime

os.environ.setdefault("SEED_PASSWORD", "test-password-123")
os.environ["SEED_DEMO"] = "false"
os.environ.pop("GROQ_API_KEY", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session  # noqa: E402

from app.auth.security import rate_limiter  # noqa: E402
from app.common import timeutil  # noqa: E402
from app.common.llm import FakeLLMClient, set_llm_client  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import get_engine, init_db, set_engine_url  # noqa: E402

PASSWORD = "test-password-123"
FROZEN = datetime(2026, 10, 19, 10, 0, 0)

ROUTINE = json.dumps({"priority": "routine", "confidence": "high", "rationale": "Mild and stable; can wait for the booked session."})
SAME_DAY = json.dumps({"priority": "same-day", "confidence": "medium", "rationale": "Should be seen today."})


def default_llm(system, user, purpose):
    if purpose == "triage":
        return ROUTINE
    return None  # questions -> fixed bank, extraction -> deterministic, summary -> template


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    settings.seed_password = PASSWORD
    settings.seed_demo = False
    timeutil.set_now(FROZEN)
    set_engine_url(f"sqlite:///{tmp_path / 'test.db'}")
    init_db()
    rate_limiter.reset()
    fake = FakeLLMClient(default_llm)
    set_llm_client(fake)
    yield fake
    set_llm_client(None)
    timeutil.set_now(None)


@pytest.fixture
def fake_llm(_env):
    return _env


@pytest.fixture
def seeded(_env):
    from app.seed import seed
    with Session(get_engine()) as db:
        return seed(db)


@pytest.fixture
def db(seeded):
    with Session(get_engine()) as s:
        yield s


@pytest.fixture
def client(seeded):
    from app.main import app
    with TestClient(app) as c:
        yield c


def login(client, email, password=PASSWORD):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def H(client):
    cache = {}

    def _h(who: str):
        email = who if "@" in who else f"{who}@example.com"
        if email not in cache:
            cache[email] = login(client, email)
        return cache[email]
    return _h
