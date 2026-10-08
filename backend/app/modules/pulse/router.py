"""AraPulse API: channels, alerts, Pulse Codes (emergency pages) and the /ws/pulse socket."""
import asyncio
from datetime import datetime, timedelta, timezone
from statistics import median

import jwt
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ...config import settings
from ...db import SessionLocal, get_db, local_day_start_utc, utcnow
from ...realtime import hub
from ..core.models import AuditLog, Department, Staff, Ward
from ..core.security import audit, require
from ..registration import service as reg
from ..registration.models import Patient
from . import handlers as _handlers  # noqa: F401  (registers event subscribers)
from . import service as svc
from .models import PulseAlert, PulseChannel, PulseMessage, PulsePage, PulsePageTarget

router = APIRouter(tags=["pulse"])
ANYONE = ("reception", "nurse", "doctor", "lab", "pharmacy", "admin")
signed_in = require(*ANYONE)


def _iso(t):
    return t.isoformat() if t else None


def _audit_patients(db: Session, staff: Staff, record_type: str, patient_ids) -> None:
    for pid in {p for p in patient_ids if p}:
        audit(db, staff, "view", record_type, None, pid)


def _audit_page_once(db: Session, staff: Staff, page: PulsePage) -> None:
    """Pages are re-fetched on every push; one audit row per person per page is the useful record."""
    if not page.patient_id:
        return
    if not db.scalar(select(AuditLog.id).where(AuditLog.patient_id == page.patient_id, AuditLog.staff_id == staff.id,
                                               AuditLog.record_type == "pulse_page", AuditLog.record_id == page.id)):
        audit(db, staff, "view", "pulse_page", page.id, page.patient_id)


# ------------------------------------------------------------------ summary
def _my_active_pages(db: Session, staff: Staff) -> list[PulsePage]:
    targeted = select(PulsePageTarget.page_id).where(PulsePageTarget.staff_id == staff.id)
    rows = db.scalars(select(PulsePage).where(PulsePage.facility_id == staff.facility_id,
                                              PulsePage.status.in_(svc.ACTIVE),
                                              or_(PulsePage.id.in_(targeted), PulsePage.responder_id == staff.id))).all()
    return sorted(rows, key=svc.page_sort_key)


@router.get("/pulse/summary")
def summary(staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    svc.ensure_channels(db, staff.facility_id)
    unread = svc.unread_counts(db, staff)
    mine = svc.my_channel_ids(db, staff)
    open_q = select(PulseAlert).where(PulseAlert.recipient_id == staff.id, PulseAlert.acked_at.is_(None))
    open_alerts = db.scalars(open_q).all()
    pages = _my_active_pages(db, staff)
    for p in pages:
        _audit_page_once(db, staff, p)
    out = {"unread_messages": sum(n for cid, n in unread.items() if cid in mine),
           "open_alerts": len(open_alerts), "critical_alerts": sum(a.priority == "critical" for a in open_alerts),
           "active_pages_for_me": [svc.page_view(db, p) for p in pages], "on_duty": bool(staff.on_duty)}
    db.commit()
    return out


@router.get("/pulse/codes")
def codes(staff: Staff = Depends(signed_in)):
    """Pulse Codes in severity order, for the 'Page a doctor' picker."""
    return [{"code": c, "label": lbl, "description": desc} for c, (lbl, desc) in svc.CODES.items()]


# ------------------------------------------------------------------ channels
def _channel(db: Session, staff: Staff, channel_id: str) -> PulseChannel:
    ch = db.get(PulseChannel, channel_id)
    if not ch or not svc.can_see(ch, staff):
        raise HTTPException(404, "Conversation not found")
    return ch


def _channel_views(db: Session, staff: Staff, rows: list[PulseChannel]) -> list[dict]:
    unread = svc.unread_counts(db, staff)
    depts = {d.id: d for d in db.scalars(select(Department).where(Department.facility_id == staff.facility_id)).all()}
    ids = [c.id for c in rows]
    latest = select(PulseMessage.channel_id, func.max(PulseMessage.created_at).label("at")) \
        .where(PulseMessage.channel_id.in_(ids)).group_by(PulseMessage.channel_id).subquery()
    last = {m.channel_id: m for m in db.scalars(select(PulseMessage).join(latest, and_(
        PulseMessage.channel_id == latest.c.channel_id, PulseMessage.created_at == latest.c.at))).all()}
    people = {s.id: s for s in db.scalars(select(Staff).where(Staff.facility_id == staff.facility_id)).all()}
    out = []
    for c in rows:
        d = depts.get(c.department_id)
        other = None
        if c.kind == "direct":
            o = people.get(c.member_b if c.member_a == staff.id else c.member_a)
            other = {"id": o.id, "name": o.full_name, "role": o.role, "position": o.position} if o else None
        m = last.get(c.id)
        sender = people.get(m.sender_id) if m and m.sender_id else None
        out.append({"id": c.id, "kind": c.kind, "name": other["name"] if other else c.name,
                    "slug": svc.slug(c.name) if c.kind == "department" else ("all-staff" if c.kind == "broadcast" else None),
                    "department_id": c.department_id, "department_code": d.code if d else None,
                    "is_mine": c.kind != "department" or c.department_id == staff.department_id,
                    "other": other, "unread": unread.get(c.id, 0),
                    "last_message": {"body": m.body[:160], "at": m.created_at.isoformat(),
                                     "sender_name": sender.full_name if sender else "AraPulse"} if m else None})
    return out


@router.get("/pulse/channels")
def channels(staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    """All staff, then your department, then every other department, then your direct chats (newest first)."""
    svc.ensure_channels(db, staff.facility_id)
    active = set(db.scalars(select(Department.id).where(Department.facility_id == staff.facility_id,
                                                        Department.is_active)).all())
    rows = db.scalars(select(PulseChannel).where(PulseChannel.facility_id == staff.facility_id, or_(
        PulseChannel.kind != "direct", PulseChannel.member_a == staff.id, PulseChannel.member_b == staff.id))).all()
    rows = [c for c in rows if c.kind != "department" or c.department_id in active]
    rank = {"broadcast": 0, "department": 2, "direct": 3}
    rows.sort(key=lambda c: (1 if c.kind == "department" and c.department_id == staff.department_id
                             else rank[c.kind], c.name.lower() if c.kind != "direct" else "",
                             -(c.last_message_at or c.created_at).timestamp()))
    out = _channel_views(db, staff, rows)
    db.commit()
    return out


class DirectIn(BaseModel):
    staff_id: str


@router.post("/pulse/channels/direct")
def open_direct(body: DirectIn, staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    other = db.get(Staff, body.staff_id)
    if not other or other.facility_id != staff.facility_id or not other.is_active:
        raise HTTPException(404, "Staff member not found")
    if other.id == staff.id:
        raise HTTPException(422, "You can't start a conversation with yourself")
    ch = svc.direct_channel(db, staff, other)
    out = _channel_views(db, staff, [ch])[0]
    db.commit()
    return out


def _message_views(db: Session, staff: Staff, msgs: list[PulseMessage]) -> list[dict]:
    people = {s.id: s for s in db.scalars(select(Staff).where(Staff.facility_id == staff.facility_id)).all()}
    depts = svc.dept_names(db, staff.facility_id)
    pats = {p.id: p for p in db.scalars(select(Patient).where(
        Patient.id.in_({m.patient_id for m in msgs if m.patient_id}))).all()}
    out = []
    for m in msgs:
        s, ack = people.get(m.sender_id), people.get(m.acknowledged_by)
        out.append({"id": m.id, "channel_id": m.channel_id,
                    "sender": {"id": s.id, "name": s.full_name, "role": s.role, "position": s.position,
                               "department_name": depts.get(s.department_id)} if s else None,
                    "kind": m.kind, "body": m.body, "priority": m.priority,
                    "patient": svc.patient_brief(pats.get(m.patient_id)), "payload": m.payload,
                    "created_at": m.created_at.isoformat(), "ack_required": bool(m.ack_required),
                    "acknowledged_by": {"id": ack.id, "name": ack.full_name} if ack else None,
                    "acknowledged_at": _iso(m.acknowledged_at)})
    return out


@router.get("/pulse/channels/{channel_id}/messages")
def list_messages(channel_id: str, before: datetime | None = None, limit: int = 50,
                  staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    ch = _channel(db, staff, channel_id)
    q = select(PulseMessage).where(PulseMessage.channel_id == ch.id)
    if before:
        if before.tzinfo:
            before = before.astimezone(timezone.utc)
        q = q.where(PulseMessage.created_at < before.replace(tzinfo=None))
    msgs = list(reversed(db.scalars(q.order_by(PulseMessage.created_at.desc()).limit(max(1, min(limit, 200)))).all()))
    _audit_patients(db, staff, "pulse_message", [m.patient_id for m in msgs])
    out = _message_views(db, staff, msgs)
    db.commit()
    return out


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    priority: str = "routine"
    patient_id: str | None = None
    ack_required: bool | None = None


@router.post("/pulse/channels/{channel_id}/messages", status_code=201)
def send_message(channel_id: str, body: MessageIn, staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    ch = _channel(db, staff, channel_id)
    if body.priority not in svc.PRIORITIES:
        raise HTTPException(422, "priority must be routine, urgent or critical")
    if not body.body.strip():
        raise HTTPException(422, "Write a message first")
    if body.patient_id:
        p = db.get(Patient, body.patient_id)
        if not p or p.facility_id != staff.facility_id:
            raise HTTPException(404, "Patient not found")
    ack = body.ack_required if body.ack_required is not None else body.priority == "critical"
    m = svc.post(db, ch, body.body.strip(), kind="text", sender=staff, priority=body.priority,
                 patient_id=body.patient_id, ack_required=ack)
    audit(db, staff, "create", "pulse_message", m.id, body.patient_id, detail=f"{ch.kind}:{ch.name}"[:200])
    out = _message_views(db, staff, [m])[0]
    db.commit()
    return out


@router.post("/pulse/channels/{channel_id}/read")
def read_channel(channel_id: str, staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    ch = _channel(db, staff, channel_id)
    svc.mark_read(db, ch.id, staff.id)
    svc.notify(db, f"staff:{staff.id}")          # other tabs/devices of the same person update their badge
    db.commit()
    return {"ok": True}


@router.post("/pulse/messages/{message_id}/ack")
def ack_message(message_id: str, staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    m = db.get(PulseMessage, message_id, with_for_update=True)
    ch = db.get(PulseChannel, m.channel_id) if m else None
    if not m or not svc.can_see(ch, staff):
        raise HTTPException(404, "Message not found")
    if not m.ack_required:
        raise HTTPException(409, "This message does not need acknowledging")
    if m.sender_id == staff.id:
        raise HTTPException(409, "You sent this message: a colleague needs to acknowledge it")
    if not m.acknowledged_at:
        m.acknowledged_by, m.acknowledged_at = staff.id, utcnow()
        audit(db, staff, "acknowledge", "pulse_message", m.id, m.patient_id)
        svc.notify(db, f"fac:{staff.facility_id}" if ch.kind != "direct" else f"staff:{m.sender_id}")
    out = _message_views(db, staff, [m])[0]
    db.commit()
    return out


# ------------------------------------------------------------------ alerts
def _alert_views(db: Session, staff: Staff, alerts: list[PulseAlert]) -> list[dict]:
    pats = {p.id: p for p in db.scalars(select(Patient).where(
        Patient.id.in_({a.patient_id for a in alerts if a.patient_id}))).all()}
    ackers = {s.id: s for s in db.scalars(select(Staff).where(
        Staff.id.in_({a.acked_by for a in alerts if a.acked_by}))).all()}
    return [{"id": a.id, "kind": a.kind, "title": a.title, "body": a.body, "priority": a.priority,
             "ack_required": bool(a.ack_required), "patient": svc.patient_brief(pats.get(a.patient_id)),
             "visit_id": a.visit_id, "ref_id": a.ref_id, "payload": a.payload, "created_at": a.created_at.isoformat(),
             "seen_at": _iso(a.seen_at), "acked_at": _iso(a.acked_at), "escalated_at": _iso(a.escalated_at),
             "acked_by": {"id": a.acked_by, "name": ackers[a.acked_by].full_name} if a.acked_by in ackers else None}
            for a in alerts]


@router.get("/pulse/alerts")
def list_alerts(status: str = "open", staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    """Open = not yet acknowledged (seen is not enough). Critical first, then newest."""
    if status not in ("open", "all"):
        raise HTTPException(422, "status must be open or all")
    q = select(PulseAlert).where(PulseAlert.recipient_id == staff.id)
    if status == "open":
        q = q.where(PulseAlert.acked_at.is_(None))
    rows = db.scalars(q.order_by(PulseAlert.created_at.desc()).limit(100)).all()
    rank = {"critical": 0, "urgent": 1, "routine": 2}
    rows = sorted(rows, key=lambda a: (a.acked_at is not None, rank.get(a.priority, 3), -a.created_at.timestamp()))
    _audit_patients(db, staff, "pulse_alert", [a.patient_id for a in rows])
    out = _alert_views(db, staff, rows)
    db.commit()
    return out


def _my_alert(db: Session, staff: Staff, alert_id: str) -> PulseAlert:
    a = db.get(PulseAlert, alert_id, with_for_update=True)
    if not a or a.recipient_id != staff.id:
        raise HTTPException(404, "Alert not found")
    return a


@router.post("/pulse/alerts/{alert_id}/seen")
def alert_seen(alert_id: str, staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    a = _my_alert(db, staff, alert_id)
    if not a.seen_at:
        a.seen_at = utcnow()
        svc.notify(db, f"staff:{staff.id}")
    out = _alert_views(db, staff, [a])[0]
    db.commit()
    return out


@router.post("/pulse/alerts/{alert_id}/ack")
def alert_ack(alert_id: str, staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    a = _my_alert(db, staff, alert_id)
    if not a.acked_at:
        svc.ack_alert(db, a, staff)
        audit(db, staff, "acknowledge", "pulse_alert", a.id, a.patient_id, detail=a.kind)
    out = _alert_views(db, staff, [a])[0]
    db.commit()
    return out


# ------------------------------------------------------------------ patient lookup
@router.get("/pulse/patients")
def find_patients(q: str = "", staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    if len(q.strip()) < 2:
        raise HTTPException(422, "Type at least 2 characters")
    rows = reg.search(db, staff.facility_id, q, limit=10)
    audit(db, staff, "search", "patient", None, None, detail=f"pulse q={q[:40]}")
    db.commit()
    return [{"id": p.id, "name": svc.patient_name(p), "patient_number": p.patient_number,
             "age": reg.age_years(p.date_of_birth), "gender": p.gender} for p in rows]


# ------------------------------------------------------------------ Pulse Codes
class PageIn(BaseModel):
    code: str
    ward_id: str
    bed: str | None = Field(None, max_length=20)
    patient_id: str | None = None
    note: str | None = Field(None, max_length=500)
    target_staff_id: str | None = None
    target_department_id: str | None = None


@router.post("/pulse/pages", status_code=201)
def raise_page(body: PageIn, staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    if body.code not in svc.CODES:
        raise HTTPException(422, f"code must be one of {', '.join(svc.CODES)}")
    ward = db.get(Ward, body.ward_id)
    if not ward or ward.facility_id != staff.facility_id or not ward.is_active:
        raise HTTPException(404, "Ward not found")
    if body.patient_id:
        p = db.get(Patient, body.patient_id)
        if not p or p.facility_id != staff.facility_id:
            raise HTTPException(404, "Patient not found")
    target = None
    if body.target_staff_id:
        target = db.get(Staff, body.target_staff_id)
        if not target or target.facility_id != staff.facility_id or not target.is_active:
            raise HTTPException(404, "The person you chose to page was not found")
    dept_id = body.target_department_id
    if dept_id:
        d = db.get(Department, dept_id)
        if not d or d.facility_id != staff.facility_id:
            raise HTTPException(404, "Department not found")
    bed = (body.bed or "").strip() or None
    dup = svc.active_duplicate(db, staff.facility_id, body.code, ward.id, bed, body.patient_id)
    if dup:
        # one emergency, one page: a second press re-alerts the existing page's targets instead of spamming
        for s in svc.targets_of(db, dup):
            svc.notify(db, f"staff:{s.id}", {"event": "page", "id": dup.id})
        audit(db, staff, "duplicate", "pulse_page", dup.id, dup.patient_id)
        out = {**svc.page_view(db, dup), "duplicate": True}
        db.commit()
        return JSONResponse(status_code=200, content=out)

    route_dept = dept_id or ward.department_id
    targets = svc.resolve_targets(db, staff.facility_id, target_staff=target, department_id=route_dept,
                                  exclude=staff.id)
    if not targets:
        raise HTTPException(409, "There is no active doctor account to page. Call the emergency line.")
    page = PulsePage(facility_id=staff.facility_id, code=body.code, status="paging", ward_id=ward.id, bed=bed,
                     patient_id=body.patient_id, note=(body.note or "").strip() or None, raised_by=staff.id,
                     target_staff_id=target.id if target else None, target_department_id=dept_id,
                     channel_id=svc.page_channel(db, staff.facility_id, route_dept).id, created_at=utcnow())
    db.add(page)
    db.flush()
    svc.add_targets(db, page, targets, 0)
    names = ", ".join(svc.doctor_title(s) for s in targets[:4]) + (f" and {len(targets) - 4} more" if len(targets) > 4 else "")
    svc.system_line(db, page, f"{svc.label(page.code).upper()}: {svc.where(page, ward)}. Raised by {staff.full_name}. "
                              f"Paging {names}." + (f" Note: {page.note}" if page.note else ""), priority="critical")
    svc.notify(db, f"fac:{staff.facility_id}")
    audit(db, staff, "create", "pulse_page", page.id, page.patient_id, detail=f"{page.code} {ward.code} {bed or ''}".strip())
    out = {**svc.page_view(db, page), "duplicate": False}
    db.commit()
    return out


@router.get("/pulse/pages")
def list_pages(scope: str = "active", staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    """active: open pages, most severe and unanswered first (full patient detail).
    mine / all: newest first, last 100, patient as {id, name, patient_number} only."""
    q = select(PulsePage).where(PulsePage.facility_id == staff.facility_id)
    if scope == "active":
        pages = sorted(db.scalars(q.where(PulsePage.status.in_(svc.ACTIVE))).all(), key=svc.page_sort_key)
        for p in pages:
            _audit_page_once(db, staff, p)
        out = [svc.page_view(db, p) for p in pages]
    elif scope in ("mine", "all"):
        if scope == "mine":
            targeted = select(PulsePageTarget.page_id).where(PulsePageTarget.staff_id == staff.id)
            q = q.where(or_(PulsePage.raised_by == staff.id, PulsePage.responder_id == staff.id,
                            PulsePage.id.in_(targeted)))
        pages = db.scalars(q.order_by(PulsePage.created_at.desc()).limit(100)).all()
        _audit_patients(db, staff, "pulse_page", [p.patient_id for p in pages])
        out = [svc.page_view(db, p, with_patient=False) for p in pages]
    else:
        raise HTTPException(422, "scope must be active, mine or all")
    db.commit()
    return out


def _page(db: Session, staff: Staff, page_id: str, lock: bool = False) -> PulsePage:
    page = db.get(PulsePage, page_id, with_for_update=lock)    # the sweeper may be escalating it right now
    if not page or page.facility_id != staff.facility_id:
        raise HTTPException(404, "Page not found")
    return page


@router.get("/pulse/pages/{page_id}")
def get_page(page_id: str, staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    page = _page(db, staff, page_id)
    _audit_page_once(db, staff, page)
    out = svc.page_view(db, page)
    db.commit()
    return out


def _is_target(db: Session, page: PulsePage, staff: Staff) -> bool:
    return db.get(PulsePageTarget, (page.id, staff.id)) is not None


def _after_change(db: Session, staff: Staff, page: PulsePage, action: str, line: str, detail: str | None = None):
    svc.system_line(db, page, line, priority="routine" if page.status in ("resolved", "cancelled") else "urgent")
    for s in svc.targets_of(db, page):
        svc.notify(db, f"staff:{s.id}")
    svc.notify(db, f"staff:{page.raised_by}")
    svc.notify(db, f"fac:{page.facility_id}")
    audit(db, staff, action, "pulse_page", page.id, page.patient_id, detail=detail)
    out = svc.page_view(db, page)
    db.commit()
    return out


class AckIn(BaseModel):
    eta_minutes: int | None = Field(None, ge=0, le=120)


@router.post("/pulse/pages/{page_id}/ack")
def ack_page(page_id: str, body: AckIn | None = None, staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    page = _page(db, staff, page_id, lock=True)
    if not (_is_target(db, page, staff) or staff.role == "doctor"):
        raise HTTPException(403, "Only the people paged, or a doctor, can take this page")
    if page.status != "paging":
        if page.status in ("acknowledged", "arrived") and page.responder_id:
            who = db.get(Staff, page.responder_id)
            raise HTTPException(409, f"{svc.doctor_title(who)} is already responding to this page")
        raise HTTPException(409, f"This page is already {page.status}")
    eta = body.eta_minutes if body else None
    page.status, page.responder_id, page.acked_at, page.eta_minutes = "acknowledged", staff.id, utcnow(), eta
    secs = round((page.acked_at - page.created_at).total_seconds())
    return _after_change(db, staff, page, "acknowledge",
                         f"{svc.doctor_title(staff)} is responding" + (f", there in {eta} min." if eta is not None else ".")
                         + f" (answered in {secs} s)", detail=f"response {secs}s")


@router.post("/pulse/pages/{page_id}/arrive")
def arrive_page(page_id: str, staff: Staff = Depends(signed_in), db: Session = Depends(get_db)):
    page = _page(db, staff, page_id, lock=True)
    if page.status not in ("paging", "acknowledged"):
        raise HTTPException(409, f"This page is already {page.status}")
    if page.responder_id and page.responder_id != staff.id:
        raise HTTPException(409, "Another doctor is responding to this page")
    if not page.responder_id and not (_is_target(db, page, staff) or staff.role == "doctor"):
        raise HTTPException(403, "Only the people paged, or a doctor, can respond to this page")
    now = utcnow()
    page.responder_id = staff.id
    page.acked_at = page.acked_at or now
    page.status, page.arrived_at = "arrived", now
    return _after_change(db, staff, page, "arrive", f"{svc.doctor_title(staff)} is at the bedside.")


class ResolveIn(BaseModel):
    outcome: str | None = Field(None, max_length=500)


@router.post("/pulse/pages/{page_id}/resolve")
def resolve_page(page_id: str, body: ResolveIn | None = None, staff: Staff = Depends(signed_in),
                 db: Session = Depends(get_db)):
    page = _page(db, staff, page_id, lock=True)
    if page.status not in svc.ACTIVE:
        raise HTTPException(409, f"This page is already {page.status}")
    allowed = staff.id in (page.responder_id, page.raised_by) or staff.role in ("doctor", "admin") \
        or _is_target(db, page, staff)
    if not allowed:
        raise HTTPException(403, "Only the responder, the person who raised it, a doctor or an admin can close a page")
    page.status, page.resolved_at = "resolved", utcnow()
    page.outcome = ((body.outcome if body else None) or "").strip() or None
    return _after_change(db, staff, page, "resolve", f"{svc.label(page.code)} closed by {staff.full_name}."
                         + (f" Outcome: {page.outcome}" if page.outcome else ""))


class CancelIn(BaseModel):
    reason: str | None = Field(None, max_length=300)


@router.post("/pulse/pages/{page_id}/cancel")
def cancel_page(page_id: str, body: CancelIn | None = None, staff: Staff = Depends(signed_in),
                db: Session = Depends(get_db)):
    page = _page(db, staff, page_id, lock=True)
    if staff.id != page.raised_by and staff.role != "admin":
        raise HTTPException(403, "Only the person who raised the page or an admin can cancel it")
    if page.status not in ("paging", "acknowledged"):
        raise HTTPException(409, f"This page is already {page.status}")
    reason = ((body.reason if body else None) or "").strip() or None
    page.status, page.resolved_at, page.outcome = "cancelled", utcnow(), reason
    return _after_change(db, staff, page, "cancel", f"{svc.label(page.code)} stood down by {staff.full_name}."
                         + (f" Reason: {reason}" if reason else ""), detail=reason)


# ------------------------------------------------------------------ admin stats
@router.get("/pulse/stats")
def stats(staff: Staff = Depends(require("admin")), db: Session = Depends(get_db)):
    fid, now = staff.facility_id, utcnow()
    since = now - timedelta(days=14)
    today = local_day_start_utc()
    recent = db.scalars(select(PulsePage).where(PulsePage.facility_id == fid, PulsePage.created_at >= since)
                        .order_by(PulsePage.created_at.desc())).all()
    acks = [(p.acked_at - p.created_at).total_seconds() for p in recent if p.acked_at]
    count = lambda q: db.scalar(select(func.count()).select_from(q.subquery()))  # noqa: E731
    out = {"pages_today": sum(p.created_at >= today for p in recent),
           "open_pages": count(select(PulsePage.id).where(PulsePage.facility_id == fid,
                                                          PulsePage.status.in_(svc.ACTIVE))),
           "median_ack_seconds": round(median(acks)) if acks else None,
           "messages_today": count(select(PulseMessage.id).where(PulseMessage.facility_id == fid,
                                                                 PulseMessage.created_at >= today)),
           "open_alerts": count(select(PulseAlert.id).where(PulseAlert.facility_id == fid, PulseAlert.acked_at.is_(None))),
           "by_code": [{"code": c, "label": lbl, "count": sum(p.code == c for p in recent)}
                       for c, (lbl, _) in svc.CODES.items()],
           "recent_pages": [{**svc.page_view(db, p, with_patient=False), "patient": None} for p in recent[:10]]}
    audit(db, staff, "view", "pulse_stats")
    db.commit()
    return out


# ------------------------------------------------------------------ socket
def _socket_staff(token: str) -> Staff | None:
    """Same checks as core.security.current_staff: signature, expiry, account active, token version."""
    try:
        data = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    with SessionLocal() as db:
        s = db.get(Staff, data.get("sub"))
        if not s or not s.is_active or data.get("ver", 0) != (s.token_version or 0):
            return None
        return s


@router.websocket("/ws/pulse")
async def ws_pulse(ws: WebSocket, token: str = ""):
    """Pushes only {"event": "pulse"} (refetch) or {"event": "page", "id": ...}; never patient data."""
    staff = await asyncio.to_thread(_socket_staff, token)
    await ws.accept()
    if not staff:
        await ws.close(code=4401)
        return
    hub.add(ws, f"staff:{staff.id}", f"fac:{staff.facility_id}")
    try:
        while True:
            await ws.receive_text()                  # client pings keep proxies from closing the socket
    except WebSocketDisconnect:
        pass
    finally:
        hub.leave_all(ws)
