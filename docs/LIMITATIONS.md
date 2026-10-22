# Prototype Scope & System Limitations

> **TRANSPARENCY STATEMENT**:
> LifeLine is an educational research prototype and local course demonstration. To maintain absolute clinical and technical integrity, this document provides an honest, non-defensive record of what the application **does not do** and cannot claim.

---

## 1. Clinical Limitations

1. **No Clinical Validation:**
   - The symptom extraction models, red-flag triggers, and ESI-to-3-tier triage classifications have **never** undergone clinical trials, diagnostic accuracy studies, or observational validation in real emergency or outpatient cohorts.
   - The software cannot guarantee sensitivity or specificity regarding critical clinical conditions.
2. **Prototype Rules:**
   - The rules defined in `app/triage/rules.py` represent a prototype heuristics list. They require formal adaptation, calibration, and approval by a certified clinical panel before any real-world pilot testing.
3. **Speech Recognition Accuracy (Tamil & Dialects):**
   - Speech-to-text functionality relies on browser-level Web Speech API passthroughs. It has not been field-tested in noisy outpatient waiting halls, with pediatric speakers, or across non-standard colloquial dialects of Tamil.

---

## 2. ABDM Simulation Limitations

1. **Zero Government Connection:**
   - LifeLine is **not** connected to the National Health Authority (NHA) ABDM Gateway, does not communicate with government sandboxes, and holds no ABDM software certification.
2. **Synthetic Identities Only:**
   - Real 14-digit ABHA Numbers, Aadhaar OTP authentication, and biometric verification are completely omitted. All ABHA identifiers in the system are synthetic strings (e.g., `username@abdm`, `username@demo`).
3. **Simplified Exchange Topography:**
   - The Consent Manager, Health Information Provider (HIP), and Health Information User (HIU) exist as logical database abstractions within a single local application rather than federated microservices operating across public health networks.

---

## 3. EHR & Interoperability Limitations

1. **No Production Hospital Information System (HIS/EHR) Integration:**
   - Encounter and prescription data are stored locally in SQLite (`app/models.py`). There is no live HL7 v2/v3 feed, DICOM imaging PACS connection, or real Epic/Cerner/Bahmni EHR integration.
2. **Draft NRCeS FHIR Profiles:**
   - While `app/ehr/fhir_mapper.py` outputs valid FHIR R4 JSON documents (`Bundle`, `Composition`, `Condition`, `MedicationRequest`), they must be validated against official National Resource Centre for EHR Standards (NRCeS) Simplifier packages prior to production exchange.

---

## 4. Infrastructure & Deployment Limitations

1. **Local Course Demo Scope:**
   - The application is intentionally configured to run on a local developer machine using SQLite and Python/Uvicorn.
   - It does not include Docker containerization, Kubernetes helm charts, CI/CD deployment pipelines, automated Prometheus/Grafana metric stacks, or distributed PostgreSQL database clusters.
2. **Local Session Storage & State:**
   - In-memory rate limiting and local SQLite concurrency limits mean the app is optimized for desktop demonstration rather than high-throughput enterprise scale.

---

*LifeLine prototype boundaries and known limitations.*
