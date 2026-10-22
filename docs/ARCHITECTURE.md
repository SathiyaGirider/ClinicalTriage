# LifeLine System Architecture & Data Flow

This document details the architectural flow, component boundaries, and security barriers of LifeLine.

---

## 1. End-to-End Pipeline Data Flow

The diagram below illustrates the exact path of clinical data from initial patient input through safety guardrails, decision support, queue management, and clinician workflows.

```mermaid
flowchart TD
    subgraph PatientLayer ["1. Patient Layer"]
        A["Patient App (Web / Mobile)"] --> B{"Skip Automated Questions?"}
        B -- "Yes (Skip)" --> C["Mark: Not Pre-Screened<br/>(Flagged for Nurse Check-in)"]
        B -- "No" --> D["Voice / Text Input<br/>(English or Tamil)"]
    end

    subgraph IntakeLayer ["2. Intake & Extraction"]
        D --> E["Original Verbatim Transcript"]
        E --> F["Sanitizer & Instruction Detector<br/>(15,000 char cap)"]
        F --> G["Deterministic Signal Extractor<br/>(Normalise vocab, safety screen chips)"]
    end

    subgraph SafetyRules ["3. Deterministic Safety Rules (Pre-LLM)"]
        G --> H{"Hardcoded Red-Flag Scan<br/>(rules.py - ESI 3-Tier)"}
        H -- "Rule Matched (Emergency / Urgent)" --> I["Authoritative Tier Assigned<br/>(Rule rationale locked)"]
        H -- "No Rule Matched" --> J{"AI_ENABLED == True?"}
        J -- "False" --> K["Deterministic Mild Allowlist / Fallback"]
        J -- "True" --> L["LLM Estimation Step"]
    end

    subgraph LLMEnsemble ["4. LLM & Output Guardrails"]
        L --> M["LLM Client (Groq / Standin)<br/>(Extracts priority & non-diagnostic rationale)"]
        M --> N["Sanitizing Filter<br/>(Removes any accidental diagnosis or prescription)"]
        N --> O{"LLM Output Priority vs Rule"}
        O -- "LLM tries to lower priority" --> P["Escalation Toward Caution:<br/>Rule / Caution Holds"]
        O -- "LLM keeps or raises" --> Q["Valid Clinical Urgency Assigned"]
    end

    subgraph SummaryAndQueue ["5. Summary & Queue Engine"]
        I --> R["Clinical Triage Summary<br/>(Separates 'Patient Words' from 'Decision Support')"]
        K --> R
        Q --> R
        C --> R
        R --> S["OPD Queue State Machine<br/>(Token generation, hold expiry, capacity protection)"]
    end

    subgraph StaffLayer ["6. Clinical Staff Workspaces"]
        S --> T["Nurse Dashboard<br/>(Scoped 1:1 to Assigned Doctor)"]
        T --> U{"Nurse Check-In Desk<br/>(4-outcome check-in, vitals, Scan & Share)"}
        U --> V["Patient Marked Present & Waiting"]
        V --> W["Doctor EHR Consultation Workspace"]
        W --> X["Doctor Diagnostic & Prescription Entry<br/>(Physician typed only, unsigned by AI)"]
        X --> Y["FHIR R4 Document Bundle<br/>(OPConsultNote, Prescription)"]
    end

    subgraph ConsentGateway ["7. Simulated ABDM Gateway"]
        Y --> Z["Mock HIP / HIU Gateway<br/>(Enforces consent status, date range, HI types, dynamic expiry)"]
        Z --> AA["Encrypted / Signed Bundle Transfer<br/>(ECDH + AES-256-GCM + ECDSA)"]
    end
```

---

## 2. Where Rules End and the LLM Begins

A strict architectural invariant in LifeLine is the absolute separation between deterministic safety logic and probabilistic machine learning:

1. **Pre-LLM Guardrail Boundary:**
   - The original raw transcript is immediately evaluated by deterministic substring pattern matching (`app/triage/rules.py` and `app/intake/redflag_scan.py`).
   - If an **Emergency** rule matches (e.g. chest pain with breathlessness, stroke signs, severe hemorrhage, pediatric seizure), **the LLM is never invoked**. The emergency outcome is sealed deterministically.
   - If the text contains instruction-like phrases (prompt injection attempt) or exceeds length thresholds, the pipeline flags `injection_suspected` and forces the priority to at least **Same-Day (Urgent)**, refusing to allow any prompt text to alter rules.

2. **The LLM Domain:**
   - The LLM is invoked **only** for cases where no emergency red-flag rule fired and `AI_ENABLED=True`.
   - The LLM receives structured clinical context (symptoms, duration, age, chronic conditions, and verbatim transcript marked strictly as untrusted user data).
   - The prompt instructs the LLM to categorize urgency (`routine` or `same-day`) and provide a brief observational rationale. The LLM is explicitly forbidden from suggesting diagnoses or pharmaceutical treatments.

3. **Post-LLM Safety Filter:**
   - All text returned by the LLM is passed through a clinical keyword filter (`app/triage/service.py`) that scrubs diagnostic statements (e.g. "migraine", "dengue", "viral infection") and drug names/dosages (e.g. "paracetamol", "ibuprofen", "500 mg").
   - If the LLM claims low confidence, returns invalid JSON, times out, or suggests lowering a rule-based priority, the pipeline overrides the LLM and escalates toward caution.

---

## 3. Server-Side Scoping and Privacy Invariants

- **1:1 Nurse-to-Doctor Scoping:** Every nurse is associated with exactly one physician in `NurseAssignment`. The queue endpoints (`/queue`, `/queue/entry/{id}`, `/queue/action`) enforce this scoping server-side. Unassigned nurses receive a descriptive empty state and zero patient data.
- **Role-Based Record Isolation:**
  - **Nurses** can view triage summaries, chief complaints, and vitals. Nurses **never** receive diagnosis history or prescriptions.
  - **Treating Doctors** have direct access to their own past encounters with their active patients.
  - **External Doctors** cannot see outside encounter history without an active, approved, unexpired, and unrevoked ABDM consent request matching the date range and record type.
- **Auditability:** Every flag change, queue reorder, priority alteration, emergency transfer, and record access is persisted in append-only tables (`AuditLog`, `NurseActionLog`, `ConsentStatusHistory`).
