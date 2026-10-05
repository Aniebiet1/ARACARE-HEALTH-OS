import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...db import get_db, utcnow
from ...events import publish
from ..core.models import Staff
from ..core.security import audit, require
from ..registration.models import Patient, Visit
from ..registration.service import age_years
from . import clinical_rules as rules
from .models import (AllergyRecord, ClinicalNote, Diagnosis, Icd10, LabOrder, MedicationOrder,
                     NoteAddendum, Vitals)

router = APIRouter(prefix="/ehr", tags=["ehr"])
CLINICAL = ("nurse", "doctor")
SEVERITIES = ("mild", "moderate", "severe", "life_threatening")
CLOSED = ("completed", "abandoned")


def _visit(db: Session, staff: Staff, visit_id: str) -> Visit:
    v = db.get(Visit, visit_id)
    if not v or v.facility_id != staff.facility_id:
        raise HTTPException(404, "Visit not found")
    return v


def _accept_scribe(db, session_id, staff, visit: Visit):
    if session_id:
        from ..scribe import service as scribe_service
        if not scribe_service.mark_accepted(db, session_id, staff, visit.id):
            raise HTTPException(422, "That dictation draft does not belong to this visit")


# ------------------------------------------------------------------ reference data
@router.get("/icd10")
def icd10_search(q: str = "", staff: Staff = Depends(require(*CLINICAL)), db: Session = Depends(get_db)):
    q = q.strip().lower()
    stmt = select(Icd10)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Icd10.code.ilike(like), Icd10.description.ilike(like), Icd10.keywords.ilike(like)))
    return [{"code": r.code, "description": r.description} for r in db.scalars(stmt.limit(15)).all()]


@router.get("/templates")
def templates(staff: Staff = Depends(require("doctor"))):
    return {k: v for k, v in rules.TEMPLATES.items()}


# ------------------------------------------------------------------ chart
@router.get("/patients/{patient_id}/chart")
def chart(patient_id: str, staff: Staff = Depends(require(*CLINICAL)), db: Session = Depends(get_db)):
    p = db.get(Patient, patient_id)
    if not p or p.facility_id != staff.facility_id:
        raise HTTPException(404, "Patient not found")
    allergies = db.scalars(select(AllergyRecord).where(AllergyRecord.patient_id == p.id)).all()
    dx = db.scalars(select(Diagnosis).where(Diagnosis.patient_id == p.id).order_by(Diagnosis.diagnosed_at.desc())).all()
    chronic_codes = {"I10", "E11.9", "J45.9", "B20", "D57.0", "A15.9"}
    problems, seen = [], set()
    for d in dx:
        if d.icd10_code in chronic_codes and d.icd10_code not in seen:
            seen.add(d.icd10_code)
            problems.append({"code": d.icd10_code, "name": d.icd10_description, "since": d.diagnosed_at.date().isoformat()})
    vit = db.scalars(select(Vitals).where(Vitals.patient_id == p.id).order_by(Vitals.recorded_at.desc()).limit(5)).all()
    history = db.scalars(select(ClinicalNote).where(ClinicalNote.patient_id == p.id, ClinicalNote.status == "signed")
                         .order_by(ClinicalNote.signed_at.desc()).limit(5)).all()
    audit(db, staff, "view", "chart", p.id, p.id)
    db.commit()
    return {
        "patient": {"id": p.id, "name": f"{p.surname} {p.first_name}", "patient_number": p.patient_number,
                    "age": age_years(p.date_of_birth), "gender": p.gender, "blood_group": p.blood_group,
                    "has_photo": bool(p.photo_path)},
        "alerts": [{"type": "allergy", "text": f"{a.allergen_name}" + (f" — {a.reaction}" if a.reaction else ""),
                    "severity": a.severity} for a in allergies]
                  + [{"type": "chronic", "text": f"{x['name']} (since {x['since']})", "severity": "info"} for x in problems],
        "allergies": [{"id": a.id, "name": a.allergen_name, "drug_class": a.drug_class,
                       "reaction": a.reaction, "severity": a.severity} for a in allergies],
        "recent_vitals": [_vitals_view(v) for v in vit],
        "history": [{"date": n.signed_at.date().isoformat(), "assessment": n.assessment[:140]} for n in history],
    }


# ------------------------------------------------------------------ allergies
class AllergyIn(BaseModel):
    allergen_name: str
    reaction: str | None = None
    severity: str = "moderate"


@router.post("/patients/{patient_id}/allergies", status_code=201)
def add_allergy(patient_id: str, body: AllergyIn, staff: Staff = Depends(require(*CLINICAL)),
                db: Session = Depends(get_db)):
    p = db.get(Patient, patient_id)
    if not p or p.facility_id != staff.facility_id:
        raise HTTPException(404, "Patient not found")
    if body.severity not in SEVERITIES:
        raise HTTPException(422, f"severity must be one of {', '.join(SEVERITIES)}")
    if not body.allergen_name.strip():
        raise HTTPException(422, "allergen_name is required")
    a = AllergyRecord(patient_id=p.id, allergen_name=body.allergen_name, reaction=body.reaction,
                      severity=body.severity, recorded_by=staff.id,
                      drug_class=rules.drug_class_of(body.allergen_name) or body.allergen_name.lower())
    db.add(a)
    db.flush()
    audit(db, staff, "create", "allergy", a.id, p.id)
    db.commit()
    return {"id": a.id}


# ------------------------------------------------------------------ triage / vitals
class TriageIn(BaseModel):
    bp_systolic: int | None = Field(None, ge=30, le=300)
    bp_diastolic: int | None = Field(None, ge=20, le=200)
    pulse_rate: int | None = Field(None, ge=20, le=250)
    respiratory_rate: int | None = Field(None, ge=4, le=80)
    temperature: float | None = Field(None, ge=30, le=45)
    spo2: int | None = Field(None, ge=40, le=100)
    weight_kg: float | None = Field(None, gt=0, le=400)
    height_cm: float | None = Field(None, gt=20, le=260)
    pain_score: int | None = Field(None, ge=0, le=10)
    chief_complaint: str | None = None
    triage_priority: str = "NORMAL"
    scribe_session_id: str | None = None


def _vitals_view(v: Vitals) -> dict:
    return {"id": v.id, "at": v.recorded_at.isoformat(), "bp": f"{v.bp_systolic}/{v.bp_diastolic}" if v.bp_systolic else None,
            "pulse_rate": v.pulse_rate, "respiratory_rate": v.respiratory_rate, "temperature": v.temperature,
            "spo2": v.spo2, "weight_kg": v.weight_kg, "height_cm": v.height_cm, "bmi": v.bmi,
            "pain_score": v.pain_score, "chief_complaint": v.chief_complaint,
            "triage_priority": v.triage_priority, "flags": v.flags or [], "source": v.source}


@router.post("/visits/{visit_id}/triage", status_code=201)
def save_triage(visit_id: str, body: TriageIn, staff: Staff = Depends(require("nurse", "doctor")),
                db: Session = Depends(get_db)):
    v = _visit(db, staff, visit_id)
    if v.status in CLOSED:
        raise HTTPException(409, f"This visit is {v.status}; check the patient in again")
    if body.triage_priority not in ("NORMAL", "HIGH", "EMERGENCY"):
        raise HTTPException(422, "triage_priority must be NORMAL, HIGH or EMERGENCY")
    data = body.model_dump()
    flags, critical = rules.flag_vitals(data)
    priority = "EMERGENCY" if critical else body.triage_priority   # critical values force emergency
    first = db.scalar(select(Vitals).where(Vitals.visit_id == v.id)) is None
    vit = Vitals(visit_id=v.id, patient_id=v.patient_id, recorded_by=staff.id, flags=flags,
                 triage_priority=priority, bmi=rules.bmi(body.weight_kg, body.height_cm),
                 source="ai_scribe" if body.scribe_session_id else "manual",
                 **{k: data[k] for k in ("bp_systolic", "bp_diastolic", "pulse_rate", "respiratory_rate", "temperature",
                                         "spo2", "weight_kg", "height_cm", "pain_score", "chief_complaint")})
    db.add(vit)
    db.flush()
    _accept_scribe(db, body.scribe_session_id, staff, v)
    if critical:
        publish(db, "CriticalVitals", {"visit_id": v.id, "flags": [f for f in flags if f["level"] == "critical"]},
                v.facility_id, room="queue")
    if first:
        v.status = "in_progress"
        publish(db, "TriageCompleted", {"visit_id": v.id, "triage_priority": priority}, v.facility_id, room="queue")
    audit(db, staff, "create", "vitals", vit.id, v.patient_id)
    db.commit()
    return _vitals_view(vit)


# ------------------------------------------------------------------ visit workspace
def _note_view(db: Session, n: ClinicalNote | None):
    if not n:
        return None
    dx = db.scalars(select(Diagnosis).where(Diagnosis.note_id == n.id)).all()
    adds = db.scalars(select(NoteAddendum).where(NoteAddendum.note_id == n.id).order_by(NoteAddendum.added_at)).all()
    return {"id": n.id, "status": n.status, "subjective": n.subjective, "objective": n.objective,
            "assessment": n.assessment, "plan": n.plan, "template_used": n.template_used, "source": n.source,
            "signed_at": n.signed_at.isoformat() if n.signed_at else None, "content_hash": n.content_hash,
            "diagnoses": [{"code": d.icd10_code, "description": d.icd10_description, "type": d.diagnosis_type} for d in dx],
            "addenda": [{"text": a.text, "reason": a.reason, "at": a.added_at.isoformat()} for a in adds]}


@router.get("/visits/{visit_id}")
def visit_workspace(visit_id: str, staff: Staff = Depends(require(*CLINICAL)), db: Session = Depends(get_db)):
    v = _visit(db, staff, visit_id)
    vit = db.scalar(select(Vitals).where(Vitals.visit_id == v.id).order_by(Vitals.recorded_at.desc()))
    note = db.scalar(select(ClinicalNote).where(ClinicalNote.visit_id == v.id, ClinicalNote.note_type == "soap"))
    labs = db.scalars(select(LabOrder).where(LabOrder.visit_id == v.id)).all()
    meds = db.scalars(select(MedicationOrder).where(MedicationOrder.visit_id == v.id)).all()
    audit(db, staff, "view", "visit", v.id, v.patient_id)
    db.commit()
    return {"visit": {"id": v.id, "type": v.visit_type, "status": v.status, "patient_id": v.patient_id},
            "vitals": _vitals_view(vit) if vit else None, "note": _note_view(db, note),
            "lab_orders": [{"id": l.id, "test_code": l.test_code, "test_name": l.test_name,
                            "priority": l.priority, "status": l.status} for l in labs],
            "prescriptions": [{"id": m.id, "drug_name": m.drug_name, "dose": m.dose, "frequency": m.frequency,
                               "duration_days": m.duration_days, "status": m.status,
                               "allergy_override_reason": m.allergy_override_reason} for m in meds]}


class NoteIn(BaseModel):
    subjective: str = ""
    objective: str = ""
    assessment: str = ""
    plan: str = ""
    diagnoses: list[str] = []      # ICD-10 codes
    template_used: str | None = None
    scribe_session_id: str | None = None


def _editable_note(db: Session, v: Visit, staff: Staff) -> ClinicalNote | None:
    n = db.scalar(select(ClinicalNote).where(ClinicalNote.visit_id == v.id, ClinicalNote.note_type == "soap"))
    if n and n.status == "signed":
        raise HTTPException(409, "This note is signed and immutable. Add an addendum instead.")
    return n


@router.put("/visits/{visit_id}/note")
def save_note(visit_id: str, body: NoteIn, staff: Staff = Depends(require("doctor")), db: Session = Depends(get_db)):
    v = _visit(db, staff, visit_id)
    n = _editable_note(db, v, staff)
    if not n:
        n = ClinicalNote(visit_id=v.id, patient_id=v.patient_id, authored_by=staff.id)
        db.add(n)
        db.flush()
    n.subjective, n.objective, n.assessment, n.plan = body.subjective, body.objective, body.assessment, body.plan
    n.template_used = body.template_used
    if body.scribe_session_id:
        n.source, n.scribe_session_id = "ai_scribe", body.scribe_session_id
        _accept_scribe(db, body.scribe_session_id, staff, v)
    for d in db.scalars(select(Diagnosis).where(Diagnosis.note_id == n.id)).all():
        db.delete(d)
    for i, code in enumerate(dict.fromkeys(body.diagnoses)):
        ref = db.get(Icd10, code)
        if not ref:
            raise HTTPException(422, f"Unknown ICD-10 code {code}")
        db.add(Diagnosis(note_id=n.id, visit_id=v.id, patient_id=v.patient_id, icd10_code=ref.code,
                         icd10_description=ref.description, diagnosis_type="primary" if i == 0 else "secondary",
                         diagnosed_by=staff.id))
    audit(db, staff, "edit", "clinical_note", n.id, v.patient_id)
    db.commit()
    return _note_view(db, n)


class LabIn(BaseModel):
    test_code: str = Field(min_length=1, max_length=20)
    test_name: str = Field(min_length=1, max_length=100)
    priority: str = "routine"


@router.post("/visits/{visit_id}/lab-orders", status_code=201)
def add_lab(visit_id: str, body: LabIn, staff: Staff = Depends(require("doctor")), db: Session = Depends(get_db)):
    v = _visit(db, staff, visit_id)
    if body.priority not in ("routine", "urgent", "stat"):
        raise HTTPException(422, "priority must be routine, urgent or stat")
    _editable_note(db, v, staff)
    o = LabOrder(visit_id=v.id, patient_id=v.patient_id, ordered_by=staff.id, **body.model_dump())
    db.add(o)
    db.flush()
    audit(db, staff, "create", "lab_order", o.id, v.patient_id)
    db.commit()
    return {"id": o.id}


class RxIn(BaseModel):
    drug_name: str = Field(min_length=2, max_length=100)
    dose: str | None = None
    frequency: str | None = None
    duration_days: int | None = Field(None, ge=1, le=365)
    route: str = "oral"
    instructions: str | None = None
    allergy_override_reason: str | None = None


@router.post("/visits/{visit_id}/prescriptions", status_code=201)
def add_rx(visit_id: str, body: RxIn, staff: Staff = Depends(require("doctor")), db: Session = Depends(get_db)):
    v = _visit(db, staff, visit_id)
    _editable_note(db, v, staff)
    allergies = db.scalars(select(AllergyRecord).where(AllergyRecord.patient_id == v.patient_id)).all()
    hits = rules.allergy_conflicts(body.drug_name, allergies)
    if hits and not (body.allergy_override_reason or "").strip():
        # HARD BLOCK: cannot proceed without explicitly documenting clinical reasoning
        audit(db, staff, "allergy_block", "medication_order", None, v.patient_id, detail=body.drug_name)
        db.commit()
        raise HTTPException(409, {"code": "allergy_conflict",
                                  "message": f"Patient is allergic to {', '.join(h.allergen_name for h in hits)}. "
                                             "Choose an alternative or document your clinical reasoning to override.",
                                  "allergies": [{"name": h.allergen_name, "reaction": h.reaction, "severity": h.severity}
                                                for h in hits]})
    m = MedicationOrder(visit_id=v.id, patient_id=v.patient_id, ordered_by=staff.id,
                        **body.model_dump(exclude={"allergy_override_reason"}),
                        allergy_override_reason=body.allergy_override_reason if hits else None)
    db.add(m)
    db.flush()
    if hits:
        audit(db, staff, "allergy_override", "medication_order", m.id, v.patient_id, detail=body.allergy_override_reason)
    audit(db, staff, "create", "medication_order", m.id, v.patient_id)
    db.commit()
    return {"id": m.id, "allergy_overridden": bool(hits)}


@router.delete("/orders/{kind}/{order_id}")
def delete_order(kind: str, order_id: str, staff: Staff = Depends(require("doctor")), db: Session = Depends(get_db)):
    model = {"lab": LabOrder, "rx": MedicationOrder}.get(kind)
    o = db.get(model, order_id) if model else None
    if not o:
        raise HTTPException(404, "Order not found")
    _visit(db, staff, o.visit_id)
    if o.status != "ordered":
        raise HTTPException(409, "Order was already sent")
    db.delete(o)
    audit(db, staff, "delete", f"{kind}_order", order_id, o.patient_id)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ sign / addendum
@router.post("/notes/{note_id}/sign")
def sign_note(note_id: str, staff: Staff = Depends(require("doctor")), db: Session = Depends(get_db)):
    n = db.get(ClinicalNote, note_id)
    if not n:
        raise HTTPException(404, "Note not found")
    v = _visit(db, staff, n.visit_id)
    if n.status == "signed":
        raise HTTPException(409, "Already signed")
    dx = db.scalars(select(Diagnosis).where(Diagnosis.note_id == n.id)).all()
    if not dx:
        raise HTTPException(422, "Add at least one ICD-10 diagnosis before signing (needed for HMO claims)")
    if not (n.subjective.strip() and n.assessment.strip()):
        raise HTTPException(422, "Subjective and Assessment are required")
    labs = db.scalars(select(LabOrder).where(LabOrder.visit_id == v.id, LabOrder.status == "ordered")).all()
    meds = db.scalars(select(MedicationOrder).where(MedicationOrder.visit_id == v.id, MedicationOrder.status == "ordered")).all()
    blob = json.dumps({"s": n.subjective, "o": n.objective, "a": n.assessment, "p": n.plan,
                       "dx": sorted(d.icd10_code for d in dx), "labs": sorted(l.test_code for l in labs),
                       "rx": sorted(m.drug_name for m in meds), "by": staff.id}, sort_keys=True)
    n.status, n.signed_by, n.signed_at = "signed", staff.id, utcnow()
    n.content_hash = hashlib.sha256(blob.encode()).hexdigest()
    for l in labs:
        l.status = "sent"
    for m in meds:
        m.status = "sent"
    if labs:
        publish(db, "LabOrdered", {"visit_id": v.id, "patient_id": v.patient_id,
                                   "tests": [l.test_code for l in labs], "summary": ", ".join(l.test_name for l in labs)},
                v.facility_id)
    if meds:
        publish(db, "Prescribed", {"visit_id": v.id, "patient_id": v.patient_id,
                                   "drugs": [m.drug_name for m in meds], "summary": ", ".join(m.drug_name for m in meds)},
                v.facility_id)
    publish(db, "NoteSigned", {"visit_id": v.id, "patient_id": v.patient_id, "note_id": n.id, "note_type": n.note_type,
                               "icd10": [d.icd10_code for d in dx], "source": n.source}, v.facility_id, room="queue")
    audit(db, staff, "sign", "clinical_note", n.id, v.patient_id, detail=f"hash={n.content_hash[:12]} source={n.source}")
    db.commit()
    return _note_view(db, n)


class AddendumIn(BaseModel):
    text: str = Field(min_length=3)
    reason: str | None = None


@router.post("/notes/{note_id}/addendum", status_code=201)
def addendum(note_id: str, body: AddendumIn, staff: Staff = Depends(require("doctor")), db: Session = Depends(get_db)):
    n = db.get(ClinicalNote, note_id)
    if not n:
        raise HTTPException(404, "Note not found")
    _visit(db, staff, n.visit_id)
    if n.status != "signed":
        raise HTTPException(409, "Only signed notes take addenda; edit the draft instead")
    db.add(NoteAddendum(note_id=n.id, text=body.text, reason=body.reason, added_by=staff.id))
    audit(db, staff, "addendum", "clinical_note", n.id, n.patient_id)
    db.commit()
    return _note_view(db, n)
