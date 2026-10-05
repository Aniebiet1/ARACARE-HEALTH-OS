"""Queue engine: ticket state machine, weighted fair queuing with aging, journey cascade."""
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...config import settings
from ...db import utcnow
from ...events import publish
from ..core.messaging import queue_message
from ..registration.models import Patient, Visit
from ..registration.service import age_years
from .models import Journey, JourneyStep, QueueState, Ticket

PREFIX = {"TRIAGE": "TRI", "OPD-GEN": "OPD", "LAB": "LAB", "PHARM": "PHM", "CASH": "CSH"}
TIER_RANK = {"EMERGENCY": 0, "HIGH": 1, "NORMAL": 2, "FOLLOW_UP": 3}
OPEN = ("waiting", "called", "in_service", "no_show")
# Departments that exist as live queues in this release. Others become 'deferred' steps.
LIVE_DEPARTMENTS = {"TRIAGE", "OPD-GEN"}


def initial_priority(patient: Patient, visit: Visit) -> str:
    if visit.visit_type == "emergency":
        return "EMERGENCY"
    if visit.visit_type == "follow_up":
        return "FOLLOW_UP"
    age = age_years(patient.date_of_birth)
    if visit.visit_type == "anc" or age < 5 or age >= 65:
        return "HIGH"
    return "NORMAL"


def _state(db: Session, facility_id: str, dept: str, day: date) -> QueueState:
    st = db.scalar(select(QueueState).where(QueueState.facility_id == facility_id,
                                            QueueState.department == dept, QueueState.day == day))
    if not st:
        st = QueueState(facility_id=facility_id, department=dept, day=day)
        db.add(st)
        db.flush()
    return st


def issue_ticket(db: Session, journey: Journey, step: JourneyStep, visit_id: str, priority: str) -> Ticket:
    day = date.today()
    st = _state(db, journey.facility_id, step.department, day)
    st.last_seq += 1
    now = utcnow()
    t = Ticket(facility_id=journey.facility_id, department=step.department, day=day,
               journey_step_id=step.id, visit_id=visit_id, patient_id=journey.patient_id,
               ticket_number=f"{PREFIX.get(step.department, step.department[:3])}-{st.last_seq:03d}",
               sequence_number=st.last_seq, priority_tier=priority, status="waiting",
               issued_at=now, entered_waiting_at=now)
    db.add(t)
    step.status = "active"
    db.flush()
    return t


def add_step(db: Session, journey: Journey, department: str, created_by="system", note=None,
             visit_id: str | None = None, priority="NORMAL") -> tuple[JourneyStep, Ticket | None]:
    order = (db.scalar(select(JourneyStep.step_order).where(JourneyStep.journey_id == journey.id)
                       .order_by(JourneyStep.step_order.desc())) or 0) + 1
    step = JourneyStep(journey_id=journey.id, step_order=order, department=department,
                       created_by=created_by, note=note)
    db.add(step)
    db.flush()
    if department not in LIVE_DEPARTMENTS:
        step.status = "deferred"
        return step, None
    return step, issue_ticket(db, journey, step, visit_id or "", priority)


def start_journey(db: Session, visit: Visit, patient: Patient) -> tuple[Journey, Ticket]:
    j = Journey(visit_id=visit.id, patient_id=patient.id, facility_id=visit.facility_id)
    db.add(j)
    db.flush()
    _, ticket = add_step(db, j, "TRIAGE", visit_id=visit.id, priority=initial_priority(patient, visit))
    publish(db, "TicketIssued", {"ticket": ticket.ticket_number, "department": "TRIAGE", "visit_id": visit.id},
            visit.facility_id, room="queue")
    return j, ticket


# ---------------------------------------------------------------- ordering / WFQ
def _aged_tier(t: Ticket, now: datetime) -> str:
    waited = (now - t.entered_waiting_at).total_seconds() / 60
    if t.priority_tier == "NORMAL" and waited > settings.aging_p2_minutes:
        return "HIGH"
    if t.priority_tier == "FOLLOW_UP" and waited > settings.aging_p3_minutes:
        return "NORMAL"
    return t.priority_tier


def waiting_tickets(db: Session, facility_id: str, dept: str) -> list[Ticket]:
    now = utcnow()
    rows = db.scalars(select(Ticket).where(Ticket.facility_id == facility_id, Ticket.department == dept,
                                           Ticket.day == date.today(), Ticket.status == "waiting")).all()
    for t in rows:
        eff = _aged_tier(t, now)
        if eff != t.priority_tier:  # aging promotion is persisted and flagged
            t.priority_tier, t.priority_aged = eff, True
    return sorted(rows, key=lambda t: (TIER_RANK[t.priority_tier], t.entered_waiting_at))


def pick_next(db: Session, facility_id: str, dept: str) -> Ticket | None:
    """Emergency first -> aging -> weighted fair queuing so HIGH can't starve NORMAL (or NORMAL starve FOLLOW_UP)."""
    rows = waiting_tickets(db, facility_id, dept)
    if not rows:
        return None
    by = {tier: [t for t in rows if t.priority_tier == tier] for tier in TIER_RANK}
    st = _state(db, facility_id, dept, date.today())
    if by["EMERGENCY"]:
        return by["EMERGENCY"][0]
    if by["HIGH"] and not (st.p1_streak >= settings.p1_burst_limit and by["NORMAL"]):
        st.p1_streak += 1
        return by["HIGH"][0]
    if by["NORMAL"] and not (st.p2_streak >= settings.p2_burst_limit and by["FOLLOW_UP"]):
        st.p1_streak = 0
        st.p2_streak += 1
        return by["NORMAL"][0]
    if by["FOLLOW_UP"]:
        st.p2_streak = 0
        return by["FOLLOW_UP"][0]
    return by["HIGH"][0] if by["HIGH"] else None


# ---------------------------------------------------------------- transitions
def _patient(db: Session, t: Ticket) -> Patient:
    return db.get(Patient, t.patient_id)


def call_ticket(db: Session, t: Ticket, counter: str):
    t.status, t.called_at, t.counter_name = "called", utcnow(), counter
    p = _patient(db, t)
    queue_message(db, t.facility_id, p.id, p.phone,
                  f"You are NEXT. {t.ticket_number}. Please go to {counter} now.")
    publish(db, "TicketCalled", {"ticket": t.ticket_number, "department": t.department, "counter": counter},
            t.facility_id, room="queue")


def mark_arrived(db: Session, t: Ticket):
    t.status, t.confirmed_at = "in_service", utcnow()
    publish(db, "TicketInService", {"ticket": t.ticket_number, "department": t.department}, t.facility_id, room="queue")


def mark_no_show(db: Session, t: Ticket):
    t.no_show_count += 1
    t.no_show_at = utcnow()
    p = _patient(db, t)
    if t.no_show_count >= 2:           # second no-show ends the journey step
        cancel_ticket(db, t, "second no-show")
        return
    t.status = "no_show"
    queue_message(db, t.facility_id, p.id, p.phone,
                  f"You missed your call ({t.ticket_number}). Reply 1 to rejoin the queue. "
                  "You have 30 minutes before your slot is forfeited.")
    publish(db, "TicketNoShow", {"ticket": t.ticket_number, "department": t.department}, t.facility_id, room="queue")


def rejoin(db: Session, t: Ticket):
    t.status, t.entered_waiting_at = "waiting", utcnow()   # back of its priority tier
    t.called_at = t.confirmed_at = None
    publish(db, "TicketRejoined", {"ticket": t.ticket_number, "department": t.department}, t.facility_id, room="queue")


def cancel_ticket(db: Session, t: Ticket, reason: str):
    t.status, t.completed_at = "cancelled", utcnow()
    step = db.get(JourneyStep, t.journey_step_id) if t.journey_step_id else None
    if step:
        step.status, step.completed_at = "abandoned", utcnow()
        step.note = reason
    publish(db, "TicketCancelled", {"ticket": t.ticket_number, "department": t.department, "reason": reason},
            t.facility_id, room="queue")
    _maybe_close_journey(db, t.visit_id)


def complete_ticket(db: Session, t: Ticket):
    """Journey cascade: finishing a step activates what comes next."""
    if t.status == "completed":
        return
    t.status, t.completed_at = "completed", utcnow()
    step = db.get(JourneyStep, t.journey_step_id) if t.journey_step_id else None
    if step:
        step.status, step.completed_at = "completed", utcnow()
    publish(db, "StepCompleted", {"ticket": t.ticket_number, "department": t.department, "visit_id": t.visit_id},
            t.facility_id, room="queue")
    if t.department == "TRIAGE":
        _activate_opd(db, t)
    else:
        _maybe_close_journey(db, t.visit_id)


def _activate_opd(db: Session, triage_ticket: Ticket, priority: str | None = None):
    j = db.scalar(select(Journey).where(Journey.visit_id == triage_ticket.visit_id))
    _, opd = add_step(db, j, "OPD-GEN", visit_id=triage_ticket.visit_id,
                      priority=priority or triage_ticket.priority_tier)
    p = _patient(db, triage_ticket)
    queue_message(db, j.facility_id, p.id, p.phone, f"Next: Doctor consultation. Queue number: {opd.ticket_number}.")
    publish(db, "TicketIssued", {"ticket": opd.ticket_number, "department": "OPD-GEN", "visit_id": j.visit_id},
            j.facility_id, room="queue")


def _maybe_close_journey(db: Session, visit_id: str):
    j = db.scalar(select(Journey).where(Journey.visit_id == visit_id))
    if not j or j.status != "in_progress":
        return
    steps = db.scalars(select(JourneyStep).where(JourneyStep.journey_id == j.id)).all()
    # 'deferred' steps (lab/pharmacy modules not yet live) don't block the clinical journey
    if all(s.status in ("completed", "abandoned", "deferred") for s in steps):
        abandoned = all(s.status == "abandoned" for s in steps)
        j.status = "abandoned" if abandoned else "completed"
        j.completed_at = utcnow()
        visit = db.get(Visit, visit_id)
        if visit:
            visit.status = "abandoned" if abandoned else "completed"
        publish(db, "JourneyClinicalCompleted" if not abandoned else "JourneyAbandoned",
                {"visit_id": visit_id, "deferred": [s.department for s in steps if s.status == "deferred"]},
                j.facility_id, room="queue")


def tick(db: Session) -> int:
    """Background sweep: called -> no_show after 3 min; no_show -> cancelled after 30 min."""
    now, changed = utcnow(), 0
    for t in db.scalars(select(Ticket).where(Ticket.status == "called")).all():
        if t.called_at and (now - t.called_at).total_seconds() > settings.call_timeout_seconds:
            mark_no_show(db, t)
            changed += 1
    for t in db.scalars(select(Ticket).where(Ticket.status == "no_show")).all():
        if t.no_show_at and (now - t.no_show_at).total_seconds() > settings.noshow_grace_seconds:
            cancel_ticket(db, t, "no response within grace window")
            changed += 1
    return changed


def stats(db: Session, facility_id: str, dept: str) -> dict:
    today = db.scalars(select(Ticket).where(Ticket.facility_id == facility_id, Ticket.department == dept,
                                            Ticket.day == date.today())).all()
    done = [t for t in today if t.status == "completed" and t.called_at]
    waits = [(t.called_at - t.entered_waiting_at).total_seconds() / 60 for t in done]
    return {"waiting": sum(t.status == "waiting" for t in today), "served": len(done),
            "no_shows": sum(t.no_show_count > 0 for t in today),
            "avg_wait_min": round(sum(waits) / len(waits), 1) if waits else None}
