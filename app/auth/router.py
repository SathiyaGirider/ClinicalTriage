"""POST /auth/register (patients only), POST /auth/login, GET /auth/me."""

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.auth.security import create_token, hash_password, rate_limiter, verify_password
from app.db import get_session
from app.models import Doctor, Hospital, Patient, User

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = logging.getLogger("lifeline.auth")


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    age: Optional[int] = Field(default=None, ge=0, le=125)
    dob: Optional[str] = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    language: Literal["en", "ta"] = "en"
    area: Optional[str] = Field(default=None, max_length=80)

    model_config = {"extra": "forbid"}  # no phone / ID fields accepted

    @field_validator("full_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("full_name is required")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int


class MeResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    hospital_id: Optional[int] = None
    hospital_name: Optional[str] = None
    doctor_id: Optional[int] = None
    language: Optional[str] = None
    age: Optional[str] = None
    area: Optional[str] = None
    share_history_consent: Optional[bool] = None


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_session)) -> TokenResponse:
    if req.age is None and req.dob is None:
        raise HTTPException(422, "Provide age or date of birth")
    email = req.email.lower()
    if db.exec(select(User).where(User.email == email)).first():
        raise HTTPException(409, "An account with this email already exists")
    user = User(email=email, password_hash=hash_password(req.password), role="patient", full_name=req.full_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(Patient(user_id=user.id, dob_or_age=req.dob or str(req.age), language=req.language, area=req.area))
    db.commit()
    logger.info("registered patient id=%s", user.id)
    return TokenResponse(access_token=create_token(user.id, user.role), role=user.role, user_id=user.id)


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_session)) -> TokenResponse:
    ip = request.client.host if request.client else "unknown"
    email = req.email.lower()
    wait = rate_limiter.locked_for(email, ip)
    if wait > 0:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, f"Too many attempts. Try again in {int(wait) + 1} seconds.")
    user = db.exec(select(User).where(User.email == email)).first()
    if user is None or not verify_password(req.password, user.password_hash):
        rate_limiter.fail(email, ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    rate_limiter.success(email, ip)
    logger.info("login user=%s role=%s", user.id, user.role)
    return TokenResponse(access_token=create_token(user.id, user.role), role=user.role, user_id=user.id)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_session)) -> MeResponse:
    out = MeResponse(id=user.id, email=user.email, full_name=user.full_name, role=user.role, hospital_id=user.hospital_id)
    if user.role == "patient":
        p = db.get(Patient, user.id)
        if p:
            out.language, out.age, out.area, out.share_history_consent = p.language, p.dob_or_age, p.area, p.share_history_consent
    if user.role == "doctor":
        doc = db.exec(select(Doctor).where(Doctor.user_id == user.id)).first()
        if doc:
            out.doctor_id = doc.id
            out.hospital_id = doc.hospital_id
    if out.hospital_id:
        h = db.get(Hospital, out.hospital_id)
        out.hospital_name = h.name if h else None
    return out
