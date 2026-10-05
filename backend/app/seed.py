import logging

from sqlalchemy import select

from .config import settings
from .db import SessionLocal
from .modules.core.models import Facility, Staff
from .modules.core.security import hash_password
from .modules.ehr.clinical_rules import ICD10_SEED
from .modules.ehr.models import Icd10

log = logging.getLogger("aracare.seed")
DEMO_STAFF = [("reception", "Amaka Ibrahim", "reception"), ("nurse", "Nurse Joy Okafor", "nurse"),
              ("doctor", "Dr. Emeka Eze", "doctor"), ("admin", "Admin Bisi Adeyemi", "admin")]


def seed(password: str = "demo123"):
    """Idempotent. Development gets demo accounts; production gets one admin from ARACARE_ADMIN_PASSWORD."""
    with SessionLocal() as db:
        fac = db.scalar(select(Facility))
        if not fac:
            fac = Facility(name=settings.facility_name, state_code=settings.state_code)
            db.add(fac)
            db.flush()
        if not db.scalar(select(Staff)):
            if settings.is_production:
                if not settings.admin_password:
                    raise RuntimeError("No staff accounts exist. Set ARACARE_ADMIN_PASSWORD to create the first "
                                       "admin (username 'admin'); you will be asked to change it at first login.")
                db.add(Staff(facility_id=fac.id, username="admin", full_name="Administrator", role="admin",
                             password_hash=hash_password(settings.admin_password), must_change_password=True))
                log.warning("Created first admin account 'admin'. Remove ARACARE_ADMIN_PASSWORD from the environment.")
            else:
                for username, name, role in DEMO_STAFF:
                    db.add(Staff(facility_id=fac.id, username=username, full_name=name, role=role,
                                 password_hash=hash_password(password)))
        known = set(db.scalars(select(Icd10.code)).all())
        for code, desc, kw in ICD10_SEED:      # new codes shipped in an update are added on next start
            if code not in known:
                db.add(Icd10(code=code, description=desc, keywords=kw))
        db.commit()
