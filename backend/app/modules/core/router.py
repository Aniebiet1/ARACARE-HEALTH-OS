import os
from datetime import timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from ...config import settings
from ...db import get_db, utcnow
from .files import media_type, save_image
from .models import AuditLog, Department, Facility, Message, OutboxEvent, Staff
from .security import (audit, check_password_strength, current_staff, hash_password, make_token, require,
                       verify_password)

router = APIRouter(tags=["core"])
ROLES = ("reception", "nurse", "doctor", "lab", "pharmacy", "admin")


def department_names(db: Session, facility_id: str) -> dict[str, str]:
    return dict(db.execute(select(Department.id, Department.name).where(Department.facility_id == facility_id)).all())


def _staff_view(s: Staff, dept_names: dict[str, str] | None = None) -> dict:
    """Pass `dept_names` when listing many staff; a single view looks its department up."""
    if dept_names is not None:
        dept = dept_names.get(s.department_id)
    else:
        d = object_session(s).get(Department, s.department_id) if s.department_id else None
        dept = d.name if d else None
    return {"id": s.id, "name": s.full_name, "role": s.role, "username": s.username,
            "is_active": s.is_active, "must_change_password": bool(s.must_change_password),
            "position": s.position, "department_id": s.department_id, "department_name": dept,
            "phone": s.phone, "on_duty": bool(s.on_duty)}


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    staff = db.scalar(select(Staff).where(Staff.username == body.username.strip().lower()))
    now = utcnow()
    if staff and staff.locked_until and staff.locked_until > now:
        mins = max(1, round((staff.locked_until - now).total_seconds() / 60))
        raise HTTPException(429, f"Too many failed attempts. Try again in {mins} min or ask an admin to reset.")
    if not staff or not staff.is_active or not verify_password(body.password, staff.password_hash):
        if staff:
            staff.failed_logins = (staff.failed_logins or 0) + 1
            if staff.failed_logins >= settings.login_max_failures:
                staff.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
                staff.failed_logins = 0
                audit(db, staff, "login_locked", "staff", staff.id)
            db.commit()
        raise HTTPException(401, "Wrong username or password")
    staff.failed_logins, staff.locked_until = 0, None
    audit(db, staff, "login", "staff", staff.id)
    db.commit()
    return {"token": make_token(staff), "staff": _staff_view(staff)}


@router.get("/auth/me")
def me(staff: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    fac = db.get(Facility, staff.facility_id)
    # the web client shows admins the set-up wizard while this is false; the API itself never blocks on it
    return {**_staff_view(staff), "facility_onboarded": bool(fac and fac.onboarded_at)}


class DutyIn(BaseModel):
    on_duty: bool


@router.post("/auth/duty")
def set_duty(body: DutyIn, staff: Staff = Depends(require(*ROLES)), db: Session = Depends(get_db)):
    """On/off duty: AraPulse pages on-duty doctors first."""
    staff.on_duty = body.on_duty
    audit(db, staff, "duty_on" if body.on_duty else "duty_off", "staff", staff.id)
    db.commit()
    return _staff_view(staff)


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str


@router.post("/auth/change-password")
def change_password(body: PasswordChangeIn, staff: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, staff.password_hash):
        raise HTTPException(403, "Current password is wrong")
    if body.new_password == body.current_password:
        raise HTTPException(422, "Choose a different password")
    check_password_strength(body.new_password)
    staff.password_hash = hash_password(body.new_password)
    staff.token_version = (staff.token_version or 0) + 1      # other sessions are logged out
    staff.must_change_password = False
    audit(db, staff, "password_change", "staff", staff.id)
    db.commit()
    return {"token": make_token(staff), "staff": _staff_view(staff)}


# ------------------------------------------------------------------ staff accounts (admin)
class StaffIn(BaseModel):
    username: str = Field(min_length=3, max_length=60, pattern=r"^[a-zA-Z0-9._-]+$")
    full_name: str = Field(min_length=2, max_length=120)
    role: str
    password: str
    position: str | None = Field(None, max_length=80)
    department_id: str | None = None
    phone: str | None = Field(None, max_length=30)


class StaffPatch(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=120)
    role: str | None = None
    is_active: bool | None = None
    position: str | None = Field(None, max_length=80)
    department_id: str | None = None     # null clears it
    phone: str | None = Field(None, max_length=30)


class ResetIn(BaseModel):
    password: str


def _check_role(role: str):
    if role not in ROLES:
        raise HTTPException(422, f"role must be one of {', '.join(ROLES)}")


def _check_department(db: Session, admin: Staff, department_id: str | None) -> str | None:
    if not department_id:
        return None
    d = db.get(Department, department_id)
    if not d or d.facility_id != admin.facility_id:
        raise HTTPException(422, "That department does not exist in this hospital")
    return d.id


def _clean(v: str | None) -> str | None:
    return (v or "").strip() or None


def _own_staff(db: Session, admin: Staff, staff_id: str) -> Staff:
    s = db.get(Staff, staff_id)
    if not s or s.facility_id != admin.facility_id:
        raise HTTPException(404, "Staff member not found")
    return s


@router.get("/admin/staff")
def list_staff(admin: Staff = Depends(require("admin")), db: Session = Depends(get_db)):
    rows = db.scalars(select(Staff).where(Staff.facility_id == admin.facility_id).order_by(Staff.full_name)).all()
    names = department_names(db, admin.facility_id)
    return [_staff_view(s, names) for s in rows]


@router.post("/admin/staff", status_code=201)
def create_staff(body: StaffIn, admin: Staff = Depends(require("admin")), db: Session = Depends(get_db)):
    _check_role(body.role)
    check_password_strength(body.password)
    username = body.username.lower()
    if db.scalar(select(Staff).where(Staff.username == username)):
        raise HTTPException(409, "That username is taken")
    s = Staff(facility_id=admin.facility_id, username=username, full_name=body.full_name.strip(), role=body.role,
              position=_clean(body.position), department_id=_check_department(db, admin, body.department_id),
              phone=_clean(body.phone), password_hash=hash_password(body.password), must_change_password=True)
    db.add(s)
    db.flush()
    audit(db, admin, "create", "staff", s.id, detail=f"{username} as {body.role}")
    db.commit()
    return _staff_view(s)


@router.patch("/admin/staff/{staff_id}")
def update_staff(staff_id: str, body: StaffPatch, admin: Staff = Depends(require("admin")),
                 db: Session = Depends(get_db)):
    s = _own_staff(db, admin, staff_id)
    if s.id == admin.id and (body.is_active is False or (body.role and body.role != "admin")):
        raise HTTPException(409, "You cannot deactivate or demote your own account")
    changes = []
    if body.full_name is not None:
        s.full_name = body.full_name.strip()
        changes.append("name")
    if body.role is not None and body.role != s.role:
        _check_role(body.role)
        s.role = body.role
        changes.append(f"role={body.role}")
    if body.is_active is not None and body.is_active != s.is_active:
        s.is_active = body.is_active
        changes.append("activated" if body.is_active else "deactivated")
    sent = body.model_fields_set
    if "position" in sent:
        s.position = _clean(body.position)
        changes.append("position")
    if "department_id" in sent:
        s.department_id = _check_department(db, admin, body.department_id)
        changes.append("department")
    if "phone" in sent:
        s.phone = _clean(body.phone)
        changes.append("phone")
    if any(c.startswith("role") or c == "deactivated" for c in changes):
        s.token_version = (s.token_version or 0) + 1   # role/access change takes effect immediately
    audit(db, admin, "update", "staff", s.id, detail=", ".join(changes) or "no change")
    db.commit()
    return _staff_view(s)


@router.post("/admin/staff/{staff_id}/reset-password")
def reset_password(staff_id: str, body: ResetIn, admin: Staff = Depends(require("admin")),
                   db: Session = Depends(get_db)):
    s = _own_staff(db, admin, staff_id)
    check_password_strength(body.password)
    s.password_hash = hash_password(body.password)
    s.token_version = (s.token_version or 0) + 1
    s.failed_logins, s.locked_until, s.must_change_password = 0, None, True
    audit(db, admin, "password_reset", "staff", s.id)
    db.commit()
    return _staff_view(s)


# ------------------------------------------------------------------ facility profile and branding
FACILITY_TYPES = ("general", "teaching", "specialist", "primary", "clinic")
OWNERSHIPS = ("federal", "state", "private", "mission", "ngo")


def facility_view(f: Facility) -> dict:
    """Public: what a receipt, the login page or the waiting-room TV may show."""
    logo = f.logo_path if f.logo_path and os.path.exists(f.logo_path) else None
    return {"name": f.name, "state_code": f.state_code, "address": f.address, "phone": f.phone, "email": f.email,
            "motto": f.motto,
            # the version busts browser caches when the logo is replaced
            "logo_url": f"/api/facility/logo?v={int(os.path.getmtime(logo))}" if logo else None,
            "city": f.city, "emergency_phone": f.emergency_phone, "website": f.website,
            "open_24h": bool(f.open_24h)}


def facility_profile(f: Facility) -> dict:
    """Admin view: everything captured at onboarding."""
    return {**facility_view(f), "facility_type": f.facility_type, "ownership": f.ownership,
            "license_number": f.license_number, "lga": f.lga, "bed_capacity": f.bed_capacity,
            "onboarded_at": f.onboarded_at.isoformat() if f.onboarded_at else None}


def _facility(db: Session) -> Facility:
    fac = db.scalar(select(Facility))
    if not fac:
        raise HTTPException(503, "Facility not set up")
    return fac


@router.get("/facility")
def get_facility(db: Session = Depends(get_db)):
    """Public, like the waiting-room TV: name, contact details and logo are printed on every receipt anyway."""
    return facility_view(_facility(db))


@router.get("/facility/logo")
def facility_logo(db: Session = Depends(get_db)):
    fac = _facility(db)
    if not fac.logo_path or not os.path.exists(fac.logo_path):
        raise HTTPException(404, "No logo uploaded")
    return FileResponse(fac.logo_path, media_type=media_type(fac.logo_path),
                        headers={"Cache-Control": "public, max-age=86400"})


class FacilityIn(BaseModel):
    """Only the fields sent are changed, so the old branding form (name, address, phone, email, motto) still works."""
    name: str = Field(min_length=2, max_length=200)
    address: str | None = Field(None, max_length=300)
    phone: str | None = Field(None, max_length=60)
    email: str | None = Field(None, max_length=120)
    motto: str | None = Field(None, max_length=160)
    facility_type: str | None = None
    ownership: str | None = None
    license_number: str | None = Field(None, max_length=60)
    city: str | None = Field(None, max_length=80)
    lga: str | None = Field(None, max_length=80)
    emergency_phone: str | None = Field(None, max_length=60)
    website: str | None = Field(None, max_length=160)
    bed_capacity: int | None = Field(None, ge=0, le=5000)
    open_24h: bool | None = None


TEXT_FIELDS = ("address", "phone", "email", "motto", "license_number", "city", "lga", "emergency_phone", "website")


@router.get("/admin/facility")
def get_facility_profile(admin: Staff = Depends(require("admin")), db: Session = Depends(get_db)):
    return facility_profile(db.get(Facility, admin.facility_id))


@router.put("/admin/facility")
def update_facility(body: FacilityIn, admin: Staff = Depends(require("admin")), db: Session = Depends(get_db)):
    fac = db.get(Facility, admin.facility_id)
    sent = body.model_fields_set
    if "facility_type" in sent and body.facility_type and body.facility_type not in FACILITY_TYPES:
        raise HTTPException(422, f"Hospital type must be one of {', '.join(FACILITY_TYPES)}")
    if "ownership" in sent and body.ownership and body.ownership not in OWNERSHIPS:
        raise HTTPException(422, f"Ownership must be one of {', '.join(OWNERSHIPS)}")
    fac.name = body.name.strip()
    for k in TEXT_FIELDS:
        if k in sent:
            setattr(fac, k, _clean(getattr(body, k)))
    for k in ("facility_type", "ownership"):
        if k in sent:
            setattr(fac, k, getattr(body, k) or None)
    if "bed_capacity" in sent:
        fac.bed_capacity = body.bed_capacity
    if body.open_24h is not None:
        fac.open_24h = body.open_24h
    audit(db, admin, "update", "facility", fac.id, detail="profile: " + ", ".join(sorted(sent)))
    db.commit()
    return facility_profile(fac)


@router.post("/admin/facility/logo")
async def upload_logo(file: UploadFile = File(...), admin: Staff = Depends(require("admin")),
                      db: Session = Depends(get_db)):
    fac = db.get(Facility, admin.facility_id)
    fac.logo_path = await save_image(file, "branding", f"logo-{fac.id}", fac.logo_path, what="Logo")
    audit(db, admin, "update", "facility", fac.id, detail="logo uploaded")
    db.commit()
    return facility_profile(fac)


@router.delete("/admin/facility/logo")
def delete_logo(admin: Staff = Depends(require("admin")), db: Session = Depends(get_db)):
    fac = db.get(Facility, admin.facility_id)
    if fac.logo_path and os.path.exists(fac.logo_path):
        os.remove(fac.logo_path)
    fac.logo_path = None
    audit(db, admin, "update", "facility", fac.id, detail="logo removed")
    db.commit()
    return facility_profile(fac)


# ------------------------------------------------------------------ admin views
@router.get("/admin/audit")
def audit_log(limit: int = 100, staff: Staff = Depends(require("admin")), db: Session = Depends(get_db)):
    rows = db.scalars(select(AuditLog).where(AuditLog.facility_id == staff.facility_id)
                      .order_by(AuditLog.at.desc()).limit(min(limit, 500))).all()
    names = {s.id: s.full_name for s in db.scalars(select(Staff).where(Staff.facility_id == staff.facility_id)).all()}
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
