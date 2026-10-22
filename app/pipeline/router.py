"""POST /pipeline/submit: intake -> triage -> summary -> PatientAdvice (fail safe)."""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth.deps import get_current_user
from app.db import get_session
from app.models import User
from app.pipeline.service import load_session, submit

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


class SubmitRequest(BaseModel):
    intake_session_id: str = Field(min_length=1, max_length=40)
    hold_id: Optional[int] = None


class LoadScenarioRequest(BaseModel):
    scenario: str = Field(min_length=1, max_length=40)
    hold_id: Optional[int] = None


@router.post("/submit")
def submit_endpoint(req: SubmitRequest, user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    row = load_session(db, req.intake_session_id, user)
    return submit(db, user, row, req.hold_id)


@router.get("/scenarios")
def list_scenarios():
    from fastapi import HTTPException
    from app.config import settings
    if not settings.dev_endpoints:
        raise HTTPException(404, "Dev endpoints disabled")
    from pathlib import Path
    import json
    mock_dir = Path(__file__).resolve().parents[2] / "mock-data"
    out = []
    for p in sorted(mock_dir.glob("scenario-*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"))
            out.append({
                "file": p.name,
                "id": data.get("scenario_id", p.stem),
                "title": data.get("stageA", {}).get("patient_story", "")[:120] or p.stem,
            })
        except Exception:
            pass
    return out


@router.post("/load-scenario")
def load_scenario_endpoint(req: LoadScenarioRequest, user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    from fastapi import HTTPException
    from app.config import settings
    from app.pipeline.service import submit_scenario
    if not settings.dev_endpoints:
        raise HTTPException(404, "Dev endpoints disabled")
    return submit_scenario(db, user, req.scenario, req.hold_id)


class SkipIntakeRequest(BaseModel):
    hold_id: int


@router.post("/skip-intake")
def skip_intake_endpoint(req: SkipIntakeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    """Patient opts out of automated triage questions (ICMR-aligned)."""
    from app.pipeline.service import skip_intake
    return skip_intake(db, user, req.hold_id)


class FeedbackRequest(BaseModel):
    summary_id: int
    useful: bool
    reason: Optional[str] = Field(default=None, max_length=300)


@router.post("/feedback")
def submit_feedback(req: FeedbackRequest, user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    """Staff one-tap feedback on AI decision-support summary."""
    from app.models import SummaryFeedback, SummaryRow
    summary = db.get(SummaryRow, req.summary_id)
    if not summary:
        from fastapi import HTTPException
        raise HTTPException(404, "Summary not found")
    fb = SummaryFeedback(
        summary_id=req.summary_id,
        user_id=user.id,
        role=user.role,
        useful=req.useful,
        reason=req.reason.strip() if req.reason else None,
        rules_version="1.0",
        prompt_version="1.0",
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return {"status": "saved", "id": fb.id, "useful": fb.useful}


@router.get("/feedback/counts")
def feedback_counts(user: User = Depends(get_current_user), db: Session = Depends(get_session)):
    """Summary of staff feedback counts."""
    from sqlmodel import select
    from app.models import SummaryFeedback
    all_fb = db.exec(select(SummaryFeedback)).all()
    useful = sum(1 for f in all_fb if f.useful)
    not_useful = sum(1 for f in all_fb if not f.useful)
    return {
        "total": len(all_fb),
        "useful": useful,
        "not_useful": not_useful,
        "recent": [
            {"id": f.id, "summary_id": f.summary_id, "useful": f.useful, "reason": f.reason, "role": f.role, "ts": f.created_at.isoformat()}
            for f in sorted(all_fb, key=lambda x: x.id or 0, reverse=True)[:20]
        ],
    }

