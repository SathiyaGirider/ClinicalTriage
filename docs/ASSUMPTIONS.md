# Assumptions and decisions

Each entry: decision, and why. Added as the build progressed.

## Contracts
1. **`IntakeResult.symptoms` stays free text.** The 8 scenarios and Person A's extractor put descriptive strings there. Canonical tags from `app/common/symptom_vocab.py` go into a new field `symptom_tags` (unknown -> `other`). Rules match on either.
2. **`TriageDecision.decided_by`** keeps `rule | llm | rule+llm` and adds `fallback` (LLM not usable: no key, timeout, error, malformed) and `human` (nurse/doctor override). Scenario 5 (LLM answered with low confidence) stays `llm`.
3. **`patient_id` stays a string** in the contracts (`str(user.id)`), as Person A required.
4. QueueEntry, PatientAdvice, DoctorRecommendation did not exist in `schemas.py`; they were added there.

## Safety
5. **Injection suspected => at least same-day.** The spec says detection sets `escalation_required=true`; rule 4 says escalation always means at least same-day + flag. So detection raises to same-day. Rules still run on the original text.
6. **Escalation always means `same-day` or higher and `flag_for_nurse=true`.** A routine decision therefore never carries `escalation_required=true`.
7. **Any positive safety-screen chip** is at least the urgent tier (same-day, flagged). Specific chips map to emergency rules (trouble breathing, severe bleeding, sudden weakness/numbness, seizure).
8. **Negation in transcripts** ("no chest pain", "not feverish") is honoured only for English words immediately preceded (within 3 words) by `no / not / without / denies / never`. Tamil post-position negation is NOT parsed, so Tamil red-flag words always fire. Errs toward caution. Needs clinician + linguist review.
9. **Intake ends early on an emergency rule.** If Q1 text already fires an emergency rule, the remaining questions (including the safety screen) are skipped so the patient gets the emergency screen immediately.
10. **Patient-reported "Worse/New symptom"** (I'm here button) always flags the entry (`flag_source=ai`, meaning "system", reason "patient reported change"), in addition to the raise-only re-triage of the text.
11. **Nurse check-in with Worse/New symptom** flags the entry (`flag_source=nurse`) and, if the nurse typed a note, re-runs triage on it as an addendum (raise only). The response tells the UI to offer the short re-check.

## Booking
12. **The server, not the client, decides the outcome at finalise.** `/booking/finalize` takes `hold_id` + `intake_id`; the server reads the stored TriageDecision. A client cannot claim "routine".
13. **Capacity = active units**: unexpired holds + appointments that are not cancelled. Cancelling frees capacity but the token number is never reused (the per-session sequence only increases), so the last token number may exceed `max_tokens`.
14. Routine bookings may use `max_tokens - reserved_urgent`; concerning (same-day) bookings may use all `max_tokens`.
15. **Concurrency** is enforced with a process-wide lock around capacity check + insert, plus SQLite's single writer. The prototype runs as ONE uvicorn worker; multi-worker deployment would need `BEGIN IMMEDIATE`/Postgres row locks.
16. Walk-in intent with no doctor picked uses the first doctor of the suggested specialty at that hospital.
17. Walk-in (W) tokens are numbered per doctor per day and issued at nurse check-in.
18. Times are naive local clinic time (`CLINIC_TZ`, default Asia/Kolkata). `app/common/timeutil.py` allows tests to freeze "now".

## Queue
19. Order mode is stored per doctor + date + session label. Walk-ins get the session label current at check-in.
20. Late arrivals (called_absent, or token already passed) and walk-ins are ordered after on-time booked patients by check-in time (after_booked). Under `interleave`, one walk-in after every three booked; late arrivals still go to the tail.
21. When an entry is marked with_doctor, every booked_not_arrived entry in that session with a lower token becomes called_absent.
22. Fast-tracked entries go right after the patient with the doctor, in fast-track time order, in both modes.

## Data and infra
23. Walk-in patients registered by a nurse get a placeholder account (`walkin-<id>@walkin.invalid`) with an unusable password. No phone/ID collected.
24. Intake sessions are stored in SQLite (JSON state) so a server restart does not lose answers.
25. Without `ANTHROPIC_API_KEY` or `LLM_MODEL` the LLM client is "unavailable": adaptive questions fall back to the fixed bank, extraction is deterministic, triage fails safe (same-day + escalation + flag) for cases no rule decides. The CLI and tests use a fake client with canned replies from `mock-data/expected.json`.
26. Uvicorn access logs have query strings stripped (doctor patient search uses `?query=`).
