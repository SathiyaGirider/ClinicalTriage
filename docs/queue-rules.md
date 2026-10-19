# Queue rules (`app/queue/ordering.py`, `app/queue/service.py`)

1. A queue entry is created when a booking is finalised (`presence=booked_not_arrived`). Walk-in intents get no token until the nurse checks them in (W-token, per doctor per day).
2. Only **present** patients are in the doctor's queue. The nurse is the source of truth: check-in sets `present`. A patient's "I'm here" tap sets `self_reported_arrived` and needs one nurse tap to confirm.
3. Order among present waiting patients:
   - fast-tracked patients first (right after the patient with the doctor), by fast-track time;
   - booked and same-day patients by token number;
   - walk-ins: `WALKIN_POLICY=after_booked` (default) after all booked patients by check-in time; `interleave` one walk-in after every three booked;
   - late arrivals (their token was passed while absent, i.e. `called_absent`, or token lower than the one being served) join after the patients present, by check-in time.
4. When a patient is marked "with doctor", every not-arrived booked patient with a lower token in that session becomes `called_absent` (skipped, not removed). At the end of a session the nurse marks absent patients no-show.
5. Order modes per doctor + date + session: **Token order** (default) and **My order** (nurse positions apply; patients she has not placed keep their relative order in the remaining slots). Switching back to Token order clears positions and restores the base order. Move up/down/drag only work in My order.
6. Flags (AI or nurse) never move anyone. Flagged present patients appear in "Needs attention"; flagged not-arrived in "Expected today (flagged)".
7. Unacknowledged flagged alerts: normal → amber after `ALERT_AMBER_SECONDS` (180) → red/pulsing after `ALERT_RED_SECONDS` (300).
8. Estimates are always labelled approximate: session start + active tokens ahead × consult minutes; once the doctor has started, now + patients ahead × recent average consult time (last 5), shown as a 30-minute range.
9. Every nurse action (check-in, acknowledge, send to ER, fast-track, return, move, with doctor, done, no-show, priority change, flag/unflag, vitals) is written to the action log with actor, time, original value, new value and reason. Priority change and flag/unflag require a reason.
