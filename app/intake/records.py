"""
In-memory Demo Records Store for Completed Intake Results.

Captures completed IntakeResult entries along with ISO-8601 timestamps
for live demo verification.

NOTE: This is an in-memory store for demonstration purposes only;
it is non-persistent and resets upon server restart.
"""

from datetime import datetime
from typing import Any
from app.common.schemas import IntakeResult


# In-memory list of records: most recent first
_COMPLETED_RECORDS: list[dict[str, Any]] = []


def save_record(intake_result: IntakeResult) -> dict[str, Any]:
    """
    Store completed IntakeResult with an ISO-8601 timestamp.
    """
    record = {
        "timestamp": datetime.now().isoformat(),
        "patient_id": intake_result.patient_id,
        "intake_result": intake_result.model_dump(),
    }
    # Prepend so list is ordered most recent first
    _COMPLETED_RECORDS.insert(0, record)
    return record


def get_records() -> list[dict[str, Any]]:
    """
    Return all captured intake records (most recent first).
    """
    return list(_COMPLETED_RECORDS)


def clear_records() -> None:
    """Clear all records (used for test setup)."""
    _COMPLETED_RECORDS.clear()
