from datetime import date

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import get_db
from ...realtime import hub
from ..core.models import Staff
from ..core.security import audit, require
from ..registration.models import Patient
from ..registration.service import age_years
from . import service
from .models import Journey, JourneyStep, Ticket

router = APIRouter(tags=["queue"])
DEPTS = {"TRIAGE", "OPD-GEN"}


def _view(t: Ticket, p: Patient) -> dict:
    return {"id": t.id, "ticket": t.ticket_number, "department": t.department, "status": t.status,
            "priority": t.priority_tier, "aged": t.priority_aged, "visit_id": t.visit_id,
            "patient_id": p.id, "patient_name": f"{p.surname} {p.first_name}",
            "patient_number": p.patient_number, "age": age_years(p.date_of_birth), "gender": p.gender,
            "waiting_since": t.entered_waiting_at.isoformat(), "called_at": t.called_at.isoformat() if t.called_at else None,
            "counter": t.counter_name, "no_show_count": t.no_show_count}


def _dept(dept: str) -> str:
    dept = dept.upper()
    if dept not in DEPTS:
        raise HTTPException(404, "Unknown queue")
    return dept


@router.get("/queues/{dept}")
def list_queue(dept: str, staff: Staff = Depends(require("reception", "nurse", "doctor", "admin")),
               db: Session = Depends(get_db)):
    dept = _dept(dept)
    order = service.waiting_tickets(db, staff.facility_id, dept)
    active = db.scalars(select(Ticket).where(Ticket.facility_id == staff.facility_id, Ticket.department == dept,
                                             Ticket.day == date.today(),
                                             Ticket.status.in_(("called", "in_service", "no_show")))
                        .order_by(Ticket.called_at)).all()
    db.commit()  # persists aging promotions
    pats = {p.id: p for p in db.scalars(select(Patient).where(Patient.id.in_([t.patient_id for t in order + active]))).all()}
    return {"department": dept, "active": [_view(t, pats[t.patient_id]) for t in active],
            "waiting": [_view(t, pats[t.patient_id]) for t in order], "stats": service.stats(db, staff.facility_id, dept)}


class CallIn(BaseModel):
    counter: str = "Room 1"


@router.post("/queues/{dept}/call-next")
def call_next(dept: str, body: CallIn, staff: Staff = Depends(require("nurse", "doctor", "admin")),
              db: Session = Depends(get_db)):
    dept = _dept(dept)
    if dept == "OPD-GEN" and staff.role == "nurse" or dept == "TRIAGE" and staff.role == "doctor":
        raise HTTPException(403, "Wrong queue for your role")
    t = service.pick_next(db, staff.facility_id, dept)
    if not t:
        db.commit()
        raise HTTPException(404, "Nobody is waiting")
    service.call_ticket(db, t, body.counter)
    p = db.get(Patient, t.patient_id)
    audit(db, staff, "call", "ticket", t.id, p.id)
    db.commit()
    return _view(t, p)


def _ticket(db: Session, staff: Staff, ticket_id: str) -> Ticket:
    t = db.get(Ticket, ticket_id)
    if not t or t.facility_id != staff.facility_id:
        raise HTTPException(404, "Ticket not found")
    return t


@router.post("/tickets/{ticket_id}/{action}")
def ticket_action(ticket_id: str, action: str,
                  staff: Staff = Depends(require("reception", "nurse", "doctor", "admin")),
                  db: Session = Depends(get_db)):
    t = _ticket(db, staff, ticket_id)
    allowed = {"arrived": ("called",), "no-show": ("called",), "rejoin": ("no_show",),
               "cancel": ("waiting", "called", "no_show", "in_service")}
    if action not in allowed:
        raise HTTPException(404, "Unknown action")
    if t.status not in allowed[action]:
        raise HTTPException(409, f"Cannot {action} a ticket that is '{t.status}'")
    {"arrived": service.mark_arrived, "no-show": service.mark_no_show, "rejoin": service.rejoin,
     "cancel": lambda d, x: service.cancel_ticket(d, x, "cancelled by staff")}[action](db, t)
    db.commit()
    return _view(t, db.get(Patient, t.patient_id))


@router.get("/visits/{visit_id}/journey")
def journey(visit_id: str, staff: Staff = Depends(require("reception", "nurse", "doctor", "admin")),
            db: Session = Depends(get_db)):
    j = db.scalar(select(Journey).where(Journey.visit_id == visit_id, Journey.facility_id == staff.facility_id))
    if not j:
        raise HTTPException(404, "No journey")
    steps = db.scalars(select(JourneyStep).where(JourneyStep.journey_id == j.id).order_by(JourneyStep.step_order)).all()
    return {"status": j.status, "steps": [{"order": s.step_order, "department": s.department,
                                           "status": s.status, "created_by": s.created_by, "note": s.note} for s in steps]}


@router.get("/display/{dept}")
def tv_display(dept: str, db: Session = Depends(get_db)):
    """Public (waiting-room TV). Ticket numbers + initials only -- no PHI."""
    dept = _dept(dept)
    from ..core.models import Facility
    fac = db.scalar(select(Facility))
    fid = fac.id
    called = db.scalars(select(Ticket).where(Ticket.facility_id == fid, Ticket.department == dept,
                                             Ticket.day == date.today(), Ticket.status.in_(("called", "in_service")))
                        .order_by(Ticket.called_at.desc())).all()
    waiting = service.waiting_tickets(db, fid, dept)
    pats = {p.id: p for p in db.scalars(select(Patient).where(Patient.id.in_([t.patient_id for t in called + waiting]))).all()}

    def short(t):
        p = pats[t.patient_id]
        return {"ticket": t.ticket_number, "priority": t.priority_tier, "status": t.status,
                "counter": t.counter_name, "who": f"{p.first_name[:1]}. {p.surname.upper()}"}
    st = service.stats(db, fid, dept)
    return {"facility": fac.name, "department": dept, "now_serving": [short(t) for t in called[:6]],
            "next_up": [short(t) for t in waiting[:6]], "stats": st}


@router.websocket("/ws/queue")
async def ws_queue(ws: WebSocket):
    hub.loop = __import__("asyncio").get_running_loop()
    await hub.join("queue", ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.leave("queue", ws)
