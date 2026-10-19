"""
Pure queue-ordering logic (no DB). See docs/queue-rules.md.

Only PRESENT entries that are waiting or fast-tracked are ordered.
1. Fast-tracked entries first (right after the patient with the doctor), in fast-track time order.
2. On-time booked / same-day entries by token number.
3. Walk-ins (W tokens): after_booked -> after all booked, by check-in time;
   interleave -> one walk-in after every three booked.
4. Late arrivals (called_absent, or token already passed) join after the
   patients present when they arrived: tail, by check-in time.
5. Nurse mode: entries with a nurse_position take that slot; entries she has
   not placed keep their relative base order in the remaining slots.
The AI never calls anything in this module with a different mode or position.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

ORDERABLE_STATUS = ("waiting", "fast_tracked")
_FAR = datetime.max


class Orderable(Protocol):
    id: int
    presence: str
    status: str
    token_number: int | None
    token_label: str | None
    check_in_ts: datetime | None
    late_arrival: bool
    fast_tracked_at: datetime | None
    nurse_position: int | None


def is_walk_in(e: Orderable) -> bool:
    return bool(e.token_label and e.token_label.startswith("W"))


def _interleave(booked: list, walkins: list, every: int = 3) -> list:
    out, wi = [], 0
    for i, b in enumerate(booked, start=1):
        out.append(b)
        if i % every == 0 and wi < len(walkins):
            out.append(walkins[wi])
            wi += 1
    return out + walkins[wi:]


def base_order(entries: list, policy: str = "after_booked") -> list:
    rest = [e for e in entries if e.presence == "present" and e.status == "waiting"]
    booked = sorted([e for e in rest if not is_walk_in(e) and not e.late_arrival], key=lambda e: (e.token_number or 0, e.id))
    walkins = sorted([e for e in rest if is_walk_in(e)], key=lambda e: (e.check_in_ts or _FAR, e.id))
    late = sorted([e for e in rest if e.late_arrival and not is_walk_in(e)], key=lambda e: (e.check_in_ts or _FAR, e.id))
    if policy == "interleave":
        return _interleave(booked, walkins) + late
    return booked + sorted(walkins + late, key=lambda e: (e.check_in_ts or _FAR, e.id))


def apply_nurse_positions(base: list) -> list:
    placed = sorted([e for e in base if e.nurse_position is not None], key=lambda e: (e.nurse_position, e.id))
    unplaced = [e for e in base if e.nurse_position is None]
    out = []
    for i in range(len(base)):
        if placed and (placed[0].nurse_position <= i or not unplaced):
            out.append(placed.pop(0))
        else:
            out.append(unplaced.pop(0))
    return out


def order_queue(entries: list, mode: str = "token", policy: str = "after_booked") -> list:
    fast = sorted([e for e in entries if e.presence == "present" and e.status == "fast_tracked"],
                  key=lambda e: (e.fast_tracked_at or _FAR, e.id))
    base = base_order(entries, policy)
    if mode == "nurse":
        base = apply_nurse_positions(base)
    return fast + base
