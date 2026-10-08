"""Organisation: departments, wards, the staff directory and the admin's first-run onboarding."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db import get_db, utcnow
from ..core.models import Department, Facility, Staff, Ward
from ..core.router import ROLES, department_names
from ..core.security import audit, require
from .catalogue import KINDS, POSITIONS, create_suggested, suggested_view

router = APIRouter(tags=["org"])
CODE = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,19}$"
signed_in = require(*ROLES)         # any role, but a temporary password still has to be changed first


# ------------------------------------------------------------------ views
def _dept_views(db: Session, facility_id: str) -> list[dict]:
    counts = dict(db.execute(select(Staff.department_id, func.count()).where(
        Staff.facility_id == facility_id, Staff.is_active, Staff.department_id.is_not(None))
        .group_by(Staff.department_id)).all())
    rows = db.scalars(select(Department).where(Department.facility_id == facility_id).order_by(Department.name)).all()
    return [{"id": d.id, "code": d.code, "name": d.name, "kind": d.kind, "is_active": d.is_active,
             "staff_count": counts.get(d.id, 0)} for d in rows]


def _ward_view(w: Ward, names: dict[str, str]) -> dict:
    return {"id": w.id, "code": w.code, "name": w.name, "floor": w.floor, "bed_count": w.bed_count,
            "department_id": w.department_id, "department_name": names.get(w.department_id), "is_active": w.is_active}


def _ward_views(db: Session, facility_id: str) -> list[dict]:
    names = department_names(db, facility_id)
    rows = db.scalars(select(Ward).where(Ward.facility_id == facility_id).order_by(Ward.name)).all()
    return [_ward_view(w, names) for w in rows]


@router.get("/org/departments")
def list_departments(staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    return _dept_views(db, staff.facility_id)


@router.get("/org/wards")
def list_wards(staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    return _ward_views(db, staff.facility_id)


@router.get("/org/directory")
def directory(staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    """Who's who, for paging and messaging. No usernames or phone numbers."""
    names = department_names(db, staff.facility_id)
    rows = db.scalars(select(Staff).where(Staff.facility_id == staff.facility_id, Staff.is_active)
                      .order_by(Staff.full_name)).all()
    return [{"id": s.id, "name": s.full_name, "role": s.role, "position": s.position, "department_id": s.department_id,
             "department_name": names.get(s.department_id), "on_duty": bool(s.on_duty)} for s in rows]


# ------------------------------------------------------------------ departments (admin)
class DepartmentIn(BaseModel):
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=2, max_length=120)
    kind: str = "clinical"


class DepartmentPatch(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    kind: str | None = None
    is_active: bool | None = None


def _check_kind(kind: str):
    if kind not in KINDS:
        raise HTTPException(422, f"Department type must be one of {', '.join(KINDS)}")


def _own(db: Session, model, admin: Staff, row_id: str, what: str):
    row = db.get(model, row_id)
    if not row or row.facility_id != admin.facility_id:
        raise HTTPException(404, f"{what} not found")
    return row


def _code_free(db: Session, model, facility_id: str, code: str, what: str):
    if db.scalar(select(model.id).where(model.facility_id == facility_id, model.code == code)):
        raise HTTPException(409, f"A {what} with code {code} already exists")


@router.post("/admin/departments", status_code=201)
def create_department(body: DepartmentIn, admin: Staff = Depends(require("admin")), db: Session = Depends(get_db)):
    _check_kind(body.kind)
    code = body.code.upper()
    _code_free(db, Department, admin.facility_id, code, "department")
    d = Department(facility_id=admin.facility_id, code=code, name=body.name.strip(), kind=body.kind)
    db.add(d)
    db.flush()
    audit(db, admin, "create", "department", d.id, detail=f"{code} {d.name}")
    db.commit()
    return next(v for v in _dept_views(db, admin.facility_id) if v["id"] == d.id)


@router.patch("/admin/departments/{dept_id}")
def update_department(dept_id: str, body: DepartmentPatch, admin: Staff = Depends(require("admin")),
                      db: Session = Depends(get_db)):
    d = _own(db, Department, admin, dept_id, "Department")
    if body.kind is not None:
        _check_kind(body.kind)
        d.kind = body.kind
    if body.name is not None:
        d.name = body.name.strip()
    if body.is_active is not None:
        d.is_active = body.is_active            # deactivate, never delete: staff and history point at it
    audit(db, admin, "update", "department", d.id, detail=", ".join(sorted(body.model_fields_set)) or "no change")
    db.commit()
    return next(v for v in _dept_views(db, admin.facility_id) if v["id"] == d.id)


# ------------------------------------------------------------------ wards (admin)
class WardIn(BaseModel):
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=2, max_length=120)
    department_id: str | None = None
    floor: str | None = Field(None, max_length=40)
    bed_count: int = Field(0, ge=0, le=500)


class WardPatch(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=120)
    department_id: str | None = None        # null unlinks it
    floor: str | None = Field(None, max_length=40)
    bed_count: int | None = Field(None, ge=0, le=500)
    is_active: bool | None = None


def _ward_department(db: Session, admin: Staff, department_id: str | None) -> str | None:
    if not department_id:
        return None
    d = db.get(Department, department_id)
    if not d or d.facility_id != admin.facility_id:
        raise HTTPException(422, "That department does not exist in this hospital")
    return d.id


@router.post("/admin/wards", status_code=201)
def create_ward(body: WardIn, admin: Staff = Depends(require("admin")), db: Session = Depends(get_db)):
    code = body.code.upper()
    _code_free(db, Ward, admin.facility_id, code, "ward")
    w = Ward(facility_id=admin.facility_id, code=code, name=body.name.strip(),
             department_id=_ward_department(db, admin, body.department_id),
             floor=(body.floor or "").strip() or None, bed_count=body.bed_count)
    db.add(w)
    db.flush()
    audit(db, admin, "create", "ward", w.id, detail=f"{code} {w.name}")
    db.commit()
    return _ward_view(w, department_names(db, admin.facility_id))


@router.patch("/admin/wards/{ward_id}")
def update_ward(ward_id: str, body: WardPatch, admin: Staff = Depends(require("admin")),
                db: Session = Depends(get_db)):
    w = _own(db, Ward, admin, ward_id, "Ward")
    sent = body.model_fields_set
    if body.name is not None:
        w.name = body.name.strip()
    if "department_id" in sent:
        w.department_id = _ward_department(db, admin, body.department_id)
    if "floor" in sent:
        w.floor = (body.floor or "").strip() or None
    if body.bed_count is not None:
        w.bed_count = body.bed_count
    if body.is_active is not None:
        w.is_active = body.is_active
    audit(db, admin, "update", "ward", w.id, detail=", ".join(sorted(sent)) or "no change")
    db.commit()
    return _ward_view(w, department_names(db, admin.facility_id))


# ------------------------------------------------------------------ onboarding (admin)
def _steps(db: Session, fac: Facility) -> dict:
    fid = fac.id
    return {
        "profile": all((fac.name, fac.address, fac.phone, fac.facility_type)),
        "departments": db.scalar(select(Department.id).where(Department.facility_id == fid, Department.is_active)
                                 .limit(1)) is not None,
        "wards": db.scalar(select(Ward.id).where(Ward.facility_id == fid, Ward.is_active).limit(1)) is not None,
        "staff": db.scalar(select(Staff.id).where(Staff.facility_id == fid, Staff.is_active, Staff.role != "admin")
                           .limit(1)) is not None,
    }


@router.get("/admin/onboarding")
def onboarding(admin: Staff = Depends(require("admin")), db: Session = Depends(get_db)):
    fac = db.get(Facility, admin.facility_id)
    return {"completed": fac.onboarded_at is not None,
            "completed_at": fac.onboarded_at.isoformat() if fac.onboarded_at else None,
            "steps": _steps(db, fac), "suggested_departments": suggested_view(), "positions": POSITIONS}


class SuggestedIn(BaseModel):
    codes: list[str] = Field(min_length=1, max_length=50)


@router.post("/admin/onboarding/departments")
def add_suggested(body: SuggestedIn, admin: Staff = Depends(require("admin")), db: Session = Depends(get_db)):
    try:
        new_d, new_w = create_suggested(db, admin.facility_id, body.codes)
    except KeyError as e:
        raise HTTPException(422, f"Not in the suggested list: {e.args[0]}")
    audit(db, admin, "create", "department", detail=f"onboarding: {len(new_d)} departments, {len(new_w)} wards")
    db.commit()
    return {"departments": _dept_views(db, admin.facility_id), "wards": _ward_views(db, admin.facility_id)}


@router.post("/admin/onboarding/complete")
def complete_onboarding(admin: Staff = Depends(require("admin")), db: Session = Depends(get_db)):
    fac = db.get(Facility, admin.facility_id)
    if not _steps(db, fac)["profile"]:
        raise HTTPException(409, "Add the hospital's name, address, phone number and type first")
    if fac.onboarded_at is None:
        fac.onboarded_at, fac.onboarded_by = utcnow(), admin.id
        audit(db, admin, "onboarding_complete", "facility", fac.id)
        db.commit()
    return onboarding(admin, db)
