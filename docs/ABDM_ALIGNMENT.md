# ABDM Alignment and Simulation Architecture

> **CRITICAL DISCLAIMER**:
> LifeLine is an educational research and local course demo. **It is NOT connected to ABDM, NOT certified by the National Health Authority (NHA), and has NOT completed official sandbox testing.** All Ayushman Bharat Digital Mission (ABDM) features described below and implemented in the application are strictly **SIMULATIONS** designed to illustrate protocol alignment, consent architecture, cryptographic transport, and FHIR standardisation without connecting to live government gateways or processing real patient credentials.

---

## 1. Feature Mapping Table

| LifeLine Feature | ABDM Concept | Implementation in LifeLine | What is Simulated | Key Differences & Simplifications |
| :--- | :--- | :--- | :--- | :--- |
| **Consent Requests & Lifecycle** | HIU-initiated Consent Request (HIP/HIU Consent Manager) | Doctor initiates request specifying purpose, date range, and record types (`OPConsultNote`, `Prescription`). Patient approves/denies/revokes in Privacy inbox. Expiry enforced on every read. | Local SQLite database simulation of Consent Manager Gateway routing via `app/abdm_mock/gateway.py` (`MockGateway`). | In ABDM, requests are pushed via NHA Gateway webhooks and the patient interacts via an approved PHR app (e.g., ABHA App, Aarogya Setu). In LifeLine, the patient approves inside the same portal. |
| **Provider-Side Scope Enforcement** | Health Information Provider (HIP) Data Transfer Guardrails | `MockGateway` and provider route verify consent status (`GRANTED`), unexpired validity, matching requester doctor ID, and filter encounter records by date range and approved `hi_types`. | Simulated within the mock gateway adapter before generating responses. | In production, HIP and HIU are physically distinct server systems communicating asynchronously over mutual TLS with encrypted artifact handshakes. |
| **Record Minimisation Projection** | Health Information Types (`hi_types`) | LifeLine supports `OPConsultNote` and `Prescription`. An app-level "diagnoses only" projection excludes medication details when prescription sharing is not explicitly granted. | Documented as an application-level privacy minimisation setting, not an official NHA-defined subtype. | NHA defines discrete HI Types (`OPConsultNote`, `Prescription`, `DiagnosticReport`, `DischargeSummary`, `ImmunizationRecord`, `WellnessRecord`, `HealthDocumentRecord`). |
| **FHIR Standardisation** | ABDM FHIR R4 Bundles | `app/ehr/fhir_mapper.py` produces FHIR R4 Document Bundles containing a `Composition` with referenced `Condition`, `MedicationRequest`, and `Practitioner` resources. | Internal Python mapper generating valid FHIR R4 JSON schemas. | Production ABDM requires conformance to NRCeS India FHIR R4 Profiles (e.g., `ndhm-op-consult-note`). Bundles must be verified against official NRCeS Simplifier packages before live deployment. |
| **Simulated Secure Transfer** | Diffie-Hellman Key Agreement & AES-GCM Encrypted Bundles | `app/abdm_mock/crypto.py` implements ECDH (`SECP256R1`) key exchange, HKDF key derivation, AES-256-GCM encryption, and ECDSA digital signatures per doctor pair. | Demo keypairs generated deterministically per doctor ID using Python's standard `cryptography` library. | In live ABDM, keys are exchanged dynamically through the ABDM Gateway `/v0.5/health-information/hip/on-request` flow with ephemeral public keys and nonce verification. |
| **Scan and Share** | ABDM OPD Scan & Share (QR-based Demographic Sharing) | Patient displays synthetic ABHA card with token/QR; nurse check-in desk accepts synthetic ABHA or code, sharing **only** name, age, gender, and synthetic ABHA address for instant check-in or walk-in token. | Simulated QR and demographic exchange; no live counter QR scanner. | Never shares health records or past consultation history; shares strictly the 4 demographic fields to accelerate OPD desk registration. |
| **Identity & ABHA Address** | Ayushman Bharat Health Account (ABHA Address & Number) | Profile allows setting a synthetic ABHA address (`name@abdm`, `name@demo`, `name@sbx`). Real Aadhaar or mobile OTP verification is completely omitted. | Enforced by regex (`^[a-zA-Z0-9._-]+@(abdm|demo|sbx)$`); purely synthetic. | Real ABDM uses 14-digit ABHA Numbers, ABHA Addresses (`@abdm`), OTP/Aadhaar/facial authentication, and digital tokens. Real identification is strictly forbidden in LifeLine. |

---

## 2. Requirements for Real Production Go-Live

To transition from this simulation to a certified live ABDM deployment, the following formal prerequisites and steps would be required:

1. **Healthcare Facility & Professional Registration:**
   - Register the medical facility in the **Health Facility Registry (HFR)** to obtain a verified Facility ID.
   - Register all practicing clinicians in the **Healthcare Professionals Registry (HPR)** to obtain HP-IDs.

2. **NHA Sandbox Onboarding & Milestone Completion:**
   - Apply for an official ABDM Sandbox account to receive API client credentials (`client_id` and `client_secret`).
   - Implement and pass official compliance testing for at least Milestones 1, 2, and 3:
     - **Milestone 1:** ABHA Creation, Verification, and Demographic Linking (including Scan & Share).
     - **Milestone 2:** HIP role: Discovery of records by ABHA, linking token generation, consent notification ingestion, and encrypted health data transfer.
     - **Milestone 3:** HIU role: Consent request generation, tracking consent status, receiving encrypted FHIR bundles, and decrypting/rendering data.

3. **NRCeS FHIR Profile Conformance:**
   - Align all JSON bundles strictly with the official National Resource Centre for EHR Standards (NRCeS) profiles:
     - `ndhm-op-consult-note`
     - `ndhm-prescription`
     - Validated using the official HL7 FHIR validator and NRCeS IG packages.

4. **Third-Party Security & Compliance Audit:**
   - Undergo a comprehensive Vulnerability Assessment and Penetration Testing (VAPT) and software architecture audit conducted by a CERT-In empanelled auditing agency.
   - Obtain formal security clearance certifying adherence to data protection standards, secure key management, and zero leakage of unconsented patient health data.

5. **Formal NHA Functional Certification:**
   - Conduct joint integration and functional testing sessions with NHA technical evaluators.
   - Obtain production credentials and gateway authorization upon passing all verification milestones.

---

## 3. Open Questions and Clarifications to Verify

1. **Granular HI Type Minimisation:** Does the live ABDM Consent Manager allow patient-side filtering of specific resource sections (such as diagnosis-only without medications) within an `OPConsultNote`, or must the provider issue a distinct, redacted Composition profile?
2. **Scan & Share Walk-In Session Caps:** What standard webhook timeout and response payload structure does NHA prescribe when an OPD reaches peak capacity during a physical Scan & Share check-in wave?
3. **Revocation Propagation Latency:** In production asynchronous federated transfer, what is the maximum permissible grace period between a patient revoking consent on their PHR app and an HIU cache purging decrypted health data?

---

*LifeLine architectural alignment reference. Simulation only. Never claim compliance or certification.*
