from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...db import utcnow
from ..core.models import Consent, Staff
from ..core.security import audit
from ..ehr.models import Icd10
from .models import ScribeSession


def has_voice_consent(db: Session, patient_id: str) -> bool:
    latest = db.scalar(select(Consent).where(Consent.patient_id == patient_id, Consent.consent_type == "voice_scribe")
                       .order_by(Consent.at.desc()))
    return bool(latest and latest.granted)


def map_icd10(db: Session, terms: list[str]) -> list[dict]:
    """Suggestion only. Each free-text term -> best ICD-10 matches the doctor can accept."""
    out, seen = [], set()
    for term in terms:
        t = term.strip().lower()
        if not t:
            continue
        like = f"%{t}%"
        rows = db.scalars(select(Icd10).where(or_(Icd10.description.ilike(like), Icd10.keywords.ilike(like))).limit(3)).all()
        for r in rows:
            if r.code not in seen:
                seen.add(r.code)
                out.append({"code": r.code, "description": r.description, "matched": term})
    return out


def mark_accepted(db: Session, session_id: str, staff: Staff):
    s = db.get(ScribeSession, session_id)
    if s and s.status == "ai_draft":
        s.status, s.accepted_at = "accepted", utcnow()
        audit(db, staff, "scribe_accepted", "scribe_session", s.id, s.patient_id)
