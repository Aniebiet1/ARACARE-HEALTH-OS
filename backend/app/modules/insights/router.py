"""Admin Overview: the numbers behind the dashboard charts.

Bucketing by local day/hour is done in Python (portable across SQLite and PostgreSQL); every query is bounded
by the date range, so a few thousand visits a month stays fast."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import median

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db import TZ, get_db, local_day_start_utc, local_today, utcnow
from ..core.models import Department, Staff, Ward
from ..core.router import ROLES, department_names
from ..core.security import audit, require
from ..ehr.models import ClinicalNote, Diagnosis, LabOrder, Vitals
from ..queues.models import Ticket
from ..registration.models import Patient, Visit
from ..registration.service import age_years

router = APIRouter(tags=["insights"])
PRIORITIES = ("EMERGENCY", "HIGH", "NORMAL", "FOLLOW_UP")
AGE_BANDS = (("0-4", 0, 4), ("5-14", 5, 14), ("15-24", 15, 24), ("25-44", 25, 44), ("45-64", 45, 64),
             ("65+", 65, 999))
PENDING_LAB = ("sent", "in_progress")


def _local(ts: datetime) -> datetime:
    """Stored naive UTC -> facility local time."""
    return ts.replace(tzinfo=timezone.utc).astimezone(TZ)


def _mins(a: datetime, b: datetime) -> float:
    return (b - a).total_seconds() / 60


def _avg(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 1) if xs else None


def _critical(flags) -> bool:
    return any(isinstance(f, dict) and f.get("level") == "critical" for f in flags or [])


@router.get("/admin/analytics")
def analytics(days: int = Query(14, ge=7, le=90), admin: Staff = Depends(require("admin")),
              db: Session = Depends(get_db)):
    fid, today = admin.facility_id, local_today()
    first_day = today - timedelta(days=days - 1)
    start, today_start = local_day_start_utc(first_day), local_day_start_utc(today)
    day_keys = [first_day + timedelta(days=i) for i in range(days)]

    # ---- visits
    visits = db.execute(select(Visit.patient_id, Visit.visit_type, Visit.checked_in_at)
                        .where(Visit.facility_id == fid, Visit.checked_in_at >= start)).all()
    daily = {d: {"date": d.isoformat(), "visits": 0, "new_complaint": 0, "follow_up": 0, "emergency": 0,
                 "avg_wait_min": None, "critical_flags": 0, "notes_signed": 0} for d in day_keys}
    hours_today, hours_before = [0] * 24, [0] * 24
    for _, vtype, at in visits:
        loc = _local(at)
        row = daily.get(loc.date())
        if row is None:
            continue
        row["visits"] += 1
        if vtype in ("new_complaint", "follow_up", "emergency"):
            row[vtype] += 1
        (hours_today if loc.date() == today else hours_before)[loc.hour] += 1
    prev_days = days - 1

    # ---- queue tickets: wait = called - entered waiting, as on the Queues page (queues.service.stats)
    tickets = db.execute(select(Ticket.department, Ticket.day, Ticket.status, Ticket.entered_waiting_at,
                                Ticket.called_at).where(Ticket.facility_id == fid, Ticket.day >= first_day)).all()
    waits_by_day: dict = {d: [] for d in day_keys}
    today_t = {"TRIAGE": [], "OPD-GEN": []}
    for dept, day, status, waiting_at, called_at in tickets:
        if called_at and waiting_at and day in waits_by_day:
            waits_by_day[day].append(_mins(waiting_at, called_at))
        if day == today and dept in today_t:
            today_t[dept].append((status, waiting_at, called_at))
    for d in day_keys:
        daily[d]["avg_wait_min"] = _avg(waits_by_day[d])

    def done_waits(dept):
        return _avg([_mins(w, c) for s, w, c in today_t[dept] if s == "completed" and c and w])

    def count(dept, *statuses):
        return sum(s in statuses for s, _, _ in today_t[dept])

    # ---- vitals (no facility column: scoped through the visit)
    vit = db.execute(select(Vitals.recorded_at, Vitals.flags, Vitals.triage_priority)
                     .join(Visit, Visit.id == Vitals.visit_id)
                     .where(Visit.facility_id == fid, Vitals.recorded_at >= start)).all()
    mix = Counter()
    critical_today = 0
    for at, flags, prio in vit:
        mix[prio] += 1
        if _critical(flags):
            d = _local(at).date()
            if d in daily:
                daily[d]["critical_flags"] += 1
            critical_today += d == today

    for (at,) in db.execute(select(ClinicalNote.signed_at).join(Visit, Visit.id == ClinicalNote.visit_id)
                            .where(Visit.facility_id == fid, ClinicalNote.status == "signed",
                                   ClinicalNote.signed_at >= start)).all():
        d = _local(at).date()
        if d in daily:
            daily[d]["notes_signed"] += 1

    # ---- diagnoses
    n = func.count(Diagnosis.id)
    top_dx = db.execute(select(Diagnosis.icd10_code, func.max(Diagnosis.icd10_description), n)
                        .join(Visit, Visit.id == Diagnosis.visit_id)
                        .where(Visit.facility_id == fid, Diagnosis.diagnosed_at >= start)
                        .group_by(Diagnosis.icd10_code).order_by(n.desc(), Diagnosis.icd10_code).limit(8)).all()

    # ---- demographics of the patients seen in the range (each patient once)
    seen = select(Visit.patient_id).where(Visit.facility_id == fid, Visit.checked_in_at >= start).distinct()
    people = db.execute(select(Patient.gender, Patient.date_of_birth).where(Patient.id.in_(seen))).all()
    gender = Counter((g or "unknown").strip().capitalize() for g, _ in people)
    bands = Counter()
    for _, dob in people:
        if dob:
            a = age_years(dob, today)
            bands[next(label for label, lo, hi in AGE_BANDS if lo <= a <= hi)] += 1

    # ---- lab
    labs = db.execute(select(LabOrder.test_name, LabOrder.status, LabOrder.result_flag, LabOrder.ordered_at,
                             LabOrder.resulted_at).join(Visit, Visit.id == LabOrder.visit_id)
                      .where(Visit.facility_id == fid, LabOrder.ordered_at >= start)).all()
    resulted = [r for r in labs if r.status == "resulted"]
    turnaround = [_mins(r.ordered_at, r.resulted_at) for r in resulted if r.resulted_at and r.ordered_at]
    resulted_today = db.scalar(select(func.count(LabOrder.id)).join(Visit, Visit.id == LabOrder.visit_id)
                               .where(Visit.facility_id == fid, LabOrder.resulted_at >= today_start)) or 0

    # ---- staff and wards
    staff = db.execute(select(Staff.role, Staff.department_id, Staff.on_duty)
                       .where(Staff.facility_id == fid, Staff.is_active)).all()
    names = department_names(db, fid)
    roles = Counter(r for r, _, _ in staff)
    by_dept = Counter(names.get(d, "No department") for _, d, _ in staff)
    wards = db.execute(select(Ward.id, Ward.name, Ward.bed_count, Department.name)
                       .outerjoin(Department, Department.id == Ward.department_id)
                       .where(Ward.facility_id == fid, Ward.is_active).order_by(Ward.name)).all()

    audit(db, admin, "view", "analytics", detail=f"{days} days")
    db.commit()
    return {
        "generated_at": utcnow().isoformat(),
        "days": days,
        "today": {
            "checked_in": daily[today]["visits"],
            "waiting_triage": count("TRIAGE", "waiting", "called"),
            "waiting_doctor": count("OPD-GEN", "waiting", "called"),
            "in_consultation": count("OPD-GEN", "in_service"),
            "seen_by_doctor": count("OPD-GEN", "completed"),
            "avg_wait_triage_min": done_waits("TRIAGE"),
            "avg_wait_doctor_min": done_waits("OPD-GEN"),
            "critical_flags": critical_today,
            "labs_pending": sum(r.status in PENDING_LAB for r in labs),
            "labs_resulted_today": resulted_today,
            "staff_active": len(staff),
            "staff_on_duty": sum(bool(on) for _, _, on in staff),
        },
        "daily": [daily[d] for d in day_keys],
        "hourly_today": [{"hour": h, "arrivals": hours_today[h],
                          "typical": round(hours_before[h] / prev_days, 1) if prev_days else 0}
                         for h in range(24)],
        "triage_mix": [{"priority": p, "count": mix[p]} for p in PRIORITIES],
        "top_diagnoses": [{"code": c, "description": desc, "count": k} for c, desc, k in top_dx],
        "demographics": {
            "gender": [{"label": g, "count": k} for g, k in gender.most_common()],
            "age_bands": [{"label": label, "count": bands[label]} for label, _, _ in AGE_BANDS],
        },
        "lab": {
            "ordered": len(labs),
            "resulted": len(resulted),
            "pending": sum(r.status in PENDING_LAB for r in labs),
            "critical": sum(r.result_flag == "critical" for r in labs),
            "median_turnaround_min": round(median(turnaround), 1) if turnaround else None,
            "by_test": [{"test": t, "count": k} for t, k in Counter(r.test_name for r in labs).most_common(6)],
        },
        "staff": {
            "by_role": [{"role": r, "count": roles[r]} for r in ROLES],
            "by_department": [{"department": d, "count": k} for d, k in by_dept.most_common()],
        },
        "wards": [{"id": i, "name": nm, "bed_count": beds, "department_name": dn} for i, nm, beds, dn in wards],
    }
