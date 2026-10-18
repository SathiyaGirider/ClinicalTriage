# API reference

Interactive docs: `http://localhost:8000/docs`. Machine-readable: `docs/openapi.json` (regenerate: `python -c "import json;from app.main import app;json.dump(app.openapi(),open('docs/openapi.json','w'),indent=1)"`).

Roles: P = patient, N = nurse, D = doctor, any = any logged-in user. Every route also does object-level checks (own data / own hospital / appointment relationship).

| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | /auth/register | public | patient self-registration (no phone/ID fields accepted) |
| POST | /auth/login | public | email + password → JWT (rate-limited) |
| GET | /auth/me | any | current account |
| GET | /catalog/hospitals, /catalog/specialties, /catalog/doctors, /catalog/doctors/{id}/sessions, /catalog/department | any | catalog, distance/area sort, deterministic department |
| POST | /booking/hold · /booking/{hold_id}/release | P | hold one capacity unit for 10 min / release |
| POST | /booking/finalize | P | `{hold_id, intake_id}` (routine) or `{mode:"same_day", session_id, intake_id}`; outcome decided by the server's stored triage |
| GET | /booking/mine · /booking/{id}/status · /booking/{id}/ics | P | appointments, live status (now serving, estimate), calendar file |
| POST | /booking/{id}/cancel · /booking/{id}/reschedule · /booking/{id}/arrived | P | cancel, reschedule (intake reused), "I'm here" + change |
| GET/POST | /booking/today-sessions · /booking/walk-in-intent | P | concerning outcome: today's sessions / "I will come today" |
| POST/GET | /intake/session/start · /{id}/answer · /{id} · /{id}/result | P (N for assisted/re-check) | adaptive 4–6 question flow, confirm screen |
| POST | /pipeline/submit | P, N | intake → triage → summary → PatientAdvice (fail safe); re-check sessions merge an addendum |
| POST | /triage · /triage/classify · /triage/reclassify · /triage/test-scenario | N, D | staff-only triage tools (patients never see priority) |
| GET | /queue · /queue/search · /queue/entry/{id} · /queue/expected-today · /queue/action-log · /queue/doctors | N | dashboard data, check-in desk, drawer, logs |
| POST | /queue/{id}/check-in · /queue/{id}/recheck/start · /queue/{id}/ack | N | nurse check-in (none/better/worse/new_symptom), short re-check, acknowledge |
| POST | /queue/walk-in · /queue/assisted-intake/start | N | register walk-in + W token, assisted intake |
| POST | /queue/action · /queue/order · /queue/flag · /queue/vitals | N | nurse actions, order mode, flags (reason required), vitals (raise-only) |
| GET/POST | /doctor/today · /doctor/start/{entry_id} · /doctor/patient/{id} · /doctor/override · /doctor/patients | D | today list (read-only order), call in, workspace + policy-filtered history, priority override (reason), search own patients |
| POST | /ehr/consultation | D | diagnosis, notes, prescription, follow-up → EHR adapter; completes the visit |
| GET | /ehr/fhir/Patient/{id} · /ehr/fhir/Encounter?patient= · /ehr/fhir/MedicationRequest?patient= | D | FHIR-style demo (policy-filtered, audit-logged) |
| GET/PUT | /me/records · /me/prescriptions · /me/consent · /me/access-log · /me/profile | P | own records, consent, who viewed, profile |
| GET | /health · /config/public | public | status, emergency numbers, banners |
