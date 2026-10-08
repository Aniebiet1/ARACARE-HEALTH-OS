"""AraPulse: department channels, personal alerts and emergency pages (Pulse Codes), with escalation.

Implements docs/internal_communications.md (see docs/arapulse.md). Other modules never call in here: they
publish domain events and handlers.py turns them into messages and alerts."""
import re
from datetime import timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ...config import settings
from ...db import insert_ignore, uid, utcnow
from ..core.models import Department, Staff, Ward
from ..ehr.models import AllergyRecord, Diagnosis, Vitals
from ..registration.models import Patient, Visit
from ..registration.service import age_years
from .models import PulseAlert, PulseChannel, PulseMessage, PulsePage, PulsePageTarget, PulseRead

# Pulse Codes, most severe first (that is also the order active pages are listed in)
CODES = {
    "code_blue": ("Code Blue", "Cardiac or respiratory arrest"),
    "obstetric": ("Obstetric Emergency", "Bleeding, eclampsia or a delivery going wrong"),
    "trauma": ("Trauma Call", "Major injury arriving or on the floor"),
    "rapid_response": ("Rapid Response", "Patient deteriorating: needs a doctor now"),
    "urgent_review": ("Urgent Review", "Needs a doctor soon, not an arrest"),
}
CODE_RANK = {c: i for i, c in enumerate(CODES)}
ACTIVE = ("paging", "acknowledged", "arrived")
PRIORITIES = ("routine", "urgent", "critical")
EMERGENCY_CODES = ("EMERG", "AE", "A&E", "ED", "EMERGENCY")
MAX_LEVEL = 2                      # 0 first wave, 1 every on-duty doctor, 2 every active doctor


# ------------------------------------------------------------------ small helpers
def notify(db: Session, room: str, msg: dict | None = None) -> None:
    """Queue a socket push for after commit (dropped on rollback). Payloads never carry patient data."""
    item = (room, msg or {"event": "pulse"})
    queued = db.info.setdefault("broadcasts", [])
    if item not in queued:
        queued.append(item)


def label(code: str) -> str:
    return CODES.get(code, (code, ""))[0]


def patient_name(p: Patient) -> str:
    return f"{p.surname} {p.first_name}"


def patient_brief(p: Patient | None) -> dict | None:
    return {"id": p.id, "name": patient_name(p), "patient_number": p.patient_number} if p else None


def dept_names(db: Session, facility_id: str) -> dict[str, str]:
    return dict(db.execute(select(Department.id, Department.name).where(Department.facility_id == facility_id)).all())


def doctor_title(s: Staff) -> str:
    return s.full_name if s.role != "doctor" or s.full_name.lower().startswith("dr") else f"Dr. {s.full_name}"


def doctors(db: Session, facility_id: str, *, on_duty: bool | None = None, department_id: str | None = None) -> list[Staff]:
    q = select(Staff).where(Staff.facility_id == facility_id, Staff.role == "doctor", Staff.is_active)
    if on_duty:
        q = q.where(Staff.on_duty)
    if department_id:
        q = q.where(Staff.department_id == department_id)
    return list(db.scalars(q.order_by(Staff.full_name)).all())


# ------------------------------------------------------------------ channels
def slug(name: str) -> str:
    """'General Outpatients (GOPD)' -> 'general-outpatients'; shown as #general-outpatients."""
    base = re.sub(r"\(.*?\)", "", name).lower().replace("&", " ")
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-") or "department"


def ensure_channels(db: Session, facility_id: str) -> None:
    """All staff + one channel per department, created idempotently (safe under concurrent requests)."""
    insert_ignore(db, PulseChannel, id=uid(), facility_id=facility_id, kind="broadcast", key="broadcast",
                  name="All staff", created_at=utcnow())
    have = {c.department_id: c for c in db.scalars(select(PulseChannel).where(
        PulseChannel.facility_id == facility_id, PulseChannel.kind == "department")).all()}
    for d in db.scalars(select(Department).where(Department.facility_id == facility_id)).all():
        if d.id not in have:
            insert_ignore(db, PulseChannel, id=uid(), facility_id=facility_id, kind="department", key=f"dept:{d.id}",
                          name=d.name, department_id=d.id, created_at=utcnow())
        elif have[d.id].name != d.name:           # department renamed by the admin
            have[d.id].name = d.name
    db.flush()


def broadcast_channel(db: Session, facility_id: str) -> PulseChannel:
    ch = db.scalar(select(PulseChannel).where(PulseChannel.facility_id == facility_id, PulseChannel.key == "broadcast"))
    if not ch:
        ensure_channels(db, facility_id)
        ch = db.scalar(select(PulseChannel).where(PulseChannel.facility_id == facility_id,
                                                  PulseChannel.key == "broadcast"))
    return ch


def department_channel(db: Session, facility_id: str, department_id: str | None) -> PulseChannel | None:
    if not department_id:
        return None
    d = db.get(Department, department_id)
    if not d or d.facility_id != facility_id or not d.is_active:
        return None
    key = f"dept:{d.id}"
    ch = db.scalar(select(PulseChannel).where(PulseChannel.facility_id == facility_id, PulseChannel.key == key))
    if not ch:
        ensure_channels(db, facility_id)
        ch = db.scalar(select(PulseChannel).where(PulseChannel.facility_id == facility_id, PulseChannel.key == key))
    return ch


def channel_by_code(db: Session, facility_id: str, *codes: str) -> PulseChannel | None:
    d = db.scalar(select(Department).where(Department.facility_id == facility_id, Department.is_active,
                                           func.upper(Department.code).in_([c.upper() for c in codes])))
    return department_channel(db, facility_id, d.id) if d else None


def direct_channel(db: Session, me: Staff, other: Staff) -> PulseChannel:
    a, b = sorted((me.id, other.id))
    key = f"dm:{a}:{b}"
    insert_ignore(db, PulseChannel, id=uid(), facility_id=me.facility_id, kind="direct", key=key,
                  name="Direct", member_a=a, member_b=b, created_at=utcnow())
    return db.scalar(select(PulseChannel).where(PulseChannel.facility_id == me.facility_id, PulseChannel.key == key))


def can_see(ch: PulseChannel, staff: Staff) -> bool:
    if ch.facility_id != staff.facility_id:
        return False
    return ch.kind != "direct" or staff.id in (ch.member_a, ch.member_b)


def mark_read(db: Session, channel_id: str, staff_id: str, at=None) -> None:
    at = at or utcnow()
    insert_ignore(db, PulseRead, channel_id=channel_id, staff_id=staff_id, last_read_at=at)
    r = db.get(PulseRead, (channel_id, staff_id))
    if r.last_read_at is None or r.last_read_at < at:
        r.last_read_at = at


def post(db: Session, ch: PulseChannel, body: str, *, kind: str = "system", sender: Staff | None = None,
         priority: str = "routine", patient_id: str | None = None, payload: dict | None = None,
         ack_required: bool = False, at=None) -> PulseMessage:
    at = at or utcnow()
    m = PulseMessage(id=uid(), facility_id=ch.facility_id, channel_id=ch.id, sender_id=sender.id if sender else None,
                     kind=kind, body=body, priority=priority, patient_id=patient_id, payload=payload,
                     ack_required=ack_required, created_at=at)
    db.add(m)
    ch.last_message_at = at
    if sender:
        mark_read(db, ch.id, sender.id, at)       # your own message is never unread for you
    if ch.kind == "direct":
        notify(db, f"staff:{ch.member_a}")
        notify(db, f"staff:{ch.member_b}")
    else:
        notify(db, f"fac:{ch.facility_id}")
    db.flush()
    return m


UNREAD_WINDOW = timedelta(days=7)    # a channel you've never opened counts only the last week as unread


def unread_counts(db: Session, staff: Staff) -> dict[str, int]:
    r = PulseRead
    since = func.coalesce(r.last_read_at, utcnow() - UNREAD_WINDOW)
    rows = db.execute(
        select(PulseMessage.channel_id, func.count())
        .join(r, and_(r.channel_id == PulseMessage.channel_id, r.staff_id == staff.id), isouter=True)
        .where(PulseMessage.facility_id == staff.facility_id, PulseMessage.created_at > since,
               or_(PulseMessage.sender_id.is_(None), PulseMessage.sender_id != staff.id))
        .group_by(PulseMessage.channel_id)).all()
    return dict(rows)


def my_channel_ids(db: Session, staff: Staff) -> set[str]:
    """Channels that count towards *your* unread badge: All staff, your department, your direct chats.
    Every department channel stays readable by everyone; it just doesn't nag people outside it."""
    q = select(PulseChannel.id).where(PulseChannel.facility_id == staff.facility_id, or_(
        PulseChannel.kind == "broadcast",
        and_(PulseChannel.kind == "direct", or_(PulseChannel.member_a == staff.id, PulseChannel.member_b == staff.id)),
        and_(PulseChannel.kind == "department", PulseChannel.department_id == staff.department_id)
        if staff.department_id else False))
    return set(db.scalars(q).all())


# ------------------------------------------------------------------ alerts
def alert(db: Session, recipient_id: str, facility_id: str, kind: str, title: str, body: str = "", *,
          priority: str = "routine", ack_required: bool = False, patient_id=None, visit_id=None, ref_id=None,
          payload=None, at=None) -> PulseAlert:
    a = PulseAlert(id=uid(), facility_id=facility_id, recipient_id=recipient_id, kind=kind, title=title[:200],
                   body=body, priority=priority, ack_required=ack_required, patient_id=patient_id,
                   visit_id=visit_id, ref_id=ref_id, payload=payload, created_at=at or utcnow())
    db.add(a)
    notify(db, f"staff:{recipient_id}")
    return a


def ack_alert(db: Session, a: PulseAlert, staff: Staff) -> None:
    now = utcnow()
    a.seen_at = a.seen_at or now
    if a.acked_at:
        return
    a.acked_at, a.acked_by = now, staff.id
    if a.kind == "critical_vitals" and a.ref_id:
        # sent to every on-duty doctor: once one of them has it, close the copies so they don't all run
        for other in db.scalars(select(PulseAlert).where(PulseAlert.kind == a.kind, PulseAlert.ref_id == a.ref_id,
                                                         PulseAlert.acked_at.is_(None), PulseAlert.id != a.id)).all():
            other.acked_at, other.acked_by = now, staff.id
            notify(db, f"staff:{other.recipient_id}")
    notify(db, f"staff:{a.recipient_id}")


# ------------------------------------------------------------------ pages
def resolve_targets(db: Session, facility_id: str, *, target_staff: Staff | None, department_id: str | None,
                    exclude: str | None = None) -> list[Staff]:
    """The named person; else on-duty doctors of the department; else every on-duty doctor; else every doctor."""
    if target_staff:
        return [target_staff]
    for pool in (doctors(db, facility_id, on_duty=True, department_id=department_id) if department_id else [],
                 doctors(db, facility_id, on_duty=True), doctors(db, facility_id)):
        pool = [s for s in pool if s.id != exclude] or pool    # don't page the person raising it, unless alone
        if pool:
            return pool
    return []


def targets_of(db: Session, page: PulsePage) -> list[Staff]:
    return list(db.scalars(select(Staff).join(PulsePageTarget, PulsePageTarget.staff_id == Staff.id)
                           .where(PulsePageTarget.page_id == page.id)
                           .order_by(PulsePageTarget.level, Staff.full_name)).all())


def add_targets(db: Session, page: PulsePage, staff: list[Staff], level: int, at=None) -> list[Staff]:
    have = set(db.scalars(select(PulsePageTarget.staff_id).where(PulsePageTarget.page_id == page.id)).all())
    new = [s for s in staff if s.id not in have]
    for s in new:
        db.add(PulsePageTarget(page_id=page.id, staff_id=s.id, level=level, notified_at=at or utcnow()))
        notify(db, f"staff:{s.id}", {"event": "page", "id": page.id})
    return new


def page_channel(db: Session, facility_id: str, department_id: str | None) -> PulseChannel:
    return (department_channel(db, facility_id, department_id) or channel_by_code(db, facility_id, *EMERGENCY_CODES)
            or broadcast_channel(db, facility_id))


def where(page: PulsePage, ward: Ward | None) -> str:
    place = ward.name if ward else "Unknown ward"
    return f"{place}, bed {page.bed}" if page.bed else place


def active_duplicate(db: Session, facility_id: str, code: str, ward_id: str, bed: str | None,
                     patient_id: str | None) -> PulsePage | None:
    """Same code for the same patient (or the same ward + bed when no patient is attached) while one is open."""
    q = select(PulsePage).where(PulsePage.facility_id == facility_id, PulsePage.code == code,
                                PulsePage.status.in_(ACTIVE))
    if patient_id:
        q = q.where(PulsePage.patient_id == patient_id)
    else:
        q = q.where(PulsePage.ward_id == ward_id, PulsePage.patient_id.is_(None),
                    PulsePage.bed.is_(None) if not bed else func.lower(PulsePage.bed) == bed.lower())
    return db.scalar(q.order_by(PulsePage.created_at))


def system_line(db: Session, page: PulsePage, text: str, priority: str = "urgent") -> None:
    ch = db.get(PulseChannel, page.channel_id) if page.channel_id else None
    if ch:
        post(db, ch, text, kind="page", priority=priority, patient_id=page.patient_id,
             payload={"page_id": page.id, "code": page.code, "status": page.status})


def escalate(db: Session, page: PulsePage) -> list[Staff]:
    """Widen a page nobody has acknowledged: level 1 every on-duty doctor, level 2 every active doctor."""
    now = utcnow()
    page.escalation_level += 1
    page.escalated_at = now
    pool = doctors(db, page.facility_id, on_duty=True) if page.escalation_level == 1 else doctors(db, page.facility_id)
    new = add_targets(db, page, pool, page.escalation_level, now)
    ward = db.get(Ward, page.ward_id)
    who = "every on-duty doctor" if page.escalation_level == 1 else "every doctor in the hospital"
    wait = round((now - page.created_at).total_seconds() / 60, 1)
    alert(db, page.raised_by, page.facility_id, "page_escalated",
          f"{label(page.code)} not answered yet: now paging {who}",
          f"{where(page, ward)}. No one has acknowledged after {wait:g} min.",
          priority="critical", patient_id=page.patient_id, ref_id=page.id,
          payload={"page_id": page.id, "level": page.escalation_level})
    for s in new:
        alert(db, s.id, page.facility_id, "page_escalated", f"{label(page.code)}: {where(page, ward)}",
              f"Escalated to you after {wait:g} min without a response.", priority="critical",
              patient_id=page.patient_id, ref_id=page.id, payload={"page_id": page.id, "level": page.escalation_level})
    for s in targets_of(db, page):        # earlier targets get the alarm again
        notify(db, f"staff:{s.id}", {"event": "page", "id": page.id})
    system_line(db, page, f"No response after {wait:g} min. {label(page.code)} escalated to {who}"
                + (f" ({len(new)} more)." if new else "."), priority="critical")
    notify(db, f"fac:{page.facility_id}")
    return new


# ------------------------------------------------------------------ views
def latest_vitals(db: Session, patient_id: str) -> dict | None:
    v = db.scalar(select(Vitals).where(Vitals.patient_id == patient_id).order_by(Vitals.recorded_at.desc()))
    if not v:
        return None
    return {"recorded_at": v.recorded_at.isoformat(), "bp_systolic": v.bp_systolic, "bp_diastolic": v.bp_diastolic,
            "pulse_rate": v.pulse_rate, "respiratory_rate": v.respiratory_rate, "temperature": v.temperature,
            "spo2": v.spo2, "pain_score": v.pain_score, "triage_priority": v.triage_priority, "flags": v.flags or []}


def patient_detail(db: Session, p: Patient) -> dict:
    """What a doctor running to a bedside needs before they get there."""
    allergies = db.scalars(select(AllergyRecord).where(AllergyRecord.patient_id == p.id)).all()
    dx, seen = [], set()
    for d in db.scalars(select(Diagnosis).where(Diagnosis.patient_id == p.id, Diagnosis.status == "active")
                        .order_by(Diagnosis.diagnosed_at.desc()).limit(30)).all():
        if d.icd10_code not in seen and len(dx) < 6:
            seen.add(d.icd10_code)
            dx.append({"code": d.icd10_code, "description": d.icd10_description})
    visit = db.scalar(select(Visit.id).where(Visit.patient_id == p.id, Visit.status.in_(("checked_in", "in_progress")))
                      .order_by(Visit.checked_in_at.desc()))
    return {"id": p.id, "name": patient_name(p), "patient_number": p.patient_number,
            "age": age_years(p.date_of_birth), "gender": p.gender, "blood_group": p.blood_group,
            "allergies": [{"allergen_name": a.allergen_name, "severity": a.severity, "reaction": a.reaction}
                          for a in allergies],
            "latest_vitals": latest_vitals(db, p.id), "diagnoses": dx, "active_visit_id": visit}


def _person(s: Staff | None, extra: bool = True) -> dict | None:
    if not s:
        return None
    d = {"id": s.id, "name": s.full_name, "position": s.position}
    if extra:
        d["role"] = s.role
    return d


def page_view(db: Session, page: PulsePage, *, with_patient: bool = True) -> dict:
    ward = db.get(Ward, page.ward_id)
    raiser, responder = db.get(Staff, page.raised_by), db.get(Staff, page.responder_id) if page.responder_id else None
    p = db.get(Patient, page.patient_id) if page.patient_id else None
    iso = lambda t: t.isoformat() if t else None  # noqa: E731
    return {"id": page.id, "code": page.code, "code_label": label(page.code), "status": page.status,
            "ward": {"id": ward.id, "name": ward.name, "floor": ward.floor} if ward else None, "bed": page.bed,
            "note": page.note, "raised_by": _person(raiser),
            "targets": [_person(s, extra=False) for s in targets_of(db, page)],
            "responder": _person(responder, extra=False), "eta_minutes": page.eta_minutes,
            "escalation_level": page.escalation_level, "created_at": iso(page.created_at),
            "acked_at": iso(page.acked_at), "arrived_at": iso(page.arrived_at), "resolved_at": iso(page.resolved_at),
            "escalated_at": iso(page.escalated_at), "outcome": page.outcome,
            "response_seconds": round((page.acked_at - page.created_at).total_seconds()) if page.acked_at else None,
            "patient": (patient_detail(db, p) if with_patient else patient_brief(p)) if p else None}


def page_sort_key(page: PulsePage):
    return (page.status != "paging", CODE_RANK.get(page.code, 99), page.created_at)


# ------------------------------------------------------------------ sweeper
def tick(db: Session) -> int:
    """Background sweep, idempotent: escalate unanswered pages and unacknowledged critical results.
    Returns rows changed."""
    now, changed = utcnow(), 0
    cutoff = now - timedelta(seconds=settings.page_escalate_seconds)
    stale = db.scalars(select(PulsePage).where(
        PulsePage.status == "paging", PulsePage.escalation_level < MAX_LEVEL,
        func.coalesce(PulsePage.escalated_at, PulsePage.created_at) < cutoff).with_for_update(skip_locked=True)).all()
    for page in stale:
        escalate(db, page)
        changed += 1
    crit_cutoff = now - timedelta(minutes=settings.critical_result_escalate_minutes)
    for a in db.scalars(select(PulseAlert).where(
            PulseAlert.kind == "lab_critical", PulseAlert.acked_at.is_(None), PulseAlert.escalated_at.is_(None),
            PulseAlert.created_at < crit_cutoff).with_for_update(skip_locked=True)).all():
        escalate_critical_result(db, a)
        changed += 1
    return changed


def escalate_critical_result(db: Session, a: PulseAlert) -> None:
    """The doctor hasn't acknowledged a critical value: copy it to their department (or All staff), so a
    colleague can act. The original alert stays open: escalation adds readers, it never removes responsibility."""
    a.escalated_at = utcnow()
    doc = db.get(Staff, a.recipient_id)
    ch = department_channel(db, a.facility_id, doc.department_id if doc else None) or broadcast_channel(db, a.facility_id)
    mins = settings.critical_result_escalate_minutes
    post(db, ch, f"CRITICAL RESULT not acknowledged by {doctor_title(doc) if doc else 'the ordering doctor'} "
                 f"after {mins} min. {a.title}. {a.body}".strip(),
         kind="system", priority="critical", patient_id=a.patient_id, ack_required=True,
         payload={"alert_id": a.id, "lab_order_id": a.ref_id, "visit_id": a.visit_id})
    notify(db, f"staff:{a.recipient_id}")
