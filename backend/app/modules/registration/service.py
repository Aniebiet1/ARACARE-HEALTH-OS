import difflib
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...config import settings
from .models import Patient


def age_years(dob: date, today: date | None = None) -> int:
    today = today or date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def category_for(dob: date) -> str:
    a = age_years(dob)
    return "infant" if a < 1 else "child" if a < 18 else "adult"


def next_patient_number(db: Session, facility_id: str, state_code: str) -> str:
    year = date.today().year
    prefix = f"ARC-{state_code}-{year}-"
    count = db.scalar(select(func.count()).select_from(Patient)
                      .where(Patient.facility_id == facility_id, Patient.patient_number.like(prefix + "%"))) or 0
    return f"{prefix}{count + 1:06d}"


def normalise_phone(p: str) -> str:
    digits = "".join(c for c in p if c.isdigit())
    if digits.startswith("234") and len(digits) == 13:
        digits = "0" + digits[3:]
    return digits


def _name_score(q: str, p: Patient) -> float:
    full = f"{p.surname} {p.first_name} {p.middle_name or ''}".lower()
    best = 0.0
    for tok in q.lower().split():
        # Nigerian spellings vary a lot: fuzzy-match each token against every name part
        parts = full.split()
        s = max([difflib.SequenceMatcher(None, tok, part).ratio() for part in parts] or [0])
        if any(part.startswith(tok) for part in parts):
            s = max(s, 0.9)
        best += s
    return best / max(len(q.split()), 1)


def search(db: Session, facility_id: str, q: str, limit: int = 15) -> list[Patient]:
    q = q.strip()
    if not q:
        return []
    digits = normalise_phone(q)
    if len(digits) >= 6:
        rows = db.scalars(select(Patient).where(
            Patient.facility_id == facility_id, Patient.is_active,
            or_(Patient.phone.like(f"%{digits[-9:]}%"), Patient.patient_number.ilike(f"%{q}%")))).all()
        if rows:
            return rows[:limit]
    if q.upper().startswith("ARC-"):
        return list(db.scalars(select(Patient).where(Patient.patient_number.ilike(f"%{q}%"))).all())[:limit]
    everyone = db.scalars(select(Patient).where(Patient.facility_id == facility_id, Patient.is_active)).all()
    scored = sorted(((_name_score(q, p), p) for p in everyone), key=lambda t: t[0], reverse=True)
    return [p for s, p in scored if s >= 0.6][:limit]


def find_possible_duplicates(db: Session, facility_id: str, surname: str, first_name: str,
                             phone: str, dob: date) -> list[Patient]:
    out = []
    digits = normalise_phone(phone)
    for p in db.scalars(select(Patient).where(Patient.facility_id == facility_id, Patient.is_active)).all():
        same_phone = normalise_phone(p.phone) == digits
        same_dob = p.date_of_birth == dob
        name = difflib.SequenceMatcher(None, f"{surname} {first_name}".lower(),
                                       f"{p.surname} {p.first_name}".lower()).ratio()
        if (same_phone and name > 0.6) or (same_dob and name > 0.8):
            out.append(p)
    return out


def card_text(p: Patient) -> str:
    return (f"Your AraCare Patient ID: {p.patient_number}\n"
            f"Name: {p.surname.upper()} {p.first_name.upper()}\n"
            f"Hospital: {settings.facility_name}\n\n"
            "Show this message or give your phone number at reception on your next visit. "
            "Do not share your Patient ID with others.")
