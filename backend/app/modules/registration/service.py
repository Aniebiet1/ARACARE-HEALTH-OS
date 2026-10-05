import difflib
import re
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...config import settings
from ...db import local_today
from ..core.security import next_counter
from .models import Patient


def age_years(dob: date, today: date | None = None) -> int:
    today = today or local_today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def category_for(dob: date) -> str:
    a = age_years(dob)
    return "infant" if a < 1 else "child" if a < 18 else "adult"


def next_patient_number(db: Session, state_code: str) -> str:
    """ARC-LAG-2026-000001. The counter is keyed by the prefix (not the facility) because patient numbers are
    globally unique: two facilities in one state share the sequence. Locked, so concurrent registrations
    never collide."""
    prefix = f"ARC-{state_code}-{local_today().year}-"
    n = next_counter(db, f"patient_number:{prefix}")
    # databases from before the counter existed: never reissue a number already taken
    while db.scalar(select(Patient.id).where(Patient.patient_number == f"{prefix}{n:06d}")):
        n = next_counter(db, f"patient_number:{prefix}")
    return f"{prefix}{n:06d}"


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
    number = parse_code(q)      # a scanned receipt typed into the search box by a handheld scanner
    if number:
        return list(db.scalars(select(Patient).where(Patient.facility_id == facility_id,
                                                     Patient.patient_number == number)).all())
    digits = normalise_phone(q)
    if len(digits) >= 6:
        rows = db.scalars(select(Patient).where(
            Patient.facility_id == facility_id, Patient.is_active,
            or_(Patient.phone.like(f"%{digits[-9:]}%"), Patient.patient_number.ilike(f"%{q}%")))).all()
        if rows:
            return rows[:limit]
    if q.upper().startswith("ARC-"):
        return list(db.scalars(select(Patient).where(Patient.facility_id == facility_id,
                                                     Patient.patient_number.ilike(f"%{q}%")).limit(limit)).all())
    scored = sorted(((_name_score(q, p), p) for p in _name_candidates(db, facility_id, q)),
                    key=lambda t: t[0], reverse=True)
    return [p for s, p in scored if s >= 0.6][:limit]


def _name_candidates(db: Session, facility_id: str, q: str, cap: int = 3000) -> list[Patient]:
    """Narrow in SQL before fuzzy scoring in Python, so search stays fast with tens of thousands of patients.
    A name part must share its first letter with a query token: that keeps the common Nigerian spelling
    variants (Okonkwo/Okonkow, Babatunde/Babtunde) while skipping most of the table."""
    tokens = [t for t in q.lower().split() if len(t) >= 2]
    if not tokens:
        return []
    conds = []
    for tok in tokens:
        like = f"{tok[0]}%"
        conds += [func.lower(Patient.surname).like(like), func.lower(Patient.first_name).like(like),
                  func.lower(Patient.middle_name).like(like)]
    return list(db.scalars(select(Patient).where(Patient.facility_id == facility_id, Patient.is_active, or_(*conds))
                           .order_by(Patient.created_at.desc()).limit(cap)).all())


def find_possible_duplicates(db: Session, facility_id: str, surname: str, first_name: str,
                             phone: str, dob: date) -> list[Patient]:
    out = []
    digits = normalise_phone(phone)
    # both duplicate rules need the same phone or the same date of birth, so let the database narrow it down
    candidates = db.scalars(select(Patient).where(Patient.facility_id == facility_id, Patient.is_active,
                                                  or_(Patient.phone == digits, Patient.date_of_birth == dob))).all()
    for p in candidates:
        same_phone = normalise_phone(p.phone) == digits
        same_dob = p.date_of_birth == dob
        name = difflib.SequenceMatcher(None, f"{surname} {first_name}".lower(),
                                       f"{p.surname} {p.first_name}".lower()).ratio()
        if (same_phone and name > 0.6) or (same_dob and name > 0.8):
            out.append(p)
    return out


QR_PREFIX = "ARACARE:"
_NUMBER = re.compile(r"ARC-[A-Z]{2,3}-\d{4}-\d{6,}", re.I)


def qr_payload(p: Patient) -> str:
    """What the receipt's QR code holds: only the patient number, nothing clinical. A phone camera that scans it
    shows text, not a link, and staff still see the photo and details before checking the patient in."""
    return f"{QR_PREFIX}{p.patient_number}"


def parse_code(code: str) -> str | None:
    """Patient number from a scanned QR code, a handheld scanner's keystrokes or a typed number. Searching rather
    than matching the whole string tolerates scanners that add prefixes, suffixes or a different keyboard layout
    for the ':' separator."""
    m = _NUMBER.search(code or "")
    return m.group(0).upper() if m else None


def card_text(p: Patient, facility_name: str | None = None) -> str:
    return (f"Your AraCare Patient ID: {p.patient_number}\n"
            f"Name: {p.surname.upper()} {p.first_name.upper()}\n"
            f"Hospital: {facility_name or settings.facility_name}\n\n"
            "Show this message or give your phone number at reception on your next visit. "
            "Do not share your Patient ID with others.")
