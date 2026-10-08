"""AraPulse reactions to clinical events: orders become channel messages, results and dangers become alerts.
Nobody types these: every one is traceable to the action that caused it."""
from sqlalchemy import select

from ...events import subscribe
from ..core.models import Staff
from ..ehr.models import LabOrder, MedicationOrder
from ..registration.models import Patient, Visit
from . import service as svc


def _patient(db, patient_id) -> Patient | None:
    return db.get(Patient, patient_id) if patient_id else None


def _who(p: Patient | None) -> str:
    return f"{svc.patient_name(p)} ({p.patient_number})" if p else "a patient"


def _staff(db, staff_id) -> Staff | None:
    return db.get(Staff, staff_id) if staff_id else None


@subscribe("LabOrdered")
def on_lab_ordered(db, ev):
    """A request in #laboratory replaces the paper slip carried by a porter."""
    p = ev.payload
    ch = svc.channel_by_code(db, ev.facility_id, "LAB")
    if not ch:
        return
    orders = db.scalars(select(LabOrder).where(LabOrder.visit_id == p["visit_id"], LabOrder.status == "sent")).all()
    doc = _staff(db, orders[0].ordered_by) if orders else None
    urgent = any(o.priority in ("stat", "urgent") for o in orders)
    tests = ", ".join(f"{o.test_name}" + (f" ({o.priority.upper()})" if o.priority != "routine" else "")
                      for o in orders) or p.get("summary", "tests")
    svc.post(db, ch, f"New lab request: {tests} for {_who(_patient(db, p.get('patient_id')))}"
                     + (f", from {svc.doctor_title(doc)}." if doc else "."),
             kind="lab_order", priority="urgent" if urgent else "routine", patient_id=p.get("patient_id"),
             payload={"visit_id": p["visit_id"], "lab_order_ids": [o.id for o in orders],
                      "tests": p.get("tests", [])})


@subscribe("Prescribed")
def on_prescribed(db, ev):
    p = ev.payload
    ch = svc.channel_by_code(db, ev.facility_id, "PHARM", "PHARMACY")
    if not ch:
        return
    meds = db.scalars(select(MedicationOrder).where(MedicationOrder.visit_id == p["visit_id"],
                                                    MedicationOrder.status == "sent")).all()
    doc = _staff(db, meds[0].ordered_by) if meds else None
    override = any(m.allergy_override_reason for m in meds)
    svc.post(db, ch, f"New prescription for {_who(_patient(db, p.get('patient_id')))}: {p.get('summary', '')}"
                     + (f", from {svc.doctor_title(doc)}." if doc else ".")
                     + (" Includes an allergy override: check the reason before dispensing." if override else ""),
             kind="prescription", priority="urgent" if override else "routine", patient_id=p.get("patient_id"),
             payload={"visit_id": p["visit_id"], "medication_order_ids": [m.id for m in meds],
                      "drugs": p.get("drugs", [])})


@subscribe("CriticalVitals")
def on_critical_vitals(db, ev):
    """Danger values at triage reach every on-duty doctor at once; the first to acknowledge closes it for all."""
    p = ev.payload
    visit = db.get(Visit, p["visit_id"])
    if not visit:
        return
    pat = _patient(db, visit.patient_id)
    recipients = svc.doctors(db, ev.facility_id, on_duty=True) or svc.doctors(db, ev.facility_id)
    flags = "; ".join(f["label"] for f in p.get("flags", []))
    for d in recipients:
        svc.alert(db, d.id, ev.facility_id, "critical_vitals", f"Critical vitals: {_who(pat)}",
                  f"{flags}. Triage set the patient to EMERGENCY.", priority="critical", ack_required=True,
                  patient_id=visit.patient_id, visit_id=visit.id, ref_id=ev.id,
                  payload={"flags": p.get("flags", [])})


@subscribe("LabResulted")
def on_lab_resulted(db, ev):
    """The report goes straight to the doctor who asked for it. Critical values must be acknowledged."""
    p = ev.payload
    order = db.get(LabOrder, p["lab_order_id"])
    if not order:
        return
    pat = _patient(db, order.patient_id)
    flag = order.result_flag or "normal"
    doc = _staff(db, order.ordered_by)
    recipients = [doc] if doc and doc.is_active else (svc.doctors(db, ev.facility_id, on_duty=True)
                                                       or svc.doctors(db, ev.facility_id))
    kind = "lab_critical" if flag == "critical" else "lab_result"
    title = (f"CRITICAL: {order.test_name} for {_who(pat)}" if flag == "critical"
             else f"Result ready: {order.test_name} for {_who(pat)}")
    for d in recipients:
        svc.alert(db, d.id, ev.facility_id, kind, title, order.result_text or "",
                  priority={"critical": "critical", "abnormal": "urgent"}.get(flag, "routine"),
                  ack_required=flag == "critical", patient_id=order.patient_id, visit_id=order.visit_id,
                  ref_id=order.id, payload={"test_code": order.test_code, "test_name": order.test_name,
                                            "result_flag": flag, "resulted_by": p.get("resulted_by")})


@subscribe("Dispensed")
def on_dispensed(db, ev):
    """Routine confirmation to the prescriber. Items dispensed one by one fold into one open alert per visit."""
    p = ev.payload
    m = db.get(MedicationOrder, p["medication_order_id"])
    if not m:
        return
    doc = _staff(db, m.ordered_by)
    if not doc or not doc.is_active:
        return
    pat = _patient(db, m.patient_id)
    open_one = db.scalar(select(svc.PulseAlert).where(
        svc.PulseAlert.recipient_id == doc.id, svc.PulseAlert.kind == "dispensed",
        svc.PulseAlert.ref_id == m.visit_id, svc.PulseAlert.seen_at.is_(None), svc.PulseAlert.acked_at.is_(None)))
    if open_one:
        drugs = list((open_one.payload or {}).get("drugs", [])) + [m.drug_name]
        open_one.payload = {**(open_one.payload or {}), "drugs": drugs}
        open_one.body = "Dispensed: " + ", ".join(drugs) + "."
        open_one.created_at = svc.utcnow()
        svc.notify(db, f"staff:{doc.id}")
        return
    svc.alert(db, doc.id, ev.facility_id, "dispensed", f"Medicines dispensed to {_who(pat)}",
              f"Dispensed: {m.drug_name}.", patient_id=m.patient_id, visit_id=m.visit_id, ref_id=m.visit_id,
              payload={"drugs": [m.drug_name], "dispensed_by": p.get("dispensed_by")})
