"""Queue module's reactions to events from other modules (the only coupling to EHR)."""
from sqlalchemy import select

from ...events import subscribe
from . import service
from .models import Journey, Ticket


def _open_ticket(db, visit_id, dept):
    return db.scalar(select(Ticket).where(Ticket.visit_id == visit_id, Ticket.department == dept,
                                          Ticket.status.in_(service.OPEN)))


@subscribe("TriageCompleted")
def on_triage_completed(db, ev):
    p = ev.payload
    t = _open_ticket(db, p["visit_id"], "TRIAGE")
    if not t:
        return
    # nurse's triage assessment sets the doctor-queue priority
    t.priority_tier = p.get("triage_priority", t.priority_tier)
    t.status, t.completed_at = "completed", service.utcnow()
    step = db.get(service.JourneyStep, t.journey_step_id)
    step.status, step.completed_at = "completed", service.utcnow()
    service.publish(db, "StepCompleted", {"ticket": t.ticket_number, "department": "TRIAGE", "visit_id": t.visit_id},
                    t.facility_id, room="queue")
    service._activate_opd(db, t, priority=p.get("triage_priority"))


@subscribe("NoteSigned")
def on_note_signed(db, ev):
    p = ev.payload
    if p.get("note_type") != "soap":
        return
    t = _open_ticket(db, p["visit_id"], "OPD-GEN")
    if t:
        service.complete_ticket(db, t)


@subscribe("LabOrdered")
def on_lab_ordered(db, ev):
    _deferred_step(db, ev, "LAB")


@subscribe("Prescribed")
def on_prescribed(db, ev):
    _deferred_step(db, ev, "PHARM")


def _deferred_step(db, ev, dept):
    j = db.scalar(select(Journey).where(Journey.visit_id == ev.payload["visit_id"]))
    if not j or j.status != "in_progress":
        return
    from .models import JourneyStep
    exists = db.scalar(select(JourneyStep).where(JourneyStep.journey_id == j.id, JourneyStep.department == dept))
    if not exists:   # one step per department per visit
        service.add_step(db, j, dept, created_by="doctor", note=ev.payload.get("summary"),
                         visit_id=j.visit_id)
