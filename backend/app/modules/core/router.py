from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import get_db
from .models import AuditLog, Message, OutboxEvent, Staff
from .security import current_staff, make_token, require, verify_password

router = APIRouter(tags=["core"])


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    staff = db.scalar(select(Staff).where(Staff.username == body.username))
    if not staff or not staff.is_active or not verify_password(body.password, staff.password_hash):
        raise HTTPException(401, "Wrong username or password")
    return {"token": make_token(staff), "staff": {
        "id": staff.id, "name": staff.full_name, "role": staff.role, "username": staff.username}}


@router.get("/auth/me")
def me(staff: Staff = Depends(current_staff)):
    return {"id": staff.id, "name": staff.full_name, "role": staff.role, "username": staff.username}


@router.get("/admin/audit")
def audit_log(limit: int = 100, staff: Staff = Depends(require("admin")), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).where(AuditLog.facility_id == staff.facility_id)
                      .order_by(AuditLog.at.desc()).limit(min(limit, 500))).all()
    names = {s.id: s.full_name for s in db.scalars(select(Staff)).all()}
    return [{"at": r.at.isoformat(), "staff": names.get(r.staff_id, "system"), "action": r.action,
             "record_type": r.record_type, "patient_id": r.patient_id, "detail": r.detail} for r in rows]


@router.get("/admin/events")
def events(limit: int = 100, staff: Staff = Depends(require("admin")), db: Session = Depends(get_db)):
    rows = db.scalars(select(OutboxEvent).where(OutboxEvent.facility_id == staff.facility_id)
                      .order_by(OutboxEvent.created_at.desc()).limit(min(limit, 500))).all()
    return [{"at": r.created_at.isoformat(), "type": r.event_type, "payload": r.payload,
             "synced": r.synced_at is not None} for r in rows]


@router.get("/admin/messages")
def messages(limit: int = 50, staff: Staff = Depends(require("admin", "reception")), db: Session = Depends(get_db)):
    rows = db.scalars(select(Message).where(Message.facility_id == staff.facility_id)
                      .order_by(Message.created_at.desc()).limit(min(limit, 200))).all()
    return [{"at": r.created_at.isoformat(), "to": r.to_phone, "channel": r.channel,
             "body": r.body, "status": r.status} for r in rows]
