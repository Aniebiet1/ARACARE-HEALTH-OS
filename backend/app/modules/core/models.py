from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, false, true
from sqlalchemy.orm import Mapped, mapped_column

from ...db import Base, uid, utcnow


class Facility(Base):
    __tablename__ = "facilities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    state_code: Mapped[str] = mapped_column(String(3))
    # branding printed on patient receipts
    address: Mapped[str | None] = mapped_column(String(300))
    phone: Mapped[str | None] = mapped_column(String(60))
    email: Mapped[str | None] = mapped_column(String(120))
    motto: Mapped[str | None] = mapped_column(String(160))
    logo_path: Mapped[str | None] = mapped_column(String(300))
    # hospital profile, captured by the admin's first-run onboarding
    facility_type: Mapped[str | None] = mapped_column(String(30))     # general | teaching | specialist | primary | clinic
    ownership: Mapped[str | None] = mapped_column(String(20))         # federal | state | private | mission | ngo
    license_number: Mapped[str | None] = mapped_column(String(60))    # state MoH / HEFAMAA registration
    city: Mapped[str | None] = mapped_column(String(80))
    lga: Mapped[str | None] = mapped_column(String(80))
    emergency_phone: Mapped[str | None] = mapped_column(String(60))
    website: Mapped[str | None] = mapped_column(String(160))
    bed_capacity: Mapped[int | None] = mapped_column(Integer)
    open_24h: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    onboarded_at = mapped_column(DateTime, nullable=True)            # NULL: admin still sees the setup wizard
    onboarded_by: Mapped[str | None] = mapped_column(String(36))


class Department(Base):
    """A unit staff belong to and AraPulse routes to: clinical, ward, diagnostic, support or admin."""
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("facility_id", "code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    facility_id: Mapped[str] = mapped_column(String(36), ForeignKey("facilities.id"), index=True)
    code: Mapped[str] = mapped_column(String(20))                     # EMERG, MED, LAB, PHARM ...
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(15), default="clinical")  # clinical | ward | diagnostic | support | admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at = mapped_column(DateTime, default=utcnow)


class Ward(Base):
    """A physical location an emergency page points to (Ward 3, A&E Bay, ICU)."""
    __tablename__ = "wards"
    __table_args__ = (UniqueConstraint("facility_id", "code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    facility_id: Mapped[str] = mapped_column(String(36), ForeignKey("facilities.id"), index=True)
    department_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("departments.id"))
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    floor: Mapped[str | None] = mapped_column(String(40))
    bed_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())


class Staff(Base):
    __tablename__ = "staff"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    facility_id: Mapped[str] = mapped_column(String(36), ForeignKey("facilities.id"), index=True)
    username: Mapped[str] = mapped_column(String(60), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))  # reception | nurse | doctor | lab | pharmacy | admin
    position: Mapped[str | None] = mapped_column(String(80))          # "Consultant Physician", "Matron", ...
    department_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("departments.id"), index=True)
    phone: Mapped[str | None] = mapped_column(String(30))
    on_duty: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())  # AraPulse paging target
    password_hash: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # bumped on password change/reset or deactivation: every token issued before is rejected
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    failed_logins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    locked_until = mapped_column(DateTime, nullable=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


class Counter(Base):
    """Named gap-free sequences (patient numbers). Incremented under a row lock, never by COUNT(*)."""
    __tablename__ = "counters"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)


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
