# Architecture note: where the rules end and the LLM begins

LifeLine is a course-project prototype with synthetic data. It is not clinically validated and not a medical product.

## Pipeline (`app/triage/service.py`)

```
patient text ──► sanitize + injection check ──► RULES ──fired?──yes──► decision (decided_by="rule")
                  (app/triage/sanitizer.py)     (rules.py)      │
                                                                no
                                                                ▼
                                    LLM urgency estimate on a structured subset (llm_classifier.py)
                                                                ▼
                                    output filter (safety_filter.py) ──► fail-safe wrapper ──► decision
```

| Step | Deterministic? | What it may do | What it may never do |
|---|---|---|---|
| Sanitizer / injection check | yes | flag `injection_suspected`, which raises to at least same-day | lower anything; rules always run on the ORIGINAL text |
| Rule layer (`evaluate_rules`) | yes (no LLM, no randomness) | decide emergency (tier 1) or same-day + flag (tier 2) using tags, transcript keywords (EN / Tamil script / transliteration), safety-screen chips, vitals | be overridden by the LLM |
| LLM (only when no rule fired) | no | return `priority`, `confidence`, 1–2 sentence rationale as JSON | see the raw transcript, names or emails (it gets tags, duration, age, known conditions, follow-up answers, a short chief complaint inside a `<patient_data>` block declared to be data) |
| Output filter | yes | replace diagnosis/medication language with a safe template, note `output_filtered` | let a condition name, drug name or dosage through |
| Fail-safe wrapper | yes | on timeout, error, malformed JSON, low confidence, low input confidence, or any exception: same-day, `escalation_required`, `flag_for_nurse`, note `llm_fallback_used` / `internal_error` | return routine on any error path, or a 500 |

Invariants enforced after every decision (`_enforce_invariants`): escalation ⇒ at least same-day; non-routine ⇒ flagged for the nurse; emergency ⇒ escalation.

## Other places an LLM is used (all optional)

| Use | Fallback when the LLM is missing or misbehaves |
|---|---|
| Adaptive intake question text (`app/intake/session.py`) | Person A's fixed bilingual question bank. The safety screen, duration, age and conditions questions are fixed and never LLM-chosen. Questions are filtered for diagnosis/drug language. |
| Intake field extraction (`app/intake/extractor.py`) | Person A's deterministic regex/lexicon extractor; red-flag scan always runs on the raw words. |
| Doctor summary rewording (`app/triage/summary.py`, Tamil intakes only) | Template summary. Any invented history item ⇒ template. Red flags and rationale are never LLM-written. |

## What AI never does

- Diagnose, suggest medication/dose/treatment, or fill any part of the consultation form (the form has no AI hooks).
- Change queue order or order mode (`app/queue/ordering.py` takes mode/positions only from nurse actions). AI flags only populate "Needs attention".
- Show anything to a patient except fixed, localised, non-diagnostic advice (`app/pipeline/advice.py`).

## Modules

`auth` (argon2, JWT 2 h, rate limit) · `catalog` · `booking` (holds, tokens, outcomes) · `intake` (adaptive sessions + Person A's extractor) · `triage` · `pipeline` (intake → triage → summary → advice) · `queue` (presence, ordering, nurse actions, vitals, alerts) · `ehr` (adapter, local SQLite, FHIR mapper, external stub, history policy) · `doctor` · `patient` · `audit`. SQLite via SQLModel. React + TypeScript PWA in `frontend/`.
