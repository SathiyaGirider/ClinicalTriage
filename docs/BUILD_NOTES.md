# LifeLine Engineering Build Notes

This document logs significant architectural refactoring, replacements, and component evolution performed during the hardening and redesign phases.

---

## 1. UI Architecture & Design System (Phase 1 & Phase 2)

### Replacement: Ad-Hoc CSS Styles -> Design System Tokens & Shared UI Library
- **What Was Replaced:** Scattered ad-hoc class styling and native browser popups (`window.prompt`, `window.confirm`).
- **Why:** Inconsistent visual hierarchy, poor mobile accessibility, lack of semantic landmarks, and disruptive browser dialogs that could not be styled or tested.
- **New Implementation:**
  - Tokenized design system in `frontend/src/shared/theme.css` aligned with the Stitch design reference (`projects/746745182743364092`).
  - Strict clinical palette: Neutral slate surfaces (`#f8fafc`, `#ffffff`), primary clinical teal/blue (`#0369a1`), with red/amber/green strictly reserved for clinical urgency states and always paired with textual labels and icons.
  - Reusable component library in `frontend/src/shared/ui/`: `Button`, `Field`, `Select`, `Chip`, `Table`, `Drawer`, `Dialog`, `Tabs`, `Banner`, `Skeleton`, `EmptyState`, `Toast`.
  - Accessible modal dialogs for:
    - Cancelling appointments (`frontend/src/patient/MyAppointments.tsx`).
    - Nurse flagging and unflagging with required clinical justification (`frontend/src/nurse/EntryDrawer.tsx`).
    - Nurse priority modification and emergency transfers (`frontend/src/nurse/Dashboard.tsx`).
    - Simulated ABDM Scan & Share registration (`frontend/src/nurse/Dashboard.tsx`).

### Scannable Doctor EHR Workspace
- **What Was Refactored:** Doctor consultation page (`frontend/src/doctor/Workspace.tsx`).
- **Why:** The doctor screen previously required reading lengthy unformatted text blocks, slowing down OPD throughput.
- **New Implementation:**
  - Fast scannable 1-line headline summarizing chief complaint, duration, and red-flags.
  - Full triage summary expands on demand.
  - Two distinctly separated, non-confusing cards:
    - `"What the patient told us"` (unaltered patient transcript).
    - `"Decision support (AI-assisted). Confirm before acting."` (triage tier, rationale, red flags).
  - 1-tap staff feedback control (`Useful` / `Not useful`) with optional rationale, stored for audit and model evaluation.

---

## 2. ABDM Simulation Architecture (Phase 3B)

### Replacement: Permanent History Consent Boolean -> Dynamic Consent Requests
- **What Was Replaced:** Legacy `share_history_consent: bool` field on `Patient` model.
- **Why:** ABDM access architecture is transactional, time-bounded, purpose-specific, and revocable. A permanent binary toggle misrepresents real digital health standards.
- **New Implementation:**
  - `app/abdm_mock/gateway.py` implementing `ConsentGateway` interface and `MockGateway`.
  - Full consent lifecycle: `REQUESTED` -> `GRANTED` -> `DENIED` -> `REVOKED` -> `EXPIRED`.
  - Provider-side read enforcement: The mock HIP dynamically checks expiry on every single read attempt. If expired, status updates to `EXPIRED` and access is rejected and audit-logged.
  - Scope filtering by date range and approved Health Information Types (`OPConsultNote`, `Prescription`).
  - App-level "diagnoses only" projection for privacy minimisation.
  - Simulated ECDH key agreement (`SECP256R1`) + AES-256-GCM encryption + ECDSA signatures in `app/abdm_mock/crypto.py` demonstrating secure transport of FHIR R4 Document Bundles.

---

## 3. Safety, Triage & Fail-Safe Hardening (Phase 3)

### AI_ENABLED Toggle & Deterministic Mild Allowlist
- **What Was Added:** `settings.ai_enabled` (default `True`).
- **Why:** To permit demonstrating and testing deterministic fail-safe behavior when the LLM is completely disabled or unreachable.
- **Behavior:**
  - When disabled, safety rules run first. Unmatched inputs either resolve via deterministic allowlist (for vetted benign symptoms like uncomplicated rhinitis) or fail safe to **Same-Day (Urgent)** with nurse flags. The LLM is never called.

### Skip Automated Intake (ICMR Compliance)
- **What Was Added:** Skip questions endpoint (`/pipeline/skip-intake`) and patient UI option.
- **Why:** Conformance with ICMR principles of patient autonomy and disclosure.
- **Behavior:**
  - A patient can choose to skip automated triage questions. An intake is recorded with `pre_screened=False`, issuing a booking slot while mandating that the nurse check-in desk conduct an in-person evaluation upon arrival.

---

*LifeLine build and refactoring log.*
