"""Suggested set-up for a Nigerian general hospital: departments, their wards, and staff position titles.
The onboarding wizard offers these as ticks; the admin can rename, add or deactivate anything afterwards."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.models import Department, Ward

KINDS = ("clinical", "ward", "diagnostic", "support", "admin")

# (code, name, kind, [(ward code, ward name, beds)])
SUGGESTED = [
    ("EMERG", "Emergency (A&E)", "clinical", [("AE-RESUS", "A&E Resus Bay", 4), ("AE-OBS", "A&E Observation", 8)]),
    ("GOPD", "General Outpatients (GOPD)", "clinical", [("GOPD-TRI", "Triage & Treatment Room", 2),
                                                        ("GOPD-CR", "GOPD Consulting Rooms", 0)]),
    ("MED", "Internal Medicine", "clinical", [("MMW", "Male Medical Ward", 24), ("FMW", "Female Medical Ward", 24)]),
    ("SURG", "Surgery", "clinical", [("MSW", "Male Surgical Ward", 20), ("FSW", "Female Surgical Ward", 20),
                                     ("THEATRE", "Main Theatre", 2)]),
    ("OBG", "Obstetrics & Gynaecology", "clinical", [("LW", "Labour Ward", 10), ("PNW", "Postnatal Ward", 16),
                                                     ("GYN", "Gynae Ward", 12)]),
    ("PAED", "Paediatrics", "clinical", [("CW", "Children's Ward", 20), ("CHER", "Children's Emergency", 6),
                                         ("SCBU", "Special Care Baby Unit", 10)]),
    ("ICU", "Intensive Care", "ward", [("ICU", "Intensive Care Unit", 6)]),
    ("LAB", "Laboratory", "diagnostic", []),
    ("RAD", "Radiology", "diagnostic", []),
    ("PHARM", "Pharmacy", "support", []),
    ("NURS", "Nursing Services", "support", []),
    ("REC", "Records / Health Information", "support", []),
    ("ADMIN", "Administration", "admin", []),
]

POSITIONS = {
    "doctor": ["House Officer", "Medical Officer", "Registrar", "Senior Registrar", "Consultant", "Medical Director"],
    "nurse": ["Staff Nurse", "Nursing Officer", "Senior Nursing Officer", "Ward Sister", "Matron", "Midwife"],
    "lab": ["Medical Laboratory Scientist", "Lab Technician"],
    "pharmacy": ["Pharmacist", "Pharmacy Technician"],
    "reception": ["Front Desk Officer", "Health Records Officer"],
    "admin": ["Administrator", "Hospital Administrator"],
}


def suggested_view() -> list[dict]:
    return [{"code": c, "name": n, "kind": k, "wards": [{"code": wc, "name": wn, "bed_count": b} for wc, wn, b in w]}
            for c, n, k, w in SUGGESTED]


def create_suggested(db: Session, facility_id: str, codes: list[str]) -> tuple[list[Department], list[Ward]]:
    """Creates the chosen suggested departments and their wards. Idempotent: existing codes are kept as they are
    (a deactivated one is switched back on, since the admin just ticked it). Unknown codes raise KeyError."""
    by_code = {c: (n, k, w) for c, n, k, w in SUGGESTED}
    wanted = [c.strip().upper() for c in codes]
    missing = [c for c in wanted if c not in by_code]
    if missing:
        raise KeyError(", ".join(missing))
    depts = {d.code: d for d in db.scalars(select(Department).where(Department.facility_id == facility_id)).all()}
    wards = set(db.scalars(select(Ward.code).where(Ward.facility_id == facility_id)).all())
    new_d, new_w = [], []
    for code in dict.fromkeys(wanted):          # keep order, drop repeats
        name, kind, ward_specs = by_code[code]
        d = depts.get(code)
        if d is None:
            d = Department(facility_id=facility_id, code=code, name=name, kind=kind)
            db.add(d)
            db.flush()
            depts[code] = d
            new_d.append(d)
        elif not d.is_active:
            d.is_active = True
        for wcode, wname, beds in ward_specs:
            if wcode not in wards:
                w = Ward(facility_id=facility_id, department_id=d.id, code=wcode, name=wname, bed_count=beds)
                db.add(w)
                wards.add(wcode)
                new_w.append(w)
    db.flush()
    return new_d, new_w
