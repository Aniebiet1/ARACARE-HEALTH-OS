from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...db import Base, uid, utcnow


class Facility(Base):
    __tablename__ = "facilities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    state_code: Mapped[str] = mapped_column(String(3))


class Staff(Base):
    __tablename__ = "staff"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    facility_id: Mapped[str] = mapped_column(String(36), ForeignKey("facilities.id"), index=True)
    username: Mapped[str] = mapped_column(String(60), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))  # reception | nurse | doctor | admin
    password_hash: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AuditLog(Base):
    """Append-only: every view/create/sign of sensitive data (NDPA 2023)."""
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    facility_id: Mapped[str] = mapped_column(String(36), index=True)
    staff_id: Mapped[str | None] = mapped_column(String(36))
    patient_id: Mapped[str | None] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(40))
    record_type: Mapped[str] = mapped_column(String(40))
    record_id: Mapped[str | None] = mapped_column(String(36))
    detail: Mapped[str | None] = mapped_column(Text)
    at = mapped_column(DateTime, default=utcnow, index=True)


class Consent(Base):
    """Immutable. Withdrawal = a new row with granted=False, never an update."""
    __tablename__ = "patient_consents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    facility_id: Mapped[str] = mapped_column(String(36), index=True)
    patient_id: Mapped[str] = mapped_column(String(36), index=True)
    consent_type: Mapped[str] = mapped_column(String(30))  # photo | voice_scribe | sms | data_sharing
    granted: Mapped[bool] = mapped_column(Boolean)
    method: Mapped[str] = mapped_column(String(30), default="verbal_confirmed")
    recorded_by: Mapped[str | None] = mapped_column(String(36))
    at = mapped_column(DateTime, default=utcnow)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    facility_id: Mapped[str] = mapped_column(String(36), index=True)
    event_type: Mapped[str] = mapped_column(String(60), index=True)
    payload = mapped_column(JSON)
    created_at = mapped_column(DateTime, default=utcnow, index=True)
    synced_at = mapped_column(DateTime, nullable=True)  # set by the future cloud-sync worker


class Message(Base):
    """Outbound SMS/WhatsApp queue. Dispatcher is a stub in this release."""
    __tablename__ = "outbound_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    facility_id: Mapped[str] = mapped_column(String(36), index=True)
    patient_id: Mapped[str | None] = mapped_column(String(36))
    to_phone: Mapped[str] = mapped_column(String(30))
    channel: Mapped[str] = mapped_column(String(10), default="sms")
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="queued")  # queued -> sent when gateway wired
    created_at = mapped_column(DateTime, default=utcnow)
