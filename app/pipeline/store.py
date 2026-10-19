"""Persistence helpers for IntakeResult / TriageDecision / DoctorSummary JSON rows."""

from __future__ import annotations

from sqlmodel import Session, select

from app.common.schemas import DoctorSummary, IntakeResult, TriageDecision
from app.models import IntakeRecord, SummaryRow, TriageDecisionRow


def save_intake(db: Session, patient_id: int, intake: IntakeResult, appointment_id: int | None = None) -> IntakeRecord:
    row = IntakeRecord(patient_id=patient_id, appointment_id=appointment_id, intake_json=intake.model_dump_json())
    db.add(row)
    db.flush()
    return row


def update_intake(db: Session, row: IntakeRecord, intake: IntakeResult) -> None:
    row.intake_json = intake.model_dump_json()
    db.add(row)


def load_intake(db: Session, intake_id: int | None) -> IntakeResult | None:
    if not intake_id:
        return None
    row = db.get(IntakeRecord, intake_id)
    return IntakeResult.model_validate_json(row.intake_json) if row else None


def save_decision(db: Session, intake_id: int, d: TriageDecision) -> TriageDecisionRow:
    row = TriageDecisionRow(intake_id=intake_id, decision_json=d.model_dump_json())
    db.add(row)
    db.flush()
    return row


def latest_decision(db: Session, intake_id: int | None) -> TriageDecision | None:
    if not intake_id:
        return None
    row = db.exec(select(TriageDecisionRow).where(TriageDecisionRow.intake_id == intake_id).order_by(TriageDecisionRow.id.desc())).first()
    return TriageDecision.model_validate_json(row.decision_json) if row else None


def save_summary(db: Session, intake_id: int, s: DoctorSummary) -> None:
    db.add(SummaryRow(intake_id=intake_id, summary_json=s.model_dump_json()))
    db.flush()


def latest_summary(db: Session, intake_id: int | None) -> DoctorSummary | None:
    if not intake_id:
        return None
    row = db.exec(select(SummaryRow).where(SummaryRow.intake_id == intake_id).order_by(SummaryRow.id.desc())).first()
    return DoctorSummary.model_validate_json(row.summary_json) if row else None
