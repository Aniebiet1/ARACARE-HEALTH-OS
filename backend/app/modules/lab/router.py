"""Lab and pharmacy worklists: the receiving end of the doctor's orders.

Results and dispensing publish domain events (LabResulted, Dispensed); AraPulse turns them into alerts for
the ordering doctor. Neither module calls the other."""
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import get_db, utcnow
from ...events import publish
from ..core.models import Staff
from ..core.security import audit, require
from ..ehr.models import LabOrder, MedicationOrder
from ..registration.models import Patient, Visit
from ..registration.service import age_years

router = APIRouter(tags=["lab"])
pharmacy = APIRouter(prefix="/pharmacy", tags=["pharmacy"])
PRIORITY_RANK = {"stat": 0, "urgent": 1, "routine": 2}
FLAGS = ("normal", "abnormal", "critical")
DONE_LIMIT = 50


def _iso(t):
    return t.isoformat() if t else None


def _patient(p: Patient) -> dict:
    return {"id": p.id, "name": f"{p.surname} {p.first_name}", "patient_number": p.patient_number,
            "age": age_years(p.date_of_birth), "gender": p.gender}


def _people(db: Session, ids) -> dict[str, Staff]:
    return {s.id: s for s in db.scalars(select(Staff).where(Staff.id.in_(set(ids)))).all()}


def _by(s: Staff | None) -> dict | None:
    return {"id": s.id, "name": s.full_name} if s else None


def _check(status: str):
    if status not in ("pending", "done"):
        raise HTTPException(422, "status must be pending or done")


# ------------------------------------------------------------------ lab
def _lab_view(o: LabOrder, p: Patient, people: dict) -> dict:
    return {"id": o.id, "test_code": o.test_code, "test_name": o.test_name, "priority": o.priority,
            "status": o.status, "ordered_at": _iso(o.ordered_at), "started_at": _iso(o.started_at),
            "resulted_at": _iso(o.resulted_at), "result_text": o.result_text, "result_flag": o.result_flag,
            "resulted_by": _by(people.get(o.resulted_by)), "patient": _patient(p),
            "ordered_by": _by(people.get(o.ordered_by)), "visit_id": o.visit_id}


@router.get("/lab/worklist")
def lab_worklist(status: str = "pending", staff: Staff = Depends(require("lab", "admin")),
                 db: Session = Depends(get_db)):
    """pending: sent by a signed note or already started; STAT first, then urgent, then oldest.
    done: the last 50 results."""
    _check(status)
    q = select(LabOrder, Patient).join(Visit, Visit.id == LabOrder.visit_id) \
        .join(Patient, Patient.id == LabOrder.patient_id).where(Visit.facility_id == staff.facility_id)
    if status == "pending":
        rows = db.execute(q.where(LabOrder.status.in_(("sent", "in_progress")))).all()
        rows.sort(key=lambda r: (PRIORITY_RANK.get(r[0].priority, 3), r[0].ordered_at))
    else:
        rows = db.execute(q.where(LabOrder.status == "resulted")
                          .order_by(LabOrder.resulted_at.desc()).limit(DONE_LIMIT)).all()
    people = _people(db, [x for o, _ in rows for x in (o.ordered_by, o.resulted_by) if x])
    audit(db, staff, "view", "lab_worklist", detail=f"{status}: {len(rows)}")
    db.commit()
    return [_lab_view(o, p, people) for o, p in rows]


def _lab_order(db: Session, staff: Staff, order_id: str) -> tuple[LabOrder, Visit]:
    o = db.get(LabOrder, order_id, with_for_update=True)
    v = db.get(Visit, o.visit_id) if o else None
    if not o or not v or v.facility_id != staff.facility_id:
        raise HTTPException(404, "Lab order not found")
    return o, v


def _lab_reply(db: Session, o: LabOrder) -> dict:
    people = _people(db, [x for x in (o.ordered_by, o.resulted_by) if x])
    return _lab_view(o, db.get(Patient, o.patient_id), people)


@router.post("/lab/orders/{order_id}/start")
def start_test(order_id: str, staff: Staff = Depends(require("lab")), db: Session = Depends(get_db)):
    o, v = _lab_order(db, staff, order_id)
    if o.status == "ordered":
        raise HTTPException(409, "This request has not been sent yet: the doctor still has to sign the note")
    if o.status != "sent":
        raise HTTPException(409, f"This test is already {o.status.replace('_', ' ')}")
    o.status, o.started_at = "in_progress", utcnow()
    audit(db, staff, "start", "lab_order", o.id, o.patient_id)
    publish(db, "LabStarted", {"lab_order_id": o.id, "visit_id": o.visit_id, "test_code": o.test_code},
            v.facility_id)
    db.commit()
    return _lab_reply(db, o)


class ResultIn(BaseModel):
    result_text: str = Field(min_length=1, max_length=4000)
    result_flag: str = "normal"


@router.post("/lab/orders/{order_id}/result")
def record_result(order_id: str, body: ResultIn, staff: Staff = Depends(require("lab")),
                  db: Session = Depends(get_db)):
    o, v = _lab_order(db, staff, order_id)
    if body.result_flag not in FLAGS:
        raise HTTPException(422, "result_flag must be normal, abnormal or critical")
    if not body.result_text.strip():
        raise HTTPException(422, "Enter the result before sending it")
    if o.status == "ordered":
        raise HTTPException(409, "This request has not been sent yet: the doctor still has to sign the note")
    if o.status == "resulted":
        raise HTTPException(409, "A result was already sent for this test. Ask the doctor to order a repeat.")
    now = utcnow()
    o.started_at = o.started_at or now
    o.status, o.result_text, o.result_flag = "resulted", body.result_text.strip(), body.result_flag
    o.resulted_by, o.resulted_at = staff.id, now
    audit(db, staff, "result", "lab_order", o.id, o.patient_id, detail=body.result_flag)
    # AraPulse turns this into an alert for the ordering doctor (critical: must be acknowledged, escalates)
    publish(db, "LabResulted", {"lab_order_id": o.id, "visit_id": o.visit_id, "patient_id": o.patient_id,
                                "ordered_by": o.ordered_by, "resulted_by": staff.id, "test_code": o.test_code,
                                "result_flag": o.result_flag}, v.facility_id)
    db.commit()
    return _lab_reply(db, o)


# ------------------------------------------------------------------ pharmacy
def _rx_item(m: MedicationOrder, people: dict) -> dict:
    return {"id": m.id, "drug_name": m.drug_name, "dose": m.dose, "frequency": m.frequency,
            "duration_days": m.duration_days, "route": m.route, "instructions": m.instructions, "status": m.status,
            "allergy_override_reason": m.allergy_override_reason, "ordered_at": _iso(m.ordered_at),
            "dispensed_at": _iso(m.dispensed_at), "dispensed_by": _by(people.get(m.dispensed_by))}


@pharmacy.get("/worklist")
def pharmacy_worklist(status: str = "pending", staff: Staff = Depends(require("pharmacy", "admin")),
                      db: Session = Depends(get_db)):
    """One card per patient visit. pending: prescriptions sent by a signed note (oldest first);
    done: the last 50 visits with something dispensed (newest first)."""
    _check(status)
    q = select(MedicationOrder, Patient).join(Visit, Visit.id == MedicationOrder.visit_id) \
        .join(Patient, Patient.id == MedicationOrder.patient_id).where(Visit.facility_id == staff.facility_id)
    if status == "pending":
        rows = db.execute(q.where(MedicationOrder.status == "sent").order_by(MedicationOrder.ordered_at)).all()
    else:
        rows = db.execute(q.where(MedicationOrder.status == "dispensed")
                          .order_by(MedicationOrder.dispensed_at.desc()).limit(DONE_LIMIT * 6)).all()
    groups: dict[str, dict] = {}
    items = defaultdict(list)
    for m, p in rows:
        if m.visit_id not in groups:
            if len(groups) >= DONE_LIMIT and status == "done":
                continue
            groups[m.visit_id] = {"visit_id": m.visit_id, "patient": _patient(p), "ordered_by_id": m.ordered_by,
                                  "ordered_at": m.ordered_at, "last_at": m.dispensed_at}
        g = groups[m.visit_id]
        g["ordered_at"] = min(g["ordered_at"], m.ordered_at)
        items[m.visit_id].append(m)
    people = _people(db, [m.ordered_by for m, _ in rows] + [m.dispensed_by for m, _ in rows if m.dispensed_by])
    audit(db, staff, "view", "pharmacy_worklist", detail=f"{status}: {len(groups)}")
    db.commit()
    return [{"visit_id": g["visit_id"], "patient": g["patient"], "ordered_by": _by(people.get(g["ordered_by_id"])),
             "ordered_at": _iso(g["ordered_at"]), "dispensed_at": _iso(g["last_at"]),
             "items": [_rx_item(m, people) for m in sorted(items[vid], key=lambda m: m.drug_name)]}
            for vid, g in groups.items()]


@pharmacy.post("/orders/{order_id}/dispense")
def dispense(order_id: str, staff: Staff = Depends(require("pharmacy")), db: Session = Depends(get_db)):
    m = db.get(MedicationOrder, order_id, with_for_update=True)
    v = db.get(Visit, m.visit_id) if m else None
    if not m or not v or v.facility_id != staff.facility_id:
        raise HTTPException(404, "Prescription not found")
    if m.status == "ordered":
        raise HTTPException(409, "This prescription has not been sent yet: the doctor still has to sign the note")
    if m.status == "dispensed":
        raise HTTPException(409, "Already dispensed")
    m.status, m.dispensed_by, m.dispensed_at = "dispensed", staff.id, utcnow()
    audit(db, staff, "dispense", "medication_order", m.id, m.patient_id, detail=m.drug_name)
    publish(db, "Dispensed", {"medication_order_id": m.id, "visit_id": m.visit_id, "patient_id": m.patient_id,
                              "ordered_by": m.ordered_by, "dispensed_by": staff.id, "drug_name": m.drug_name},
            v.facility_id)
    db.commit()
    return _rx_item(m, _people(db, [staff.id]))


router.include_router(pharmacy)
