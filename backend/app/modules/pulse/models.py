"""AraPulse tables: channels, messages, read markers, personal alerts, emergency pages (Pulse Codes).

patient_id columns carry no foreign key on purpose (like lab_orders): the mock-data reset deletes patients,
and a page or message must never block that or vanish with it."""
from sqlalchemy import (JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
                        false)
from sqlalchemy.orm import Mapped, mapped_column

from ...db import Base, uid, utcnow


class PulseChannel(Base):
    """broadcast ("All staff"), one per department, or a direct conversation between two staff."""
    __tablename__ = "pulse_channels"
    __table_args__ = (UniqueConstraint("facility_id", "key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    facility_id: Mapped[str] = mapped_column(String(36), ForeignKey("facilities.id"), index=True)
    kind: Mapped[str] = mapped_column(String(12))                     # broadcast | department | direct
    key: Mapped[str] = mapped_column(String(90))                      # "broadcast" | "dept:<id>" | "dm:<a>:<b>"
    name: Mapped[str] = mapped_column(String(120))
    department_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("departments.id"))
    member_a: Mapped[str | None] = mapped_column(String(36))          # direct only (sorted ids)
    member_b: Mapped[str | None] = mapped_column(String(36))
    created_at = mapped_column(DateTime, default=utcnow)
    last_message_at = mapped_column(DateTime, nullable=True)


class PulseRead(Base):
    """How far each person has read a channel (drives unread counts)."""
    __tablename__ = "pulse_reads"
    channel_id: Mapped[str] = mapped_column(String(36), ForeignKey("pulse_channels.id"), primary_key=True)
    staff_id: Mapped[str] = mapped_column(String(36), ForeignKey("staff.id"), primary_key=True, index=True)
    last_read_at = mapped_column(DateTime, default=utcnow)


class PulseMessage(Base):
    __tablename__ = "pulse_messages"
    __table_args__ = (Index("ix_pulse_messages_channel_created", "channel_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    facility_id: Mapped[str] = mapped_column(String(36), index=True)
    channel_id: Mapped[str] = mapped_column(String(36), ForeignKey("pulse_channels.id"))
    sender_id: Mapped[str | None] = mapped_column(String(36))          # NULL: written by the system
    kind: Mapped[str] = mapped_column(String(15), default="text")      # text | system | lab_order | prescription | page
    body: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(10), default="routine")  # routine | urgent | critical
    patient_id: Mapped[str | None] = mapped_column(String(36))
    payload = mapped_column(JSON, nullable=True)
    ack_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    acknowledged_by: Mapped[str | None] = mapped_column(String(36))
    acknowledged_at = mapped_column(DateTime, nullable=True)
    created_at = mapped_column(DateTime, default=utcnow)


class PulseAlert(Base):
    """A personal, actionable item for one person. Seen and acknowledged are separate states on purpose."""
    __tablename__ = "pulse_alerts"
    __table_args__ = (Index("ix_pulse_alerts_recipient_created", "recipient_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    facility_id: Mapped[str] = mapped_column(String(36), index=True)
    recipient_id: Mapped[str] = mapped_column(String(36), ForeignKey("staff.id"))
    # lab_result | lab_critical | critical_vitals | dispensed | page_escalated | system
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[str] = mapped_column(String(10), default="routine")
    ack_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    patient_id: Mapped[str | None] = mapped_column(String(36))
    visit_id: Mapped[str | None] = mapped_column(String(36))
    ref_id: Mapped[str | None] = mapped_column(String(36), index=True)  # lab order / visit / page it is about
    payload = mapped_column(JSON, nullable=True)
    created_at = mapped_column(DateTime, default=utcnow)
    seen_at = mapped_column(DateTime, nullable=True)
    acked_at = mapped_column(DateTime, nullable=True)
    acked_by: Mapped[str | None] = mapped_column(String(36))          # may be a colleague (shared alerts)
    escalated_at = mapped_column(DateTime, nullable=True)


class PulsePage(Base):
    """An emergency page (Pulse Code): paging -> acknowledged -> arrived -> resolved, or cancelled."""
    __tablename__ = "pulse_pages"
    __table_args__ = (Index("ix_pulse_pages_facility_status", "facility_id", "status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    facility_id: Mapped[str] = mapped_column(String(36), ForeignKey("facilities.id"))
    code: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(15), default="paging")
    ward_id: Mapped[str] = mapped_column(String(36), ForeignKey("wards.id"))
    bed: Mapped[str | None] = mapped_column(String(20))
    patient_id: Mapped[str | None] = mapped_column(String(36), index=True)
    note: Mapped[str | None] = mapped_column(Text)
    raised_by: Mapped[str] = mapped_column(String(36), ForeignKey("staff.id"))
    target_staff_id: Mapped[str | None] = mapped_column(String(36))
    target_department_id: Mapped[str | None] = mapped_column(String(36))
    channel_id: Mapped[str | None] = mapped_column(String(36))         # where the system lines are posted
    responder_id: Mapped[str | None] = mapped_column(String(36))
    eta_minutes: Mapped[int | None] = mapped_column(Integer)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    outcome: Mapped[str | None] = mapped_column(Text)
    created_at = mapped_column(DateTime, default=utcnow, index=True)
    acked_at = mapped_column(DateTime, nullable=True)
    arrived_at = mapped_column(DateTime, nullable=True)
    resolved_at = mapped_column(DateTime, nullable=True)               # also set on cancel
    escalated_at = mapped_column(DateTime, nullable=True)


class PulsePageTarget(Base):
    """Who a page reached and at which escalation level (0 = first wave)."""
    __tablename__ = "pulse_page_targets"
    page_id: Mapped[str] = mapped_column(String(36), ForeignKey("pulse_pages.id"), primary_key=True)
    staff_id: Mapped[str] = mapped_column(String(36), ForeignKey("staff.id"), primary_key=True, index=True)
    level: Mapped[int] = mapped_column(Integer, default=0)
    notified_at = mapped_column(DateTime, default=utcnow)
