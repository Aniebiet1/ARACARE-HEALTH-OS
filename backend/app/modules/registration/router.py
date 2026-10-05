import os
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...config import settings
from ...db import get_db
from ...events import publish
from ..core.messaging import queue_message
from ..core.models import Consent, Facility, Staff
from ..core.security import audit, require
from ..ehr.models import AllergyRecord
from ..ehr.clinical_rules import drug_class_of
from ..queues import service as queue_service
from . import service
from .models import Patient, Visit

router = APIRouter(tags=["registration"])
FRONT = ("reception", "nurse", "doctor", "admin")


class AllergyIn(BaseModel):
    allergen_name: str
    reaction: str | None = None
    severity: str = "moderate"


class PatientIn(BaseModel):
    surname: str = Field(min_length=1)
    first_name: str = Field(min_length=1)
    middle_name: str | None = None
    phone: str = Field(min_length=7)
    date_of_birth: date
    gender: str
    nok_name: str | None = None
    nok_phone: str | None = None
    state_of_origin: str | None = None
    hmo_provider: str | None = None
    hmo_number: str | None = None
    blood_group: str | None = None
    allergies: list[AllergyIn] = []
    force: bool = False   # register anyway after the duplicate warning


def _summary(p: Patient, db: Session) -> dict:
    allergies = db.scalars(select(AllergyRecord).where(AllergyRecord.patient_id == p.id)).all()
    last = db.scalar(select(Visit).where(Visit.patient_id == p.id).order_by(Visit.checked_in_at.desc()))
    return {"id": p.id, "patient_number": p.patient_number, "surname": p.surname, "first_name": p.first_name,
            "middle_name": p.middle_name, "phone": p.phone, "date_of_birth": p.date_of_birth.isoformat(),
            "age": service.age_years(p.date_of_birth), "gender": p.gender, "category": p.category,
            "hmo_provider": p.hmo_provider, "has_photo": bool(p.photo_path),
            "allergies": [a.allergen_name for a in allergies],
            "last_visit": last.checked_in_at.date().isoformat() if last else None}


@router.post("/patients", status_code=201)
def register(body: PatientIn, staff: Staff = Depends(require("reception", "admin")), db: Session = Depends(get_db)):
    if body.gender not in ("male", "female", "other"):
        raise HTTPException(422, "gender must be male, female or other")
    if body.date_of_birth > date.today():
        raise HTTPException(422, "Date of birth cannot be in the future")
    if not body.force:
        dupes = service.find_possible_duplicates(db, staff.facility_id, body.surname, body.first_name,
                                                 body.phone, body.date_of_birth)
        if dupes:
            raise HTTPException(409, {"code": "possible_duplicate",
                                      "message": "This looks like an existing patient.",
                                      "candidates": [_summary(d, db) for d in dupes]})
    fac = db.get(Facility, staff.facility_id)
    p = Patient(facility_id=fac.id, patient_number=service.next_patient_number(db, fac.id, fac.state_code),
                surname=body.surname.strip(), first_name=body.first_name.strip(),
                middle_name=body.middle_name, phone=service.normalise_phone(body.phone),
                date_of_birth=body.date_of_birth, gender=body.gender,
                category=service.category_for(body.date_of_birth), nok_name=body.nok_name,
                nok_phone=body.nok_phone, state_of_origin=body.state_of_origin,
                hmo_provider=body.hmo_provider, hmo_number=body.hmo_number,
                blood_group=body.blood_group, registered_by=staff.id)
    db.add(p)
    db.flush()
    for a in body.allergies:  # Tier-2 field captured at reception; owned by the EHR table
        db.add(AllergyRecord(patient_id=p.id, allergen_name=a.allergen_name, reaction=a.reaction,
                             severity=a.severity, drug_class=drug_class_of(a.allergen_name) or a.allergen_name.lower(),
                             recorded_by=staff.id))
    queue_message(db, fac.id, p.id, p.phone, service.card_text(p))
    publish(db, "PatientRegistered", {"patient_id": p.id, "patient_number": p.patient_number}, fac.id)
    audit(db, staff, "create", "patient", p.id, p.id)
    db.commit()
    return {**_summary(p, db), "card_text": service.card_text(p)}


@router.get("/patients/search")
def search(q: str, staff: Staff = Depends(require(*FRONT)), db: Session = Depends(get_db)):
    results = service.search(db, staff.facility_id, q)
    audit(db, staff, "search", "patient", None, None, detail=f"q={q[:40]}")
    db.commit()
    return [_summary(p, db) for p in results]


@router.get("/patients/{patient_id}")
def get_patient(patient_id: str, staff: Staff = Depends(require(*FRONT)), db: Session = Depends(get_db)):
    p = db.get(Patient, patient_id)
    if not p or p.facility_id != staff.facility_id:
        raise HTTPException(404, "Patient not found")
    audit(db, staff, "view", "patient", p.id, p.id)
    db.commit()
    return {**_summary(p, db), "card_text": service.card_text(p), "nok_name": p.nok_name, "nok_phone": p.nok_phone}


@router.post("/patients/{patient_id}/photo")
async def upload_photo(patient_id: str, consent: bool = Form(...), file: UploadFile | None = File(None),
                       staff: Staff = Depends(require("reception", "admin")), db: Session = Depends(get_db)):
    p = db.get(Patient, patient_id)
    if not p or p.facility_id != staff.facility_id:
        raise HTTPException(404, "Patient not found")
    # consent is recorded either way; the photo is stored only if granted
    db.add(Consent(facility_id=p.facility_id, patient_id=p.id, consent_type="photo", granted=consent,
                   recorded_by=staff.id))
    if consent and file is not None:
        os.makedirs(os.path.join(settings.data_dir, "photos"), exist_ok=True)
        path = os.path.join(settings.data_dir, "photos", f"{p.id}.jpg")
        with open(path, "wb") as f:
            f.write(await file.read())
        p.photo_path = path
    audit(db, staff, "consent_photo" if consent else "refuse_photo", "patient", p.id, p.id)
    db.commit()
    return {"photo_saved": bool(p.photo_path), "consent": consent}


class CheckInIn(BaseModel):
    visit_type: str = "new_complaint"
    payment_track: str = "out_of_pocket"


@router.post("/patients/{patient_id}/check-in", status_code=201)
def check_in(patient_id: str, body: CheckInIn, staff: Staff = Depends(require("reception", "admin")),
             db: Session = Depends(get_db)):
    if body.visit_type not in ("new_complaint", "follow_up", "anc", "emergency"):
        raise HTTPException(422, "Unknown visit type")
    p = db.get(Patient, patient_id)
    if not p or p.facility_id != staff.facility_id:
        raise HTTPException(404, "Patient not found")
    open_visit = db.scalar(select(Visit).where(Visit.patient_id == p.id,
                                               Visit.status.in_(("checked_in", "in_progress"))))
    if open_visit:
        raise HTTPException(409, "This patient already has an open visit today")
    v = Visit(facility_id=p.facility_id, patient_id=p.id, visit_type=body.visit_type,
              payment_track=body.payment_track if p.hmo_provider or body.payment_track == "out_of_pocket" else "out_of_pocket",
              checked_in_by=staff.id)
    db.add(v)
    db.flush()
    journey, ticket = queue_service.start_journey(db, v, p)
    publish(db, "VisitCheckedIn", {"visit_id": v.id, "patient_id": p.id, "visit_type": v.visit_type,
                                   "payment_track": v.payment_track}, p.facility_id, room="queue")
    audit(db, staff, "check_in", "visit", v.id, p.id)
    db.commit()
    return {"visit_id": v.id, "ticket": ticket.ticket_number, "priority": ticket.priority_tier,
            "department": ticket.department}
