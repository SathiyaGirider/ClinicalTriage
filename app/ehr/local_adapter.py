"""SQLite implementation of EhrAdapter (EHR_BACKEND=local)."""

from __future__ import annotations

import json
from typing import Optional

from sqlmodel import Session, select

from app.ehr.adapter import EhrAdapter, EncounterIn, EncounterRecord, PrescriptionItem
from app.models import Doctor, Encounter, Hospital, Prescription


class LocalEhrAdapter(EhrAdapter):
    def __init__(self, db: Session):
        self.db = db

    def _record(self, e: Encounter) -> EncounterRecord:
        doc = self.db.get(Doctor, e.doctor_id)
        h = self.db.get(Hospital, doc.hospital_id) if doc else None
        items: list[PrescriptionItem] = []
        for p in self.db.exec(select(Prescription).where(Prescription.encounter_id == e.id)).all():
            items += [PrescriptionItem.model_validate(i) for i in json.loads(p.items_json)]
        return EncounterRecord(id=e.id, patient_id=e.patient_id, doctor_id=e.doctor_id, appointment_id=e.appointment_id, date=e.date,
                               diagnosis_text=e.diagnosis_text, diagnosis_code=e.diagnosis_code, clinical_notes=e.clinical_notes,
                               follow_up_date=e.follow_up_date, doctor_name=doc.name if doc else "", specialty=doc.specialty if doc else "",
                               hospital_name=h.name if h else "", prescriptions=items)

    def get_encounters(self, patient_id: int) -> list[EncounterRecord]:
        rows = self.db.exec(select(Encounter).where(Encounter.patient_id == patient_id).order_by(Encounter.date.desc(), Encounter.id.desc())).all()
        return [self._record(e) for e in rows]

    def get_encounter(self, encounter_id: int) -> Optional[EncounterRecord]:
        e = self.db.get(Encounter, encounter_id)
        return self._record(e) if e else None

    def save_encounter(self, enc: EncounterIn) -> EncounterRecord:
        e = Encounter(**enc.model_dump())
        self.db.add(e)
        self.db.flush()
        return self._record(e)

    def save_prescription(self, encounter_id: int, items: list[PrescriptionItem]) -> None:
        if items:
            self.db.add(Prescription(encounter_id=encounter_id, items_json=json.dumps([i.model_dump() for i in items])))
            self.db.flush()

    def list_prescriptions(self, patient_id: int) -> list[dict]:
        out = []
        for rec in self.get_encounters(patient_id):
            for item in rec.prescriptions:
                out.append({"encounter_id": rec.id, "date": rec.date.isoformat(), "doctor_name": rec.doctor_name, **item.model_dump()})
        return out
