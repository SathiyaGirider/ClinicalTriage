"""
Where a real EHR would plug in (hospital system, or an ABDM-style gateway).
Selected by EHR_BACKEND=external. Deliberately not implemented: this
prototype is designed to be connectable, not connected. See docs/ehr-integration.md.
"""

from app.ehr.adapter import EhrAdapter

_MSG = ("External EHR is not connected in this prototype. Implement ExternalEhrAdapter (auth, FHIR client, "
        "mapping via app/ehr/fhir_mapper.py, consent + audit) and set EHR_BACKEND=external. See docs/ehr-integration.md.")


class ExternalEhrAdapter(EhrAdapter):
    def get_encounters(self, patient_id):
        raise NotImplementedError(_MSG)

    def get_encounter(self, encounter_id):
        raise NotImplementedError(_MSG)

    def save_encounter(self, enc):
        raise NotImplementedError(_MSG)

    def save_prescription(self, encounter_id, items):
        raise NotImplementedError(_MSG)

    def list_prescriptions(self, patient_id):
        raise NotImplementedError(_MSG)
