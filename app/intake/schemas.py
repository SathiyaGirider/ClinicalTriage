"""
Internal request and response schemas for the Intake module.
Strictly imports and uses IntakeResult from app.common.schemas.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field
from app.common.schemas import IntakeResult


class IntakeRequest(BaseModel):
    """
    Client submission payload from browser voice transcript or direct text input.
    """
    raw_transcript: str = Field(
        ...,
        description="Verbatim patient transcript received from client STT or typed input."
    )
    language: Literal["en", "ta"] = Field(
        default="en",
        description="Language code: 'en' for English, 'ta' for Tamil."
    )
    patient_id: Optional[str] = Field(
        default=None,
        description="Optional patient identifier; generated automatically if omitted."
    )
    age: Optional[int] = Field(
        default=None,
        ge=0,
        le=130,
        description="Optional patient age in years."
    )
    known_conditions: list[str] = Field(
        default_factory=list,
        description="Pre-existing patient conditions if already recorded."
    )
    follow_up_answers: dict[str, str] = Field(
        default_factory=dict,
        description="Key-value mapping of answers to previously generated follow-up questions."
    )


class FollowUpQuestion(BaseModel):
    """
    Constrained follow-up clinical question.
    """
    category: Literal[
        "onset",
        "associated_symptoms",
        "history",
        "medications",
    ] = Field(..., description="Standard clinical follow-up category.")
    question: str = Field(..., description="Localized question text in Tamil or English.")
    language: Literal["en", "ta"] = Field(..., description="Language of the question.")


class FollowUpRequest(BaseModel):
    """
    Request model to generate standalone adaptive follow-up questions.
    """
    raw_transcript: str
    language: Literal["en", "ta"] = "en"
    chief_complaint: Optional[str] = None
    duration: Optional[str] = None
    symptoms: list[str] = Field(default_factory=list)


class FollowUpResponse(BaseModel):
    """
    List of 4 to 6 adaptive follow-up questions.
    """
    questions: list[FollowUpQuestion] = Field(default_factory=list)


class IntakeResponseEnvelope(BaseModel):
    """
    Wrapper envelope returned by POST /intake.
    Contains the strict IntakeResult (A -> B contract) plus suggested follow-ups
    and deterministic red flags for UI or downstream preview.
    """
    intake_result: IntakeResult
    suggested_followups: list[FollowUpQuestion] = Field(default_factory=list)
    red_flags_detected: list[str] = Field(
        default_factory=list,
        description="Deterministic red-flag terms flagged by redflag_scan.py for Person B."
    )
