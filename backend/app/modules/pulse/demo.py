"""AraPulse demo content, called at the end of mock-data generation: `fill(db, facility)`.

Writes channels, a believable few days of cross-department talk (A&E, Laboratory, Pharmacy, wards), resolved
Pulse Codes over the last 14 days with realistic response times, one live page, and lab-result alerts for the
demo doctor ("doctor") built from the lab orders already in the database.

Safe to run again: it clears this facility's AraPulse messages, alerts and pages first (channels are kept).
Works with no departments, wards or patients: it simply writes less."""
import logging
import random
from datetime import timedelta

from sqlalchemy import delete, select

from ...db import uid, utcnow
from ..core.models import Department, Facility, Staff, Ward
from ..ehr.models import LabOrder, MedicationOrder, Vitals
from ..registration.models import Patient, Visit
from . import service as svc
from .models import PulseAlert, PulseChannel, PulseMessage, PulsePage, PulsePageTarget, PulseRead

log = logging.getLogger("aracare.pulse.demo")

# (department finder, sender role, text, hours ago, attach a patient?, priority)
SCRIPT = [
    ("broadcast", "admin", "Reminder: fire drill on Friday at 11am. Please make sure every ward knows the "
                           "assembly point by the car park.", 50, False, "routine"),
    ("pharmacy", "pharmacy", "Heads up: Artesunate injection is out of stock until Thursday. For severe malaria "
                             "please use IM Artemether for now.", 31, False, "urgent"),
    ("pharmacy", "doctor", "Noted, thanks. Is Ceftriaxone 1g still available?", 30.8, False, "routine"),
    ("pharmacy", "pharmacy", "Yes, plenty in stock.", 30.7, False, "routine"),
    ("emergency", "nurse", "Two road traffic casualties coming in from Ikorodu Road in about 10 minutes. "
                           "Resus bay is being set up.", 26, False, "urgent"),
    ("emergency", "doctor", "Coming down now. Please have two large-bore IV lines and O-negative ready.", 25.9,
     False, "urgent"),
    ("emergency", "lab", "Lab here: we're keeping a crossmatch slot open for A&E until they're stable.", 25.8,
     False, "routine"),
    ("broadcast", "admin", "HMO claims need every note from last week signed by Monday. Thank you all!", 20,
     False, "routine"),
    ("ward", "nurse", "BP 190/110 after evening meds, complaining of headache. Can a doctor review?", 7, True,
     "urgent"),
    ("ward", "doctor", "On my way. Repeat the BP in 15 minutes and hold the next dose until I see her.", 6.9, True,
     "routine"),
    ("laboratory", "doctor", "Please run the PCV for this patient first, she looks very pale.", 5, True, "urgent"),
    ("laboratory", "lab", "Sample received. Result in about 20 minutes.", 4.9, True, "routine"),
    ("laboratory", "nurse", "Do we have malaria RDT kits? Triage used the last one this morning.", 3, False,
     "routine"),
    ("laboratory", "lab", "Two boxes came in today. Sending one to triage with the porter now.", 2.9, False,
     "routine"),
    ("pharmacy", "doctor", "Please hold the Augmentin for this patient: penicillin allergy just reported. "
                           "New prescription coming.", 2, True, "urgent"),
    ("pharmacy", "pharmacy", "Held. Waiting for the new prescription.", 1.9, True, "routine"),
    ("emergency", "nurse", "Resus bay is clear and restocked.", 0.8, False, "routine"),
]

OUTCOMES = {
    "code_blue": ["ROSC after 3 cycles of CPR, moved to ICU", "Stabilised on oxygen and IV fluids; family informed"],
    "rapid_response": ["IV fluids and antibiotics started, sepsis bundle done", "Hypoglycaemia corrected with IV dextrose"],
    "urgent_review": ["Reviewed: switched to IV antibiotics", "Reviewed: analgesia adjusted, observe 4-hourly"],
    "obstetric": ["PPH controlled with oxytocin and uterine massage", "Emergency C-section: mother and baby stable"],
    "trauma": ["Splinted and sent for X-ray; orthopaedics informed", "Wound sutured, tetanus toxoid given"],
}

RESULTS = {   # test code -> [(result text, flag)]
    "LAB-MAL": [("Malaria RDT: POSITIVE (P. falciparum)", "abnormal"), ("Malaria RDT: negative", "normal")],
    "LAB-MP": [("Malaria parasites seen ++ (P. falciparum)", "abnormal")],
    "LAB-FBC": [("Hb 12.4 g/dL, WBC 6.9 x10^9/L, Plt 243 x10^9/L", "normal"),
                ("Hb 9.1 g/dL, WBC 14.2 x10^9/L (neutrophilia), Plt 180", "abnormal")],
    "LAB-PCV": [("PCV 17%", "critical"), ("PCV 34%", "normal")],
    "LAB-EUC": [("Na 136, K 6.8 mmol/L, Urea 18.2, Cr 412 umol/L", "critical"),
                ("Na 139, K 4.1, Urea 4.6, Cr 88 umol/L", "normal")],
    "LAB-FBS": [("Fasting blood sugar 6.1 mmol/L", "abnormal"), ("Fasting blood sugar 4.9 mmol/L", "normal")],
    "LAB-HBA1C": [("HbA1c 8.9%", "abnormal")],
    "LAB-TYP": [("Widal: O 1:80, H 1:80 (not significant)", "normal")],
    "LAB-UA": [("Urinalysis: leucocytes ++, nitrites +", "abnormal"), ("Urinalysis: normal", "normal")],
    "LAB-LIP": [("Total cholesterol 6.2 mmol/L, LDL 4.1", "abnormal")],
}


def _find(depts: list[Department], codes: tuple[str, ...], words: tuple[str, ...], kind: str | None = None):
    for d in depts:
        if d.code.upper() in codes:
            return d
    for d in depts:
        if any(w in d.name.lower() for w in words) or (kind and d.kind == kind):
            return d
    return None


def _wipe(db, fid: str) -> None:
    pages = select(PulsePage.id).where(PulsePage.facility_id == fid)
    chans = select(PulseChannel.id).where(PulseChannel.facility_id == fid)
    db.execute(delete(PulsePageTarget).where(PulsePageTarget.page_id.in_(pages)))
    db.execute(delete(PulsePage).where(PulsePage.facility_id == fid))
    db.execute(delete(PulseAlert).where(PulseAlert.facility_id == fid))
    db.execute(delete(PulseMessage).where(PulseMessage.facility_id == fid))
    db.execute(delete(PulseRead).where(PulseRead.channel_id.in_(chans)))
    db.execute(delete(PulseChannel).where(PulseChannel.facility_id == fid, PulseChannel.kind == "direct"))
    db.flush()


def fill(db, facility: Facility, seed: int = 2026) -> dict:
    r = random.Random(seed)
    fid, now = facility.id, utcnow()
    _wipe(db, fid)
    svc.ensure_channels(db, fid)
    counts = {"messages": 0, "pages": 0, "alerts": 0}

    staff = db.scalars(select(Staff).where(Staff.facility_id == fid, Staff.is_active).order_by(Staff.username)).all()
    by_role: dict[str, list[Staff]] = {}
    for s in staff:
        by_role.setdefault(s.role, []).append(s)
    doctor = next((s for s in staff if s.username == "doctor"), (by_role.get("doctor") or [None])[0])
    nurse = next((s for s in staff if s.username == "nurse"), (by_role.get("nurse") or [None])[0])

    def person(role):
        if role == "doctor" and doctor:
            return doctor if r.random() < 0.6 else r.choice(by_role["doctor"])
        return r.choice(by_role[role]) if by_role.get(role) else None

    depts = db.scalars(select(Department).where(Department.facility_id == fid, Department.is_active)).all()
    found = {"emergency": _find(depts, svc.EMERGENCY_CODES, ("emergency", "a&e", "casualty")),
             "laboratory": _find(depts, ("LAB",), ("laborator",)),
             "pharmacy": _find(depts, ("PHARM", "PHARMACY"), ("pharmac",)),
             "ward": _find(depts, ("MED", "IM", "MMW", "FMW"), ("medicine", "medical"), kind="ward")}
    channels = {k: svc.department_channel(db, fid, d.id) if d else None for k, d in found.items()}
    channels["broadcast"] = svc.broadcast_channel(db, fid)

    recent = db.scalars(select(Patient).join(Visit, Visit.patient_id == Patient.id)
                        .where(Visit.facility_id == fid, Visit.checked_in_at >= now - timedelta(days=3))
                        .order_by(Visit.checked_in_at.desc()).limit(40)).all()
    recent = list(dict.fromkeys(recent))

    # ---- conversations
    for where, role, text, hours, with_patient, priority in SCRIPT:
        ch, sender = channels.get(where), person(role)
        if not ch or not sender:
            continue
        p = r.choice(recent) if with_patient and recent else None
        svc.post(db, ch, text, kind="text", sender=sender, priority=priority, patient_id=p.id if p else None,
                 at=now - timedelta(hours=hours, minutes=r.uniform(0, 4)))
        counts["messages"] += 1
    if doctor and nurse:
        dm = svc.direct_channel(db, nurse, doctor)
        p = recent[0] if recent else None
        for sender, text, mins in ((nurse, "The patient in bay 2 is asking about her results. Can you see her "
                                           "before you leave?", 70),
                                   (doctor, "Yes, after this patient. About 15 minutes.", 66)):
            svc.post(db, dm, text, kind="text", sender=sender, patient_id=p.id if p and sender is nurse else None,
                     at=now - timedelta(minutes=mins))
            counts["messages"] += 1

    # recent lab requests, as the live system posts them on signing
    lab_ch = channels.get("laboratory")
    if lab_ch:
        sent = db.execute(select(LabOrder, Patient).join(Patient, Patient.id == LabOrder.patient_id)
                          .join(Visit, Visit.id == LabOrder.visit_id)
                          .where(Visit.facility_id == fid, LabOrder.status == "sent")
                          .order_by(LabOrder.ordered_at.desc()).limit(4)).all()
        names = {s.id: s for s in staff}
        for o, p in reversed(sent):
            doc = names.get(o.ordered_by)
            svc.post(db, lab_ch, f"New lab request: {o.test_name}"
                                 + (f" ({o.priority.upper()})" if o.priority != "routine" else "")
                                 + f" for {svc.patient_name(p)} ({p.patient_number})"
                                 + (f", from {svc.doctor_title(doc)}." if doc else "."),
                     kind="lab_order", priority="urgent" if o.priority != "routine" else "routine", patient_id=p.id,
                     payload={"visit_id": o.visit_id, "lab_order_ids": [o.id], "tests": [o.test_code]},
                     at=min(now, o.ordered_at + timedelta(minutes=8)))
            counts["messages"] += 1

    # ---- Pulse Codes
    wards = db.scalars(select(Ward).where(Ward.facility_id == fid, Ward.is_active).order_by(Ward.code)).all()
    doctors = by_role.get("doctor", [])
    raisers = by_role.get("nurse", []) or staff
    if wards and doctors and raisers:
        codes = ["code_blue", "rapid_response", "rapid_response", "urgent_review", "urgent_review", "obstetric",
                 "trauma", "rapid_response"]
        for i, code in enumerate(codes):
            created = now - timedelta(days=r.uniform(0.5, 13.5), minutes=r.uniform(0, 600))
            escalated = i == 3
            ack_s = r.uniform(150, 260) if escalated else r.triangular(25, 190, 70)
            page = _page(db, r, fid, code, r.choice(wards), r.choice(raisers), doctors, created,
                         p=r.choice(recent) if recent and r.random() < 0.6 else None)
            responder = r.choice(doctors)
            page.responder_id, page.acked_at = responder.id, created + timedelta(seconds=ack_s)
            page.eta_minutes = r.choice([1, 2, 3, 5])
            if i == 6:                                   # a false alarm, stood down
                page.status, page.resolved_at = "cancelled", page.acked_at + timedelta(minutes=2)
                page.outcome = "False alarm: patient was asleep, observations normal"
            else:
                page.status = "resolved"
                page.arrived_at = page.acked_at + timedelta(minutes=r.uniform(1.5, 6))
                page.resolved_at = page.arrived_at + timedelta(minutes=r.uniform(12, 55))
                page.outcome = r.choice(OUTCOMES[code])
            if escalated:
                page.escalation_level, page.escalated_at = 1, created + timedelta(seconds=120)
                svc.add_targets(db, page, doctors, 1, page.escalated_at)
            ch = db.get(PulseChannel, page.channel_id)
            svc.post(db, ch, f"{svc.doctor_title(responder)} is responding (answered in {round(ack_s)} s)",
                     kind="page", priority="urgent", patient_id=page.patient_id, at=page.acked_at,
                     payload={"page_id": page.id, "code": code, "status": "acknowledged"})
            svc.post(db, ch, f"{svc.label(code)} closed. Outcome: {page.outcome}" if page.status == "resolved"
                     else f"{svc.label(code)} stood down. {page.outcome}", kind="page", priority="routine",
                     patient_id=page.patient_id, at=page.resolved_at,
                     payload={"page_id": page.id, "code": code, "status": page.status})
            counts["pages"] += 1

        # one live page: answered by the demo doctor a minute ago, on the way
        # the patient with the most worrying vitals in the last two days
        flagged = db.execute(select(Vitals, Patient).join(Patient, Patient.id == Vitals.patient_id)
                             .where(Patient.facility_id == fid, Vitals.recorded_at >= now - timedelta(days=2))
                             .order_by(Vitals.recorded_at.desc()).limit(200)).all()
        live_p = max(flagged, key=lambda vp: (sum(f.get("level") == "critical" for f in vp[0].flags or []),
                                              len(vp[0].flags or [])), default=(None, None))[1]
        if doctor:
            created = now - timedelta(minutes=3)
            page = _page(db, r, fid, "rapid_response", wards[0], nurse or raisers[0], [doctor], created, p=live_p,
                         bed="3", note="Breathless and drowsy, observations getting worse. Please come now.")
            page.status, page.responder_id = "acknowledged", doctor.id
            page.acked_at, page.eta_minutes = created + timedelta(seconds=48), 4
            svc.post(db, db.get(PulseChannel, page.channel_id), f"{svc.doctor_title(doctor)} is responding, "
                     "there in 4 min. (answered in 48 s)", kind="page", priority="urgent", patient_id=page.patient_id,
                     at=page.acked_at, payload={"page_id": page.id, "code": page.code, "status": "acknowledged"})
            counts["pages"] += 1

    # ---- results for the demo doctor
    if doctor:
        counts["alerts"] += _lab_alerts(db, r, fid, doctor, now)
        counts["alerts"] += _dispensed_alert(db, fid, doctor, now)

    # everyone has read up to a few hours ago, so badges show only the latest traffic
    for ch in db.scalars(select(PulseChannel).where(PulseChannel.facility_id == fid,
                                                    PulseChannel.kind != "direct")).all():
        for s in staff:
            svc.mark_read(db, ch.id, s.id, now - timedelta(hours=4))
    db.flush()
    log.info("AraPulse demo: %s", counts)
    return counts


def _page(db, r, fid, code, ward, raiser, doctors, created, p=None, bed=None, note=None) -> PulsePage:
    ch = svc.page_channel(db, fid, ward.department_id)
    page = PulsePage(id=uid(), facility_id=fid, code=code, status="paging", ward_id=ward.id,
                     bed=bed or str(r.randint(1, max(ward.bed_count or 12, 1))), patient_id=p.id if p else None,
                     note=note, raised_by=raiser.id, channel_id=ch.id, created_at=created)
    db.add(page)
    db.flush()
    targets = [d for d in doctors if d.department_id == ward.department_id] or doctors[:3]
    svc.add_targets(db, page, targets, 0, created)
    svc.post(db, ch, f"{svc.label(code).upper()}: {svc.where(page, ward)}. Raised by {raiser.full_name}. Paging "
                     + ", ".join(svc.doctor_title(d) for d in targets) + "." + (f" Note: {note}" if note else ""),
             kind="page", priority="critical", patient_id=page.patient_id, at=created,
             payload={"page_id": page.id, "code": code, "status": "paging"})
    return page


def _result_alert(db, fid, doctor: Staff, o: LabOrder, p: Patient):
    flag = o.result_flag or "normal"
    critical = flag == "critical"
    return svc.alert(db, doctor.id, fid, "lab_critical" if critical else "lab_result",
                     (f"CRITICAL: {o.test_name} for " if critical else f"Result ready: {o.test_name} for ")
                     + f"{svc.patient_name(p)} ({p.patient_number})", o.result_text or "",
                     priority={"critical": "critical", "abnormal": "urgent"}.get(flag, "routine"),
                     ack_required=critical, patient_id=p.id, visit_id=o.visit_id, ref_id=o.id,
                     payload={"test_code": o.test_code, "test_name": o.test_name, "result_flag": flag},
                     at=o.resulted_at)


def _lab_alerts(db, r, fid, doctor: Staff, now) -> int:
    """Alerts for the doctor's latest results as they are in the database (older ones already dealt with),
    plus one fresh critical value still waiting for acknowledgement. Other pending tests stay on the lab's list."""
    base = (select(LabOrder, Patient).join(Patient, Patient.id == LabOrder.patient_id)
            .join(Visit, Visit.id == LabOrder.visit_id)
            .where(Visit.facility_id == fid, LabOrder.ordered_by == doctor.id))
    done = db.execute(base.where(LabOrder.status == "resulted", LabOrder.resulted_at.is_not(None))
                      .order_by(LabOrder.resulted_at.desc()).limit(5)).all()
    n = 0
    for i, (o, p) in enumerate(done):
        a = _result_alert(db, fid, doctor, o, p)
        if i >= 2 or a.priority == "critical":
            a.seen_at = a.created_at + timedelta(minutes=r.uniform(1, 6))
            a.acked_at, a.acked_by = a.seen_at, doctor.id
        elif i == 1:
            a.seen_at = a.created_at + timedelta(minutes=2)      # seen is not acknowledged
        n += 1
    crit_codes = [c for c, opts in RESULTS.items() if any(f == "critical" for _, f in opts)]
    row = db.execute(base.where(LabOrder.status.in_(("sent", "in_progress")), LabOrder.test_code.in_(crit_codes))
                     .order_by(LabOrder.ordered_at.desc()).limit(1)).first()
    if row:
        o, p = row
        o.result_text, o.result_flag = next((t, f) for t, f in RESULTS[o.test_code] if f == "critical")
        o.status, o.resulted_at = "resulted", now - timedelta(minutes=4)
        o.started_at = o.started_at or max(o.ordered_at, now - timedelta(minutes=35))
        o.resulted_by = db.scalar(select(Staff.id).where(Staff.facility_id == fid, Staff.role == "lab",
                                                         Staff.is_active).order_by(Staff.username))
        _result_alert(db, fid, doctor, o, p)
        n += 1
    return n


def _dispensed_alert(db, fid, doctor: Staff, now) -> int:
    row = db.execute(select(MedicationOrder, Patient).join(Patient, Patient.id == MedicationOrder.patient_id)
                     .join(Visit, Visit.id == MedicationOrder.visit_id)
                     .where(Visit.facility_id == fid, MedicationOrder.ordered_by == doctor.id,
                            MedicationOrder.status.in_(("sent", "dispensed")))
                     .order_by(MedicationOrder.ordered_at.desc()).limit(1)).first()
    if not row:
        return 0
    m, p = row
    meds = db.scalars(select(MedicationOrder).where(MedicationOrder.visit_id == m.visit_id,
                                                    MedicationOrder.status.in_(("sent", "dispensed")))).all()
    pharmacist = db.scalar(select(Staff.id).where(Staff.facility_id == fid, Staff.role == "pharmacy", Staff.is_active))
    at = min(now - timedelta(minutes=12), max(x.ordered_at for x in meds) + timedelta(minutes=25))
    for x in meds:
        x.status, x.dispensed_at, x.dispensed_by = "dispensed", x.dispensed_at or at, x.dispensed_by or pharmacist
    svc.alert(db, doctor.id, fid, "dispensed", f"Medicines dispensed to {svc.patient_name(p)} ({p.patient_number})",
              "Dispensed: " + ", ".join(x.drug_name for x in meds) + ".", patient_id=p.id, visit_id=m.visit_id,
              ref_id=m.visit_id, payload={"drugs": [x.drug_name for x in meds], "dispensed_by": pharmacist}, at=at)
    return 1


def reset(db) -> None:
    """Delete every AraPulse row (called by `mock_data --reset` before patients are deleted)."""
    for model in (PulsePageTarget, PulsePage, PulseAlert, PulseMessage, PulseRead, PulseChannel):
        db.execute(delete(model))
    db.flush()
