# LifeLine — Hospital OPD Patient Intake, Nurse Triage & Doctor EHR Platform

> **DEMO & COURSE PROJECT (LOCAL RUN)**
> - **Synthetic Data Only:** Never enter real patient credentials, phone numbers, or health information.
> - **Clinical Decision Support:** AI assists the care team. It does **not** diagnose or prescribe. A nurse or doctor makes every decision.
> - **Zero Regulatory Claims:** Not clinically validated. Not certified by CDSCO or ABDM. Prototype only.

---

## Overview

LifeLine is a full-stack hospital outpatient department (OPD) web application designed for local operation on Windows, macOS, or Linux. It connects three primary user roles into an integrated, safe, and audited clinical workflow:

1. **Patient Web App:** Multi-step accessible intake wizard (English & Tamil), symptom-first routing, capacity-capped session booking with 10-minute holds, non-reusable tokens, live queue status ("Now serving"), appointment reschedule/cancellation, and an ABDM-style Privacy & Consent inbox.
2. **Nurse Triage Dashboard:** Dense clinical table strictly scoped 1-to-1 to the assigned physician, pinned "Needs Attention" alert panel, 4-outcome check-in desk ("No change", "Better", "Worse", "New symptom"), objective vitals recording (SpO2, BP, pulse, temp), fast-track/queue reordering, and simulated ABDM Scan & Share express check-in.
3. **Doctor Consultation Workspace:** Scannable 1-line headline, expandable triage summary strictly separating *"What the patient told us"* from *"Decision support (AI-assisted)"*, 1-tap staff feedback control, physician-authored EHR diagnosis and prescription forms, and ABDM consent-governed outside history retrieval.

---

## Safety Invariants (Strictly Enforced)

1. **AI Never Diagnoses or Prescribes:** Diagnosis and prescription fields are strictly blank text inputs authored and signed by the licensed physician. Accidental drug or diagnostic strings in model output are filtered server-side.
2. **Deterministic Rules Are Authoritative:** Hardcoded red-flag rules evaluate original patient text before any LLM invocation. The LLM can maintain or raise clinical urgency, but can **never** lower it below a rule threshold.
3. **Fail-Safes Escalate Toward Caution:** Model timeouts, rate limits, malformed JSON, low confidence, or low input confidence escalate to **Same-Day (Urgent)** with nurse flags.
4. **Patient Text Is Untrusted Data:** Prompt injection attacks in English, Tamil, transliteration, or encoded formats cannot change triage rules or lower priorities.
5. **AI Never Changes Queue Order:** Only the assigned nurse can reorder or fast-track patients in the queue.
6. **1:1 Nurse-Doctor Scoping:** Nurses are bound server-side to exactly one doctor. Unassigned nurses receive an HTTP 403 / descriptive empty state.
7. **Complete Auditability:** Every override, flag change, acknowledgement, reorder, emergency transfer, and consent access is recorded with actor ID, timestamp, and clinical justification.
8. **Role-Based Record Isolation:** Nurses never see past diagnosis history or prescriptions. Outside doctors can only view past encounters through active, approved, unexpired, unrevoked ABDM consent requests scoped to specific record types.
9. **Capacity & Token Integrity:** Tokens are numbered sequentially per session and never reused upon cancellation. Holds expire after 10 minutes, preventing orphaned capacity.
10. **ABDM Features Are a Simulation:** Simulated Consent Manager, mock HIP/HIU provider enforcement, ECDH + AES-GCM encrypted bundles, and Scan & Share. Never connect to live ABDM or use real ABHA/Aadhaar IDs.

---

## Setup & Running on Windows (PowerShell)

### Prerequisites
- Python 3.11+
- Node.js 18+
- PowerShell or Windows Command Prompt

### 1. Backend Setup
```powershell
# In the project root:
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies:
pip install -r requirements.txt

# Configure environment:
Copy-Item .env.example .env

# Reset database and populate realistic synthetic data:
python -m app.seed --reset

# Start FastAPI server (runs on http://localhost:8000):
uvicorn app.main:app --reload --port 8000
```
*Interactive Swagger UI documentation is available at `http://localhost:8000/docs`.*

### 2. Frontend Setup
```powershell
# In a second terminal window:
cd frontend
npm install

# Start Vite dev server (runs on http://localhost:5173, proxies API to 8000):
npm run dev
```

---

## Configuration Flags (.env)

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `AI_ENABLED` | `true` | When `true`, calls LLM for non-rule cases. When `false`, executes pure deterministic safety rules and mild fallbacks. |
| `DEMO_LLM_STANDIN` | `false` | When `true` and no `GROQ_API_KEY` is provided, uses a labelled deterministic keyword standin to demonstrate the routine outcome. |
| `ABDM_MODE` | `mock` | Selects `MockGateway` in `app/abdm_mock/gateway.py` with provider-side read enforcement. |
| `SEED_DEMO` | `true` | Allows running `python -m app.seed` to generate synthetic doctors, nurses, sessions, and patients. |
| `SEED_PASSWORD` | `Password123!` | Default password for all seeded demo accounts. |

---

## Presentation Walkthrough & Demo Guide
👉 **See [WALKTHROUGH.md](file:///d:/projects/ClinicalTriage/WALKTHROUGH.md) for the 5-minute professor demo script and Q&A prep.**

---

## Seeded Demo Accounts (Password: `Password123!`)

| Role | Email | Details / Scoping |
| :--- | :--- | :--- |
| **Patient 1** | `asha@example.com` | English profile, synthetic ABHA: `asha@abdm`, prior encounters |
| **Patient 2** | `ravi@example.com` | Tamil profile, synthetic ABHA: `ravi@abdm`, prior encounters |
| **Patient 3** | `priya@example.com` | General patient, synthetic ABHA: `priya@abdm` |
| **Nurse (Adyar)** | `nurse.adyar@example.com` | Scoped to Dr. Meena Raghavan (General Medicine, Room 101) |
| **Nurse (Cardio)** | `nurse.cardio.adyar@example.com` | Scoped to Dr. Arjun Rao (Cardiology, Room 102) |
| **Nurse (Derm)** | `nurse.derm.adyar@example.com` | Scoped to Dr. Karthik Iyer (Dermatology, Room 103) |
| **Nurse (Unassigned)**| `nurse.unassigned@example.com` | Tests unassigned guardrails (HTTP 403 / empty state) |
| **Doctor (Treating)** | `dr.gm.adyar@example.com` | Dr. Meena Raghavan, General Medicine, LifeLine Adyar |
| **Doctor (Outside)** | `dr.derm.adyar@example.com` | Dr. Karthik Iyer, Dermatology (tests ABDM consent access) |

---

## Verification & Test Commands

```powershell
# Run backend tests (triage, ABDM, crypto, booking concurrency, queue, authz, IDOR):
pytest

# Run the 8 scripted CLI scenarios against mock-data/expected.json:
python -m app.triage.cli

# Run frontend tests (Vitest + Testing Library + i18n key consistency):
cd frontend
npm test
```

---

## Documentation Index

- `docs/ARCHITECTURE.md`: Pipeline architecture, component flow, and exact rule-LLM boundaries.
- `docs/FAILURE_MODES.md`: Analysis of AI errors, LLM downtime, unacknowledged alerts, and booking concurrency.
- `docs/RED_FLAG_RULES.md`: Catalogue of emergency and urgent rules with clinician review notices.
- `docs/DEMO_SCRIPT.md`: Rehearsed 8–10 minute script covering patient, nurse, doctor, and ABDM flows.
- `docs/ABDM_ALIGNMENT.md`: Concept mapping to official ABDM standards, simulation boundaries, and go-live requirements.
- `docs/REGULATORY_NOTES.md`: CDS classification, CDSCO medical device considerations, ICMR ethical principles, and DPDP Act notes.
- `docs/LIMITATIONS.md`: Boundaries and limitations (no clinical trials, no live government connection, no real EHR).
- `docs/BUILD_NOTES.md`: Engineering rationale for UI component replacement and ABDM consent architecture.
- `docs/ASSUMPTIONS.md`: Full log of technical assumptions and invariant design decisions.

---

*LifeLine course project repository. Synthetic data only.*
