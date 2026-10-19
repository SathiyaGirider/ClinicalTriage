# LifeLine build plan (Phase 0 audit)

Prototype with synthetic data only. Not a medical device, not clinically validated.

## What already exists (audit of `master-build`, commit 3b537a1)

| Area | Owner | Files | State |
|---|---|---|---|
| Shared contracts | all | `app/common/schemas.py` | `IntakeResult`, `TriageDecision`, `DoctorSummary`. Works. |
| Scenarios | all | `mock-data/scenario-01..08.json` | 8 scenarios with stage A/B/C ideal outputs. Works. |
| Intake | Person A | `app/intake/*` | Kiosk state machine (`conversation.py`), hybrid extractor (Gemini + deterministic fallback), bilingual red-flag scanner, follow-up bank (en/ta), deterministic confidence, router (`/intake`, `/intake/envelope`, `/intake/questions`, `/intake/kiosk/*`), static kiosk UI, 108 unit tests (2 failing on repeat-phrase detection). |
| Triage | Person B | `app/triage/*` | `check_red_flags()` (10 substring rules), Groq LLM classifier, escalation, `triage()` service, `POST /triage`. Script runner `tests/test_triage_runner.py` (7/8 with mock LLM). |
| Explain | Person C | `app/explain/*` | `build_doctor_summary()`, `render_dashboard()`, script test 8/8. |
| Root | - | `main.py` (empty), `requirements.txt`, `README.md` (empty) | No app wiring. |

Missing entirely: config, database, auth/roles, catalog, booking/tokens, queue, nurse/doctor dashboards, EHR, audit log, React frontend, docs.

## Decisions per module

| Module | Decision | Why |
|---|---|---|
| `app/common/schemas.py` | **Extend** | Keep every existing field and type. Add optional fields (`symptom_tags`, `safety_screen`, `language`, `addenda`, `flag_for_nurse`, `audit_notes`, `suggested_department`, ...) with defaults so old payloads and the 8 scenarios still validate. New contracts `QueueEntry`, `PatientAdvice`, `DoctorRecommendation` added. Listed in `docs/schema.md`. |
| `mock-data/` | **Keep + extend** | Scenarios untouched. Add `mock-data/expected.json` (expected priority / decided_by and the canned fake-LLM reply for LLM-path scenarios). |
| `app/intake/extractor.py` | **Extend** | Deterministic fallback, red-flag merge and verbatim transcript are kept. The Gemini call is replaced by the shared Anthropic wrapper (`app/common/llm.py`) because the spec requires the Anthropic SDK with model/key from env; when no key is set the deterministic path runs exactly as before. |
| `app/intake/redflag_scan.py`, `confidence.py`, `followup.py` | **Reuse as-is** | Used by the new adaptive session flow (fallback question bank, confidence scoring). |
| `app/intake/conversation.py` + kiosk static UI + existing `/intake*` routes | **Keep** | Still mounted. The new patient app uses a new adaptive session flow (`app/intake/session.py`, `/intake/session/*`) because the spec requires the fixed safety screen, profile-prefilled age, 4-6 question cap and assisted/re-check modes; the kiosk flow has none of these. `/intake/tts` proxy is kept but not used by the new frontend (no audio leaves the browser in the new app). |
| `app/intake/conversation.py::is_repeat_request` | **Fix** | Two pre-existing failing tests ("sorry what", "திரும்ப சொல்லுங்க"). Small regex fix, no behaviour removed. |
| `app/triage/rules.py` | **Extend** | `check_red_flags(symptoms, age)` is kept unchanged (legacy API, used by the runner). A new declarative engine `evaluate_rules()` is added in the same file: tags + transcript keywords (en/ta/transliteration) + safety screen + vitals, emergency and urgent tiers, templated rationales. Rule ids for the existing flags are kept (`chest_pain_with_breathlessness`, `stroke_signs`, `respiratory_distress`, `pediatric_seizure`, ...). |
| `app/triage/llm_classifier.py` | **Replace internals, keep function name** | Groq HTTP call replaced by `app/common/llm.py` (Anthropic SDK, timeouts, no retries, fake client for tests). `classify_with_llm()` keeps its `(priority, confidence, reason)` return shape. |
| `app/triage/escalation.py` | **Reuse** | Called from the new service. |
| `app/triage/service.py` | **Extend** | `triage()` keeps its signature and now runs sanitize -> rules -> LLM -> safety filter -> fail-safe wrapper. New `reclassify()` (raise-only). |
| `app/triage/router.py` | **Extend** | `POST /triage` kept; add `/triage/classify`, `/triage/reclassify`, `/triage/test-scenario`. |
| New triage files | **Add** | `sanitizer.py`, `safety_filter.py`, `prompts.py`, `cli.py`, `summary.py`. |
| `app/explain/` | **Reuse** | `build_doctor_summary()` is the deterministic template summary. Wrapped by `app/triage/summary.py` which adds the optional LLM rewording with traceability checks. |
| `tests/test_triage_runner.py`, `app/explain/test_explain.py` | **Keep** | Still runnable as scripts. New pytest suites live in `tests/`. |
| `main.py` (root, empty) | **Replace** | Now a one-line shim importing `app.main:app`, so `uvicorn main:app` also works. |
| `requirements.txt` | **Extend** | Add sqlmodel, anthropic, argon2-cffi, PyJWT, pytest, httpx. `google-genai` kept (still optional import in nothing; harmless) - removed from the import path, kept in file to avoid surprising teammates. |

New modules (nothing to reuse): `app/config.py`, `app/db.py`, `app/models.py`, `app/auth/`, `app/audit/`, `app/catalog/`, `app/booking/`, `app/queue/`, `app/ehr/`, `app/doctor/`, `app/patient/`, `app/pipeline/`, `app/seed.py`, `frontend/`.

## Nothing deleted
No teammate file was deleted. The only behavioural replacements are the two LLM provider calls (Groq, Gemini) which move to the Anthropic wrapper as the spec requires.
