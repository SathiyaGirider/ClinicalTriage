"""
Pure functions mapping LifeLine records to FHIR R4-style resources and document bundles
(Patient, Encounter, Condition, MedicationRequest, Composition, Bundle).

Course-project demonstration aligned with ABDM HI Types:
- OPConsultNote (with app-level 'diagnoses only' minimisation projection)
- Prescription

NOTE: Must be checked against official NRCeS FHIR profiles before any real use.
"""

from __future__ import annotations

from typing import Any
from app.ehr.adapter import EncounterRecord


def patient_resource(user_id: int, full_name: str, language: str, dob_or_age: str | None) -> dict[str, Any]:
    res: dict[str, Any] = {
        "resourceType": "Patient",
        "id": str(user_id),
        "name": [{"text": full_name}],
        "communication": [{"language": {"coding": [{"system": "urn:ietf:bcp:47", "code": language}]}}],
        "meta": {"tag": [{"system": "urn:lifeline", "code": "synthetic-demo"}]},
    }
    if dob_or_age and "-" in dob_or_age:
        res["birthDate"] = dob_or_age
    return res


def encounter_resource(e: EncounterRecord) -> dict[str, Any]:
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


def condition_resource(e: EncounterRecord) -> dict[str, Any]:
    code: dict[str, Any] = {"text": e.diagnosis_text}
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


def medication_requests(e: EncounterRecord) -> list[dict[str, Any]]:
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


def composition_resource(
    e: EncounterRecord,
    doc_type: str,  # "OPConsultNote" | "Prescription"
    sections: list[dict[str, Any]],
) -> dict[str, Any]:
    """Top-level document metadata Composition for FHIR R4 document bundle."""
    type_code = "371530004" if doc_type == "OPConsultNote" else "440545006"
    display = "Outpatient Consultation Note" if doc_type == "OPConsultNote" else "Prescription Record"
    return {
        "resourceType": "Composition",
        "id": f"comp-{doc_type.lower()}-{e.id}",
        "status": "final",
        "type": {
            "coding": [{"system": "http://snomed.info/sct", "code": type_code, "display": display}],
            "text": display,
        },
        "category": [
            {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/composition-category", "code": "clinical-note"}]}
        ],
        "subject": {"reference": f"Patient/{e.patient_id}"},
        "encounter": {"reference": f"Encounter/{e.id}"},
        "date": e.date.isoformat(),
        "author": [{"reference": f"Practitioner/{e.doctor_id}", "display": e.doctor_name}],
        "title": f"{display} - {e.date.isoformat()}",
        "section": sections,
    }


def op_consult_note_document_bundle(e: EncounterRecord, diagnoses_only: bool = False) -> dict[str, Any]:
    """
    Creates an ABDM-style FHIR R4 Document Bundle for OPConsultNote.
    If diagnoses_only is True, clinical notes and prescriptions are omitted (data minimisation).
    """
    enc = encounter_resource(e)
    cond = condition_resource(e)

    sections = [
        {
            "title": "Diagnosis / Chief Findings",
            "code": {"coding": [{"system": "http://snomed.info/sct", "code": "439401000124108", "display": "Diagnosis"}]},
            "entry": [{"reference": f"Condition/{cond['id']}"}],
        }
    ]

    entries = [enc, cond]

    if not diagnoses_only:
        meds = medication_requests(e)
        if meds:
            sections.append({
                "title": "Prescriptions",
                "code": {"coding": [{"system": "http://snomed.info/sct", "code": "721912009", "display": "Medication summary"}]},
                "entry": [{"reference": f"MedicationRequest/{m['id']}"} for m in meds],
            })
            entries.extend(meds)

    comp = composition_resource(e, "OPConsultNote", sections)
    if diagnoses_only:
        comp["meta"] = {"tag": [{"code": "app-minimised-diagnoses-only"}]}

    all_resources = [comp] + entries
    return {
        "resourceType": "Bundle",
        "id": f"bundle-opconsult-{e.id}",
        "type": "document",
        "meta": {"profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/OPConsultRecord"]},
        "timestamp": f"{e.date.isoformat()}T10:00:00Z",
        "entry": [{"fullUrl": f"urn:uuid:{r.get('id', '')}", "resource": r} for r in all_resources],
    }


def prescription_document_bundle(e: EncounterRecord) -> dict[str, Any]:
    """
    Creates an ABDM-style FHIR R4 Document Bundle for Prescription.
    """
    enc = encounter_resource(e)
    meds = medication_requests(e)

    sections = [
        {
            "title": "Prescribed Medications",
            "code": {"coding": [{"system": "http://snomed.info/sct", "code": "721912009", "display": "Medication summary"}]},
            "entry": [{"reference": f"MedicationRequest/{m['id']}"} for m in meds],
        }
    ]

    comp = composition_resource(e, "Prescription", sections)
    all_resources = [comp, enc] + meds
    return {
        "resourceType": "Bundle",
        "id": f"bundle-prescription-{e.id}",
        "type": "document",
        "meta": {"profile": ["https://nrces.in/ndhm/fhir/r4/StructureDefinition/PrescriptionRecord"]},
        "timestamp": f"{e.date.isoformat()}T10:00:00Z",
        "entry": [{"fullUrl": f"urn:uuid:{r.get('id', '')}", "resource": r} for r in all_resources],
    }


def bundle(resources: list[dict[str, Any]]) -> dict[str, Any]:
    """Legacy/searchset bundle builder."""
    return {"resourceType": "Bundle", "type": "searchset", "total": len(resources), "entry": [{"resource": r} for r in resources]}
