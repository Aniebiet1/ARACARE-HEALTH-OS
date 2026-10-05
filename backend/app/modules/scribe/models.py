from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ...db import Base, uid, utcnow


class ScribeSession(Base):
    """One dictation. The transcript + draft are kept for audit; AUDIO IS NEVER STORED."""
    __tablename__ = "scribe_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    facility_id: Mapped[str] = mapped_column(String(36), index=True)
    visit_id: Mapped[str] = mapped_column(String(36), index=True)
    patient_id: Mapped[str] = mapped_column(String(36), index=True)
    staff_id: Mapped[str] = mapped_column(String(36))
    role: Mapped[str] = mapped_column(String(10))            # nurse | doctor
    transcript: Mapped[str] = mapped_column(Text)
    draft = mapped_column(JSON)
    dropped = mapped_column(JSON, default=list)               # fields removed by the grounding check
    engine = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(12), default="ai_draft")  # ai_draft | accepted | discarded
    created_at = mapped_column(DateTime, default=utcnow)
    accepted_at = mapped_column(DateTime, nullable=True)
