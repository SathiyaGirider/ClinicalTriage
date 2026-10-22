# Failure Mode & Effects Analysis (FMEA)

This document analyzes critical failure modes in LifeLine, their system-level consequences, automatic mitigation guardrails, and human escalation procedures.

---

## 1. When the AI is Wrong in Each Direction

### Case A: AI Under-Triages (False Negative / Low-Urgency Estimate on Critical Patient)
- **Failure Description:** The LLM receives symptoms that represent an emergent condition, but the model erroneously estimates `routine` or suggests the patient wait for a later appointment.
- **System Safeguard (Deterministic Rules):**
  - The LLM does **not** evaluate red flags alone. Hardcoded rules in `app/triage/rules.py` execute on the verbatim transcript *before* any model invocation.
  - If any recognized danger pattern is detected (e.g. chest pain with breathlessness, stroke weakness, severe bleeding, unresponsive state), the tier is set to **Emergency** deterministically. The LLM is never called and cannot downgrade the case.
  - If a rule assigns `urgent` (same-day), and the LLM returns `routine`, the triage comparator enforces `max(rule_priority, llm_priority)` using `PRIORITY_RANK`. The downgrade attempt is rejected and logged as `llm_downgrade_prevented`.
- **Secondary Safeguard (In-Person Nurse Check-In):**
  - Even if a non-flagged condition passes to the clinic, all arriving patients must be checked in by the triage nurse. The nurse performs the 4-outcome check-in ("Better", "No change", "Worse", "New symptom") and can record vitals. Abnormal vitals or a worsening condition automatically raise the priority.

### Case B: AI Over-Triages (False Positive / Excessive Urgency on Benign Condition)
- **Failure Description:** The LLM flags a benign, routine symptom (e.g. mild cold or localized muscle twitch) as `same-day` or `emergency`, causing patient anxiety or OPD queue congestion.
- **System Safeguard (Mild Allowlist & Human Override):**
  - For common mild presentations without red flags (e.g. isolated rhinitis, mild sneezing, short-duration localized symptoms), deterministic allowlists provide a baseline calibration.
  - Staff screens prominently label AI outputs as:
    `"Decision support. AI-assisted. Confirm before acting."`
  - The assigned nurse can lower or modify an over-escalated priority via the "Change Priority" dialog, provided they enter a mandatory clinical rationale. The override is timestamped and audit-logged with the nurse's credentials.

---

## 2. When the LLM is Down, Unresponsive, or Times Out

- **Failure Description:** The external LLM API (e.g., Groq or provider gateway) suffers network failure, rate limiting (HTTP 429), connection timeout, or returns malformed JSON.
- **System Safeguard (Safe Fallback to Caution):**
  - Catch blocks in `app/triage/service.py` intercept `LLMTimeout`, `RateLimitError`, and `JSONDecodeError`.
  - The pipeline logs `ai_unavailable_escalated` or `llm_fallback_used` in the audit notes.
  - If deterministic mild allowlist conditions are met, the system can assign `routine`. Otherwise, the system automatically escalates the patient to **Same-Day (Urgent)** with `flag_for_nurse=True`.
  - The nurse and doctor workspaces display a clear banner:
    `"AI estimate unavailable or unsure: fail-safe used. Please evaluate manually."`
  - An environment switch `AI_ENABLED=false` is provided to demonstrate pure deterministic fallback operation.

---

## 3. When a Nurse Does Not Acknowledge an Alert

- **Failure Description:** A patient with flagged symptoms arrives, is placed in the "Needs Attention" queue, but the busy nurse fails to click "Acknowledge" or review the drawer.
- **System Safeguard (Persistent Visual & Operational Escalation):**
  - The patient entry is styled with high-contrast alert styling (`alert-red` or `alert-amber`) and a prominent danger flag icon.
  - The "Needs Attention" section remains permanently pinned to the top of the nurse dashboard, above the standard queue.
  - In the doctor workspace, flagged patients display an immediate visual warning headline (`"Red flags: ..."`), alerting the physician directly when the patient enters the consultation room regardless of nurse acknowledgment state.
  - The unacknowledged status remains recorded in the database, allowing supervisory audits to review delayed attention logs.

---

## 4. Race Condition: Two Patients Try to Book the Last Token

- **Failure Description:** Two patients view the same doctor session simultaneously when only 1 open token remains. Both attempt to complete intake and book at the exact same instant.
- **System Safeguard (Two-Phase Capacity Hold & Database Transactions):**
  - **10-Minute Ephemeral Hold:** When a patient initiates an appointment flow, the booking engine allocates a temporary 10-minute hold (`hold_token`) in the database. Tokens are deducted from available capacity immediately upon hold creation.
  - **Single Token Allocation:** A second user attempting to book while the hold is active sees the session as "Full (0 tokens left)".
  - **Hold Expiry:** If the first user abandons the wizard or fails to complete intake within 10 minutes, the hold expires automatically. Capacity is restored to the pool for other patients without orphaned reservations.
  - **Atomic Finalisation:** At booking confirmation, an atomic SQL transaction validates that the session has not exceeded `max_capacity`. If simultaneous requests bypass holds, the second commit fails with an HTTP 409 Conflict error (`"Session capacity reached"`). The token is never duplicated or oversold.

---

*LifeLine clinical failure modes and risk analysis.*
