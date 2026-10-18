"""Password hashing (argon2), JWT tokens, and in-memory login rate limiting."""

import threading
import time
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import settings

_hasher = PasswordHasher()
UNUSABLE_PASSWORD = "!unusable"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    if password_hash == UNUSABLE_PASSWORD:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_token(user_id: int, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiry_minutes)
    return jwt.encode({"sub": str(user_id), "role": role, "exp": exp}, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


class LoginRateLimiter:
    """5 failures per (email, ip) => locked for 60 seconds."""

    def __init__(self, max_failures: int = 5, lockout_seconds: int = 60):
        self.max_failures = max_failures
        self.lockout_seconds = lockout_seconds
        self._state: dict[tuple[str, str], tuple[int, float]] = {}
        self._lock = threading.Lock()

    def locked_for(self, email: str, ip: str) -> float:
        with self._lock:
            failures, until = self._state.get((email.lower(), ip), (0, 0.0))
            remaining = until - time.monotonic()
            return remaining if remaining > 0 else 0.0

    def fail(self, email: str, ip: str) -> None:
        key = (email.lower(), ip)
        with self._lock:
            failures, until = self._state.get(key, (0, 0.0))
            if until and until <= time.monotonic():
                failures = 0
            failures += 1
            until = time.monotonic() + self.lockout_seconds if failures >= self.max_failures else 0.0
            self._state[key] = (failures, until)

    def success(self, email: str, ip: str) -> None:
        with self._lock:
            self._state.pop((email.lower(), ip), None)

    def reset(self) -> None:
        with self._lock:
            self._state.clear()


rate_limiter = LoginRateLimiter()
