"""Catalog: hospitals, doctors, sessions, department suggestion. Any logged-in user."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.auth.deps import get_current_user
from app.catalog import service
from app.common.symptom_vocab import SPECIALTIES, department_for, normalise_tags
from app.db import get_session
from app.models import Doctor, Hospital, User

router = APIRouter(prefix="/catalog", tags=["Catalog"])


@router.get("/hospitals")
def hospitals(lat: Optional[float] = Query(None, ge=-90, le=90), lon: Optional[float] = Query(None, ge=-180, le=180),
              area: Optional[str] = Query(None, max_length=80), db: Session = Depends(get_session), _: User = Depends(get_current_user)):
    items = [service.hospital_view(h, lat, lon) for h in db.exec(select(Hospital)).all()]
    return service.sort_by_distance_or_area(items, area)


@router.get("/specialties")
def specialties(_: User = Depends(get_current_user)):
    return SPECIALTIES


@router.get("/doctors")
def doctors(specialty: Optional[str] = Query(None, max_length=40), hospital_id: Optional[int] = None,
            lat: Optional[float] = Query(None, ge=-90, le=90), lon: Optional[float] = Query(None, ge=-180, le=180),
            area: Optional[str] = Query(None, max_length=80), db: Session = Depends(get_session), _: User = Depends(get_current_user)):
    q = select(Doctor)
    if specialty:
        q = q.where(Doctor.specialty == specialty)
    if hospital_id:
        q = q.where(Doctor.hospital_id == hospital_id)
    items = [service.doctor_view(db, d, lat, lon) for d in db.exec(q).all()]
    return service.sort_by_distance_or_area(items, area)


@router.get("/doctors/{doctor_id}/sessions")
def doctor_sessions(doctor_id: int, date: Optional[date] = None, db: Session = Depends(get_session), _: User = Depends(get_current_user)):
    if not db.get(Doctor, doctor_id):
        raise HTTPException(404, "Doctor not found")
    return [service.session_view(db, s) for s in service.sessions_for(db, doctor_id, date)]


@router.get("/department")
def department(tags: str = Query("", max_length=500), age: Optional[int] = Query(None, ge=0, le=125), _: User = Depends(get_current_user)):
    tag_list = normalise_tags([t for t in tags.split(",") if t.strip()])
    dept = department_for(tag_list, age)
    return {"department": dept, "text": f"This kind of problem is usually seen by: {dept}"}
