from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ...db import Base, uid, utcnow


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)  # global id (cross-facility later)
    facility_id: Mapped[str] = mapped_column(String(36), ForeignKey("facilities.id"), index=True)
    patient_number: Mapped[str] = mapped_column(String(30), unique=True)        # ARC-LAG-2026-000001
    surname: Mapped[str] = mapped_column(String(80), index=True)
    first_name: Mapped[str] = mapped_column(String(80))
    middle_name: Mapped[str | None] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(30), index=True)
    date_of_birth = mapped_column(Date)
    gender: Mapped[str] = mapped_column(String(10))
    category: Mapped[str] = mapped_column(String(10))                            # adult | child | infant
    nok_name: Mapped[str | None] = mapped_column(String(120))
    nok_phone: Mapped[str | None] = mapped_column(String(30))
    state_of_origin: Mapped[str | None] = mapped_column(String(40))
    hmo_provider: Mapped[str | None] = mapped_column(String(80))
    hmo_number: Mapped[str | None] = mapped_column(String(60))
    blood_group: Mapped[str | None] = mapped_column(String(5))
    photo_path: Mapped[str | None] = mapped_column(String(300))                  # vault 3 (biometric)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    registered_by: Mapped[str | None] = mapped_column(String(36))
    created_at = mapped_column(DateTime, default=utcnow)


class Visit(Base):
    __tablename__ = "visits"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    facility_id: Mapped[str] = mapped_column(String(36), ForeignKey("facilities.id"), index=True)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patients.id"), index=True)
    visit_type: Mapped[str] = mapped_column(String(20))   # new_complaint | follow_up | anc | emergency
    payment_track: Mapped[str] = mapped_column(String(20), default="out_of_pocket")
    status: Mapped[str] = mapped_column(String(20), default="checked_in")  # checked_in | in_progress | completed | abandoned
    checked_in_at = mapped_column(DateTime, default=utcnow)
    checked_in_by: Mapped[str | None] = mapped_column(String(36))
