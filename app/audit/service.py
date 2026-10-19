"""
Action log (who did what to which patient's care) and audit log (who viewed
which patient's history). Values stored here are ids, enum values and short
staff-entered reasons, never symptom text.
"""

import logging

from sqlmodel import Session

from app.models import ActionLog, AuditLog, User

logger = logging.getLogger("lifeline.audit")


def log_action(
    db: Session,
    actor: User | None,
    action: str,
    patient_id: int | None = None,
    original_value: str | None = None,
    new_value: str | None = None,
    reason: str | None = None,
    hospital_id: int | None = None,
    commit: bool = True,
) -> ActionLog:
    row = ActionLog(
        actor_user_id=actor.id if actor else None,
        actor_role=actor.role if actor else "system",
        patient_id=patient_id,
        action=action,
        original_value=original_value,
        new_value=new_value,
        reason=reason,
        hospital_id=hospital_id if hospital_id is not None else (actor.hospital_id if actor else None),
    )
    db.add(row)
    if commit:
        db.commit()
    logger.info("action=%s actor=%s patient=%s", action, row.actor_user_id, patient_id)
    return row


def log_view(db: Session, viewer: User, patient_id: int, scope: str, commit: bool = True) -> AuditLog:
    row = AuditLog(viewer_user_id=viewer.id, patient_id=patient_id, scope=scope)
    db.add(row)
    if commit:
        db.commit()
    logger.info("view scope=%s viewer=%s patient=%s", scope, viewer.id, patient_id)
    return row
