import logging

from sqlalchemy import select

from .config import settings
from .db import SessionLocal
from .modules.core.models import Department, Facility, Staff
from .modules.core.security import hash_password
from .modules.ehr.clinical_rules import ICD10_SEED
from .modules.ehr.models import Icd10
from .modules.org.catalogue import SUGGESTED, create_suggested

log = logging.getLogger("aracare.seed")
# (username, name, role, position, department code)
DEMO_STAFF = [("reception", "Amaka Ibrahim", "reception", "Front Desk Officer", "REC"),
              ("nurse", "Nurse Joy Okafor", "nurse", "Nursing Officer", "GOPD"),
              ("doctor", "Dr. Emeka Eze", "doctor", "Medical Officer", "GOPD"),
              ("lab", "Chiamaka Nwosu", "lab", "Medical Laboratory Scientist", "LAB"),
              ("pharmacy", "Pharm. Tunde Bakare", "pharmacy", "Pharmacist", "PHARM"),
              ("admin", "Admin Bisi Adeyemi", "admin", "Hospital Administrator", "ADMIN")]


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
        if not settings.is_production:
            demo_departments(db, fac)
            add_demo_staff(db, fac, password)
        known = set(db.scalars(select(Icd10.code)).all())
        for code, desc, kw in ICD10_SEED:      # new codes shipped in an update are added on next start
            if code not in known:
                db.add(Icd10(code=code, description=desc, keywords=kw))
        db.commit()


def demo_departments(db, fac: Facility):
    """Development: the suggested departments and wards, so paging and channels have somewhere to go.
    The facility is left NOT onboarded on purpose, so the admin still walks through the set-up wizard."""
    if db.scalar(select(Department.id).where(Department.facility_id == fac.id)) is None:
        create_suggested(db, fac.id, [code for code, *_ in SUGGESTED])


def add_demo_staff(db, fac: Facility, password: str, accounts=DEMO_STAFF):
    """Adds any demo account that is missing (e.g. `lab` and `pharmacy` on a database made by an older build),
    and gives existing demo accounts a position and department if they have neither."""
    known = {s.username: s for s in db.scalars(select(Staff)).all()}
    depts = dict(db.execute(select(Department.code, Department.id).where(Department.facility_id == fac.id)).all())
    for username, name, role, position, dept in accounts:
        s = known.get(username)
        if s is not None:
            if s.position is None and s.department_id is None and s.role == role:
                s.position, s.department_id = position, depts.get(dept)
        else:
            db.add(Staff(facility_id=fac.id, username=username, full_name=name, role=role, position=position,
                         department_id=depts.get(dept), password_hash=hash_password(password)))
