"""
Pure functions mapping LifeLine records to FHIR R4-style resources as plain
JSON (Patient, Encounter, Condition, MedicationRequest). Demonstration only;
not validated against a FHIR server.
"""

from __future__ import annotations

from app.ehr.adapter import EncounterRecord


def patient_resource(user_id: int, full_name: str, language: str, dob_or_age: str | None) -> dict:
    res = {
        "resourceType": "Patient",
        "id": str(user_id),
        "name": [{"text": full_name}],
        "communication": [{"language": {"coding": [{"system": "urn:ietf:bcp:47", "code": language}]}}],
        "meta": {"tag": [{"system": "urn:lifeline", "code": "synthetic-demo"}]},
    }
    if dob_or_age and "-" in dob_or_age:
        res["birthDate"] = dob_or_age
    return res


def encounter_resource(e: EncounterRecord) -> dict:
    return {
        "resourceType": "Encounter",
        "id": str(e.id),
        "status": "finished",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB", "display": "ambulatory"},
        "subject": {"reference": f"Patient/{e.patient_id}"},
        "participant": [{"individual": {"reference": f"Practitioner/{e.doctor_id}", "display": e.doctor_name}}],
        "period": {"start": e.date.isoformat()},
        "serviceProvider": {"display": e.hospital_name},
        "serviceType": {"text": e.specialty},
    }


def condition_resource(e: EncounterRecord) -> dict:
    code = {"text": e.diagnosis_text}
    if e.diagnosis_code:
        code["coding"] = [{"system": "http://hl7.org/fhir/sid/icd-10", "code": e.diagnosis_code}]
    return {
        "resourceType": "Condition",
        "id": f"cond-{e.id}",
        "subject": {"reference": f"Patient/{e.patient_id}"},
        "encounter": {"reference": f"Encounter/{e.id}"},
        "code": code,
        "recordedDate": e.date.isoformat(),
        "asserter": {"reference": f"Practitioner/{e.doctor_id}"},
    }


def medication_requests(e: EncounterRecord) -> list[dict]:
    out = []
    for i, item in enumerate(e.prescriptions):
        out.append({
            "resourceType": "MedicationRequest",
            "id": f"medreq-{e.id}-{i}",
            "status": "active",
            "intent": "order",
            "subject": {"reference": f"Patient/{e.patient_id}"},
            "encounter": {"reference": f"Encounter/{e.id}"},
            "requester": {"reference": f"Practitioner/{e.doctor_id}"},
            "medicationCodeableConcept": {"text": item.drug},
            "dosageInstruction": [{"text": " ".join(x for x in [item.dose, item.frequency, item.duration, item.instructions] if x)}],
            "authoredOn": e.date.isoformat(),
        })
    return out


def bundle(resources: list[dict]) -> dict:
    return {"resourceType": "Bundle", "type": "searchset", "total": len(resources), "entry": [{"resource": r} for r in resources]}
