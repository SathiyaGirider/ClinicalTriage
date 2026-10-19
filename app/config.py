"""
Central configuration. Every value comes from the environment (.env is loaded
if present). Nothing secret or model-specific is hardcoded here.
"""

import os
import secrets
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./lifeline.db"))
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET") or secrets.token_urlsafe(48))
    jwt_expiry_minutes: int = field(default_factory=lambda: _int("JWT_EXPIRY_MINUTES", 120))
    frontend_origin: str = field(default_factory=lambda: os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"))

    # LLM (no default model on purpose: the model name must come from env)
    groq_api_key: str | None = field(default_factory=lambda: os.getenv("GROQ_API_KEY") or None)
    groq_api_url: str = field(default_factory=lambda: os.getenv("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions"))
    llm_model: str | None = field(default_factory=lambda: os.getenv("LLM_MODEL") or None)
    llm_timeout_seconds: float = field(default_factory=lambda: float(os.getenv("LLM_TIMEOUT_SECONDS", "8")))

    # Clinic and sessions
    clinic_tz: str = field(default_factory=lambda: os.getenv("CLINIC_TZ", "Asia/Kolkata"))
    demo_city: str = field(default_factory=lambda: os.getenv("DEMO_CITY", "Chennai"))
    morning_window: str = field(default_factory=lambda: os.getenv("MORNING_WINDOW", "09:00-12:00"))
    afternoon_window: str = field(default_factory=lambda: os.getenv("AFTERNOON_WINDOW", "14:00-17:00"))
    reserved_urgent: int = field(default_factory=lambda: _int("RESERVED_URGENT", 2))
    hold_minutes: int = field(default_factory=lambda: _int("HOLD_MINUTES", 10))
    walkin_policy: str = field(default_factory=lambda: os.getenv("WALKIN_POLICY", "after_booked"))

    # Alerts
    alert_amber_seconds: int = field(default_factory=lambda: _int("ALERT_AMBER_SECONDS", 180))
    alert_red_seconds: int = field(default_factory=lambda: _int("ALERT_RED_SECONDS", 300))

    emergency_numbers: list[str] = field(
        default_factory=lambda: [n.strip() for n in os.getenv("EMERGENCY_NUMBERS", "112,108").split(",") if n.strip()]
    )

    ehr_backend: str = field(default_factory=lambda: os.getenv("EHR_BACKEND", "local"))
    seed_demo: bool = field(default_factory=lambda: _bool("SEED_DEMO", False))
    seed_password: str | None = field(default_factory=lambda: os.getenv("SEED_PASSWORD") or None)
    dev_endpoints: bool = field(default_factory=lambda: _bool("DEV_ENDPOINTS", True))

    @property
    def llm_configured(self) -> bool:
        return bool(self.groq_api_key and self.llm_model)


settings = Settings()
