# Proposed ownership of the finished app (no overlapping files)

| Person | Owns (folders/files) | Public interfaces they must not break |
|---|---|---|
| **A: patient app, intake, catalog/booking** | `frontend/src/patient/`, `frontend/src/auth/`, `frontend/src/shared/i18n/*.json`, `app/intake/` (incl. kiosk legacy), `app/catalog/`, `app/booking/`, `app/pipeline/advice.py`, `mock-data/` stage A, `tests/test_booking.py`, `tests/test_intake_and_pipeline.py`, `frontend/e2e/` | `/intake/session/*`, `/booking/*`, `/catalog/*` request/response shapes; `IntakeResult` fields; `intake.session.build_intake_result()`; `booking.service.capacity_lock` semantics |
| **B: triage, safety, security, authz tests, red-flag docs** | `app/triage/`, `app/common/symptom_vocab.py`, `app/common/llm.py`, `app/auth/`, `app/audit/`, `app/common/logging_setup.py`, `mock-data/expected.json`, `tests/test_triage.py`, `tests/test_authz.py`, `docs/RED_FLAG_RULES.md`, `docs/security-note.md`, `docs/FAILURE_MODES.md`, `docs/ARCHITECTURE.md` | `triage()`, `reclassify()`, `evaluate_rules()`, `check_red_flags()`; `TriageDecision` fields; `python -m app.triage.cli`; `require_roles` dependencies; `log_action` / `log_view` |
| **C: nurse + doctor dashboards, queue, EHR, history policy** | `frontend/src/nurse/`, `frontend/src/doctor/`, `app/queue/`, `app/doctor/`, `app/ehr/`, `app/patient/`, `app/explain/`, `tests/test_queue.py`, `tests/test_history_policy.py`, `tests/test_e2e_smoke.py`, `docs/queue-rules.md`, `docs/ehr-integration.md` | `/queue/*`, `/doctor/*`, `/ehr/*`, `/me/*` shapes; `QueueEntry` and `DoctorSummary`; `order_queue()`; `EhrAdapter` interface; `history_policy` functions |

## Shared files: give the team a heads-up before editing
`app/common/schemas.py`, `app/models.py`, `app/main.py`, `app/config.py`, `app/db.py`, `app/seed.py`, `app/pipeline/service.py` + `store.py`, `requirements.txt`, `frontend/package.json`, `frontend/src/shared/*.tsx|ts` (api, auth, layout, ui, voice), `frontend/src/App.tsx`, `frontend/src/styles.css`, `tests/conftest.py`, `tests/helpers.py`, `.env.example`, `docs/schema.md`, `docs/ASSUMPTIONS.md`.

Rule of thumb: contract changes are additive (optional fields with defaults) and listed in `docs/schema.md`.
