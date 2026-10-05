from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...db import Base, uid, utcnow


class Icd10(Base):
    __tablename__ = "icd10_codes"
    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    description: Mapped[str] = mapped_column(String(200))
    keywords: Mapped[str] = mapped_column(String(300), default="")


class AllergyRecord(Base):
    __tablename__ = "allergy_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patients.id"), index=True)
    allergen_name: Mapped[str] = mapped_column(String(100))
    drug_class: Mapped[str | None] = mapped_column(String(50))  # penicillin | sulfonamide | nsaid | ...
    reaction: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(15), default="moderate")
    recorded_by: Mapped[str | None] = mapped_column(String(36))
    recorded_at = mapped_column(DateTime, default=utcnow)


class Vitals(Base):
    __tablename__ = "vitals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    visit_id: Mapped[str] = mapped_column(String(36), ForeignKey("visits.id"), index=True)
    patient_id: Mapped[str] = mapped_column(String(36), index=True)
    recorded_by: Mapped[str] = mapped_column(String(36))
    recorded_at = mapped_column(DateTime, default=utcnow)
    bp_systolic: Mapped[int | None] = mapped_column(Integer)
    bp_diastolic: Mapped[int | None] = mapped_column(Integer)
    pulse_rate: Mapped[int | None] = mapped_column(Integer)
    respiratory_rate: Mapped[int | None] = mapped_column(Integer)
    temperature: Mapped[float | None] = mapped_column(Float)
    spo2: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    height_cm: Mapped[float | None] = mapped_column(Float)
    bmi: Mapped[float | None] = mapped_column(Float)
    pain_score: Mapped[int | None] = mapped_column(Integer)
    chief_complaint: Mapped[str | None] = mapped_column(Text)
    triage_priority: Mapped[str] = mapped_column(String(12), default="NORMAL")
    flags = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | ai_scribe (clinician-confirmed)


class ClinicalNote(Base):
    __tablename__ = "clinical_notes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    visit_id: Mapped[str] = mapped_column(String(36), ForeignKey("visits.id"), index=True)
    patient_id: Mapped[str] = mapped_column(String(36), index=True)
    note_type: Mapped[str] = mapped_column(String(20), default="soap")
    template_used: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(10), default="draft")  # draft | signed
    subjective: Mapped[str] = mapped_column(Text, default="")
    objective: Mapped[str] = mapped_column(Text, default="")
    assessment: Mapped[str] = mapped_column(Text, default="")
    plan: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | ai_scribe
    scribe_session_id: Mapped[str | None] = mapped_column(String(36))
    authored_by: Mapped[str] = mapped_column(String(36))
    signed_by: Mapped[str | None] = mapped_column(String(36))
    signed_at = mapped_column(DateTime, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64))   # sha256 of the signed content
    created_at = mapped_column(DateTime, default=utcnow)


class NoteAddendum(Base):
    __tablename__ = "note_addenda"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    note_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinical_notes.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    added_by: Mapped[str] = mapped_column(String(36))
    added_at = mapped_column(DateTime, default=utcnow)


class Diagnosis(Base):
    __tablename__ = "diagnoses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    note_id: Mapped[str] = mapped_column(String(36), ForeignKey("clinical_notes.id"), index=True)
    visit_id: Mapped[str] = mapped_column(String(36), index=True)
    patient_id: Mapped[str] = mapped_column(String(36), index=True)
    icd10_code: Mapped[str] = mapped_column(String(10))
    icd10_description: Mapped[str] = mapped_column(String(200))
    diagnosis_type: Mapped[str] = mapped_column(String(15), default="primary")
    status: Mapped[str] = mapped_column(String(10), default="active")
    diagnosed_by: Mapped[str] = mapped_column(String(36))
    diagnosed_at = mapped_column(DateTime, default=utcnow)


class LabOrder(Base):
    __tablename__ = "lab_orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    visit_id: Mapped[str] = mapped_column(String(36), index=True)
    patient_id: Mapped[str] = mapped_column(String(36), index=True)
    ordered_by: Mapped[str] = mapped_column(String(36))
    test_code: Mapped[str] = mapped_column(String(20))
    test_name: Mapped[str] = mapped_column(String(100))
    priority: Mapped[str] = mapped_column(String(10), default="routine")
    status: Mapped[str] = mapped_column(String(15), default="ordered")  # ordered | sent (lab module deferred)
    ordered_at = mapped_column(DateTime, default=utcnow)


class MedicationOrder(Base):
    __tablename__ = "medication_orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    visit_id: Mapped[str] = mapped_column(String(36), index=True)
    patient_id: Mapped[str] = mapped_column(String(36), index=True)
    ordered_by: Mapped[str] = mapped_column(String(36))
    drug_name: Mapped[str] = mapped_column(String(100))
    dose: Mapped[str | None] = mapped_column(String(60))
    frequency: Mapped[str | None] = mapped_column(String(60))
    duration_days: Mapped[int | None] = mapped_column(Integer)
    route: Mapped[str] = mapped_column(String(10), default="oral")
    instructions: Mapped[str | None] = mapped_column(Text)
    allergy_override_reason: Mapped[str | None] = mapped_column(Text)  # set only when a conflict was knowingly overridden
    status: Mapped[str] = mapped_column(String(15), default="ordered")  # ordered | sent (pharmacy module deferred)
    ordered_at = mapped_column(DateTime, default=utcnow)
