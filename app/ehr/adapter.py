"""
EHR adapter interface. Designed to be connectable; NOT connected in this
prototype (EHR_BACKEND=local uses SQLite). No access-control logic lives in
adapters: policy is in app/ehr/history_policy.py and is applied by callers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class PrescriptionItem(BaseModel):
    drug: str = Field(min_length=1, max_length=120)
    dose: str = Field(default="", max_length=60)
    frequency: str = Field(default="", max_length=60)
    duration: str = Field(default="", max_length=60)
    instructions: str = Field(default="", max_length=300)


class EncounterIn(BaseModel):
    patient_id: int
    doctor_id: int
    appointment_id: Optional[int] = None
    date: date
    diagnosis_text: str
    diagnosis_code: Optional[str] = None
    clinical_notes: str = ""
    follow_up_date: Optional[date] = None


class EncounterRecord(EncounterIn):
    id: int
    doctor_name: str = ""
    specialty: str = ""
    hospital_name: str = ""
    prescriptions: list[PrescriptionItem] = Field(default_factory=list)


class EhrAdapter(ABC):
    @abstractmethod
    def get_encounters(self, patient_id: int) -> list[EncounterRecord]: ...

    @abstractmethod
    def get_encounter(self, encounter_id: int) -> Optional[EncounterRecord]: ...

    @abstractmethod
    def save_encounter(self, enc: EncounterIn) -> EncounterRecord: ...

    @abstractmethod
    def save_prescription(self, encounter_id: int, items: list[PrescriptionItem]) -> None: ...

    @abstractmethod
    def list_prescriptions(self, patient_id: int) -> list[dict]: ...


def get_adapter(db) -> EhrAdapter:
    from app.config import settings
    if settings.ehr_backend == "external":
        from app.ehr.external_stub import ExternalEhrAdapter
        return ExternalEhrAdapter()
    from app.ehr.local_adapter import LocalEhrAdapter
    return LocalEhrAdapter(db)
