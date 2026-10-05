from sqlalchemy import select

from .config import settings
from .db import SessionLocal
from .modules.core.models import Facility, Staff
from .modules.core.security import hash_password
from .modules.ehr.clinical_rules import ICD10_SEED
from .modules.ehr.models import Icd10

DEMO_STAFF = [("reception", "Amaka Ibrahim", "reception"), ("nurse", "Nurse Joy Okafor", "nurse"),
              ("doctor", "Dr. Emeka Eze", "doctor"), ("admin", "Admin Bisi Adeyemi", "admin")]


def seed(password: str = "demo123"):
    with SessionLocal() as db:
        fac = db.scalar(select(Facility))
        if not fac:
            fac = Facility(name=settings.facility_name, state_code=settings.state_code)
            db.add(fac)
            db.flush()
        if not db.scalar(select(Staff)):
            for username, name, role in DEMO_STAFF:
                db.add(Staff(facility_id=fac.id, username=username, full_name=name, role=role,
                             password_hash=hash_password(password)))
        if not db.scalar(select(Icd10)):
            for code, desc, kw in ICD10_SEED:
                db.add(Icd10(code=code, description=desc, keywords=kw))
        db.commit()
