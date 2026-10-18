"""FastAPI dependencies: current user and role checks."""

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from app.auth.security import decode_token
from app.db import get_session
from app.models import Doctor, User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_session),
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_token(creds.credentials)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, user_id)
    if user is None or user.role != payload.get("role"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed for this role")
        return user
    return _dep


require_patient = require_roles("patient")
require_nurse = require_roles("nurse")
require_doctor = require_roles("doctor")
require_staff = require_roles("nurse", "doctor")


def doctor_profile(db: Session, user: User) -> Doctor:
    doc = db.exec(select(Doctor).where(Doctor.user_id == user.id)).first()
    if doc is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No doctor profile for this account")
    return doc
