# Regulatory and Clinical Decision Support Notes

> **IMPORTANT NOTICE**:
> This document contains plain architectural and operational notes regarding software design, data handling, and regulatory considerations in India. **This document does NOT constitute legal advice or formal regulatory clearance conclusions.** LifeLine is an academic prototype and local course demonstration using synthetic data. It has not undergone clinical trials, medical device certification, or regulatory auditing.

---

## 1. Classification: Decision Support System (SaMD Considerations)

1. **Intended Purpose & Framing:**
   - LifeLine's symptom extraction, red-flag screening, urgency tiering, and summary generation are strictly designed and labelled as **Clinical Decision Support (CDS)** tools.
   - The software does **not** diagnose conditions, does **not** prescribe pharmaceuticals, and does **not** automate clinical decisions.
   - Diagnosis and prescription fields in the doctor consultation workspace are strictly blank text inputs that can only be authored and signed by the licensed treating physician.
   - Priority ratings and triage rationales are labelled on all clinical views as:
     `"Decision support. AI-assisted. Confirm before acting."`

2. **CDSCO Software as a Medical Device (SaMD) Landscape:**
   - Under the Central Drugs Standard Control Organisation (CDSCO) and the Medical Device Rules (MDR), software intended for medical purposes is assessed based on **its intended functionality and clinical risk**, rather than marketing labels.
   - Software that triages patients, estimates clinical urgency, or prioritizes emergency cases may fall within the scope of regulated medical device software (Class B or Class C depending on the potential severity of risk if an error or delay occurs).
   - **Conclusion for Real-World Deployment:** Any transition of LifeLine or similar software toward actual hospital deployment will require a formal regulatory assessment under CDSCO guidelines, conformity assessment by notified bodies, and compliance with ISO 13485 (Medical devices — Quality management systems) and IEC 62304 (Medical device software — Software life cycle processes).

---

## 2. Alignment with ICMR Ethical Guidelines for AI in Healthcare

LifeLine is intentionally structured to follow the key principles outlined in the **Indian Council of Medical Research (ICMR) Ethical Guidelines for Application of Artificial Intelligence in Biomedical Research and Healthcare**:

1. **Principle of Autonomy and Human Control:**
   - **Non-Authoritative AI:** AI models never make final queue movements, admissions, diagnoses, or prescriptions.
   - **Nurse and Doctor in the Loop:** A qualified nurse must confirm patient presence, conduct physical check-in assessments, and manually approve or override any suggested priority. A doctor confirms clinical findings before concluding any encounter.
   - **Unbroken Escalation Guardrails:** Deterministic red-flag rules take precedence over AI estimates; AI is permitted to raise or maintain urgency, but is structurally prohibited from lowering priority below a hardcoded safety rule.

2. **Principle of Patient Transparency and Disclosure:**
   - Prior to answering intake questions, patients receive clear disclosure:
     `"An automated tool helps prepare information for your care team. A nurse or doctor makes every decision. You can skip these questions and speak to the staff instead."`
   - Patients retain the unconditional right to skip automated screening. Bookings made via skipped screening are explicitly marked as `"not pre-screened"`, mandating an in-person nurse evaluation.

3. **Principle of Accountability and Auditability:**
   - Every priority change, flag, unflag, acknowledge, reorder, emergency transfer, or ABDM consent interaction is logged in an append-only audit trail (`AuditLog`, `NurseActionLog`, `ConsentStatusHistory`) with actor ID, role, timestamp, and clinical justification.
   - Patient words are preserved verbatim and visually separated from decision-support summaries (`"What the patient told us"` vs. `"Decision support"`).

4. **Principle of Continuous Feedback and Error Reporting:**
   - Every generated triage summary features a 1-tap staff feedback control (`Useful` / `Not useful` with optional rationale).
   - Feedback submissions are recorded alongside the active rule engine version, prompt version, and summary ID to facilitate continuous quality monitoring and model drift detection.

---

## 3. Data Protection and Digital Personal Data Protection (DPDP) Act

1. **Data Fiduciary and Data Processor Roles:**
   - The healthcare facility operating the OPD acts as the **Data Fiduciary**, responsible for lawful grounds of processing, data minimisation, and data principal rights.
   - Where an external Cloud LLM API (e.g., Groq, OpenAI, Anthropic) is utilized for speech extraction or rationale generation, that provider acts as a **Third-Party Data Processor**.
   - Symptom descriptions and health concerns transmitted to the LLM constitute health data. In a compliant deployment, data processing agreements (DPAs), local hosting options, or on-premises models (e.g., localized open-weight LLMs) must be evaluated to satisfy data localization and privacy mandates.

2. **Simulated Synthetic Privacy Safeguards:**
   - LifeLine enforces strict data minimisation:
     - No national ID numbers, Aadhaar numbers, or real phone numbers are stored or requested.
     - Synthetic ABHA addresses (`username@abdm`, `username@demo`) are strictly simulated.
     - Nurses are restricted server-side from accessing past diagnosis histories or prescription details.
     - External doctors can only access outside hospital encounters via explicit, time-bounded, purpose-specific, revocable consent requests.

---

## 4. Prototype Limitations and Operational Scope

- **No Clinical Validation:** No clinical trials or observational studies have validated the clinical sensitivity or specificity of the triage rules in patient populations.
- **Clinician Review Required:** All symptom keywords, red-flag triggers, and ESI-to-3-tier mappings are prototype rules that require multidisciplinary clinical panel validation before real clinical pilot testing.
- **Language & Speech Accuracy:** Tamil speech recognition relies on client-side Web Speech APIs or local interfaces and has not been field-tested in noisy OPD waiting room environments.

---

*LifeLine clinical decision support and regulatory documentation reference.*
