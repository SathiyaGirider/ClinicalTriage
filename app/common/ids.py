"""Small id helpers."""

import uuid


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:16]}"


def token_label(session_label: str | None, number: int, walk_in: bool = False) -> str:
    if walk_in:
        return f"W-{number:02d}"
    letter = "M" if session_label == "morning" else "A"
    return f"{letter}-{number:02d}"
