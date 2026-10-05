from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Boolean, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ...db import Base, uid, utcnow


class QueueState(Base):
    """Per facility/department/day: ticket sequence + weighted-fair-queuing counters."""
    __tablename__ = "queue_states"
    __table_args__ = (UniqueConstraint("facility_id", "department", "day"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    facility_id: Mapped[str] = mapped_column(String(36), index=True)
    department: Mapped[str] = mapped_column(String(20))
    day = mapped_column(Date)
    last_seq: Mapped[int] = mapped_column(Integer, default=0)
    p1_streak: Mapped[int] = mapped_column(Integer, default=0)   # HIGH served since last NORMAL
    p2_streak: Mapped[int] = mapped_column(Integer, default=0)   # NORMAL served since last FOLLOW_UP


class Journey(Base):
    __tablename__ = "journeys"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    visit_id: Mapped[str] = mapped_column(String(36), ForeignKey("visits.id"), unique=True)
    patient_id: Mapped[str] = mapped_column(String(36), index=True)
    facility_id: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(15), default="in_progress")  # in_progress | completed | abandoned
    started_at = mapped_column(DateTime, default=utcnow)
    completed_at = mapped_column(DateTime, nullable=True)


class JourneyStep(Base):
    __tablename__ = "journey_steps"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    journey_id: Mapped[str] = mapped_column(String(36), ForeignKey("journeys.id"), index=True)
    step_order: Mapped[int] = mapped_column(Integer)
    department: Mapped[str] = mapped_column(String(20))
    # pending | active | completed | abandoned | deferred (department module not in this release)
    status: Mapped[str] = mapped_column(String(15), default="pending")
    created_by: Mapped[str] = mapped_column(String(15), default="system")
    note: Mapped[str | None] = mapped_column(Text)
    created_at = mapped_column(DateTime, default=utcnow)
    completed_at = mapped_column(DateTime, nullable=True)


class Ticket(Base):
    __tablename__ = "queue_tickets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    facility_id: Mapped[str] = mapped_column(String(36), index=True)
    department: Mapped[str] = mapped_column(String(20), index=True)
    day = mapped_column(Date, index=True)
    journey_step_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("journey_steps.id"))
    visit_id: Mapped[str] = mapped_column(String(36), index=True)
    patient_id: Mapped[str] = mapped_column(String(36), index=True)
    ticket_number: Mapped[str] = mapped_column(String(20))   # TRI-007
    sequence_number: Mapped[int] = mapped_column(Integer)
    priority_tier: Mapped[str] = mapped_column(String(12), default="NORMAL")
    priority_aged: Mapped[bool] = mapped_column(Boolean, default=False)
    # waiting | called | in_service | completed | no_show | cancelled | transferred
    status: Mapped[str] = mapped_column(String(12), default="waiting", index=True)
    issued_at = mapped_column(DateTime, default=utcnow)
    entered_waiting_at = mapped_column(DateTime, default=utcnow)
    called_at = mapped_column(DateTime, nullable=True)
    confirmed_at = mapped_column(DateTime, nullable=True)
    completed_at = mapped_column(DateTime, nullable=True)
    no_show_at = mapped_column(DateTime, nullable=True)
    no_show_count: Mapped[int] = mapped_column(Integer, default=0)
    counter_name: Mapped[str | None] = mapped_column(String(60))
    __table_args__ = (UniqueConstraint("facility_id", "department", "day", "sequence_number"),)
