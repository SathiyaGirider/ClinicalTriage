# EHR integration

**Designed to be connectable; not connected in this prototype.**

- `app/ehr/adapter.py` — `EhrAdapter` interface: `get_encounters`, `get_encounter`, `save_encounter`, `save_prescription`, `list_prescriptions`. No access control inside adapters.
- `app/ehr/local_adapter.py` — SQLite implementation (`EHR_BACKEND=local`, default).
- `app/ehr/external_stub.py` — `ExternalEhrAdapter` (`EHR_BACKEND=external`) raises `NotImplementedError` with instructions.
- `app/ehr/fhir_mapper.py` — pure functions to FHIR R4-style JSON (Patient, Encounter, Condition, MedicationRequest). Demo endpoints: `GET /ehr/fhir/Patient/{id}`, `/ehr/fhir/Encounter?patient=`, `/ehr/fhir/MedicationRequest?patient=` (doctor only, policy-filtered, audit-logged).
- `app/ehr/history_policy.py` — who sees what. Stays in our app whatever the backend.

## To connect a real EHR (hospital system or ABDM-style gateway)
1. Implement `ExternalEhrAdapter` with a FHIR client; keep the method signatures.
2. Auth: OAuth2 client credentials / SMART on FHIR backend services; secrets in env/secret store.
3. Mapping table: our `patients.user_id` ↔ external patient id (ABHA/MRN) in a new table; practitioner ids for doctors; ICD-10 codes in `diagnosis_code`.
4. Consent: honour the external system's consent artefacts in addition to `share_history_consent`; record consent ids.
5. Audit: keep writing `audit_log` locally and send access events if the gateway requires them.
6. Run the authz test-suite against the new adapter; add contract tests with a FHIR sandbox.
