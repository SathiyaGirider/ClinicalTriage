# LifeLine (course-project prototype)

> **Demo with synthetic data. Do not enter real health information.**
> **AI assists the care team. It does not diagnose or prescribe. A nurse or doctor decides.**
> Not clinically validated. Not a medical product.

LifeLine is a hospital web app with three areas. **Patients** book a session token (or start from symptoms). **Nurses** run the day's queue and flagged patients. **Doctors** see a 5-line triage summary and write the diagnosis and prescription into an EHR-style record. Fixed red-flag rules plus an optional LLM estimate urgency. The AI only flags and explains. It never diagnoses, prescribes or reorders the queue, and every override is logged.

Built on the team's earlier work: intake (Person A), triage (Person B), explain (Person C), and the 8 scenarios in `mock-data/`. See `docs/BUILD_PLAN.md`.

## Run it

Needs Python 3.11+ and Node 18+.

```bash
# backend
pip install -r requirements.txt
cp .env.example .env              # set SEED_PASSWORD; optionally GROQ_API_KEY + LLM_MODEL, or DEMO_LLM_STANDIN=true
SEED_DEMO=true python -m app.seed  # synthetic hospitals, doctors, sessions, accounts (use --reset to start over)
uvicorn app.main:app --reload --port 8000      # API docs: http://localhost:8000/docs

# frontend (dev, proxies the API)
cd frontend && npm install && npm run dev      # http://localhost:5173
# or a single-process demo: `npm run build`, then the backend serves frontend/dist at http://localhost:8000
```

If there is no API key the app still runs and fails safe: rules decide red flags, intake uses fixed questions, and cases no rule decides become "visit today, nurse checks you". For the demo's "routine" step, set `DEMO_LLM_STANDIN=true`. This is a labelled keyword heuristic, not AI.

### Demo logins (after seeding; password = `SEED_PASSWORD`, or printed once)
| Role | Email |
|---|---|
| Patient (consent ON, prior visits) | asha@example.com |
| Patient (Tamil, consent OFF, prior visits) | ravi@example.com |
| Patient | priya@example.com |
| Nurse, Adyar / Mylapore | nurse.adyar@example.com / nurse.mylapore@example.com |
| Doctors (Adyar) | dr.gm.adyar, dr.cardio.adyar, dr.derm.adyar, dr.paeds.adyar, dr.neuro.adyar @example.com |
| Doctor (Mylapore) | dr.gm.mylapore@example.com |

## Tests (no API key needed; fake LLM client)
```bash
python -m pytest                    # 200+ backend tests: triage, booking concurrency, queue, authz/IDOR, history policy, fail-safe, logs
python -m app.triage.cli            # 8 scripted scenarios, PASS/FAIL vs mock-data/expected.json
cd frontend && npm test             # component tests
node e2e/smoke.mjs                  # browser smoke test of the 3 journeys (running backend + `playwright` package)
```

## Docs
`docs/architecture-note.md` (where rules end and the LLM begins) · `failure-mode-analysis.md` · `red-flag-rules.md` · `security-note.md` · `ehr-integration.md` · `queue-rules.md` · `API.md` · `openapi.json` · `schema.md` · `DEMO_SCRIPT.md` · `OWNERSHIP.md` · `BUILD_PLAN.md` · `ASSUMPTIONS.md`

## Layout
```
app/  auth catalog booking intake triage pipeline queue ehr doctor patient audit common  main.py config.py models.py seed.py
frontend/src/  shared patient nurse doctor auth
mock-data/  tests/  docs/
```
