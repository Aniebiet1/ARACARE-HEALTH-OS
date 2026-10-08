"""Onboarding, departments and wards, staff positions and new roles, duty status, and the admin analytics."""
import uuid

from app.db import SessionLocal
from app.modules.core.models import Department, Facility


def _code(prefix="T"):
    return f"{prefix}{uuid.uuid4().hex[:6]}".upper()


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _staff(client, auth, role, **extra):
    username = f"{role}.{uuid.uuid4().hex[:6]}"
    r = client.post("/api/admin/staff", headers=auth["admin"], json={
        "username": username, "full_name": f"Test {role}", "role": role, "password": "Start-1234", **extra})
    assert r.status_code == 201, r.text
    token = client.post("/api/auth/login", json={"username": username, "password": "Start-1234"}).json()["token"]
    token = client.post("/api/auth/change-password", headers=_bearer(token),
                        json={"current_password": "Start-1234", "new_password": "Fresh-5678"}).json()["token"]
    return r.json(), _bearer(token)


# ------------------------------------------------------------------ onboarding
def test_onboarding_flow(client, auth):
    with SessionLocal() as db:                       # start from "not onboarded", whatever ran before
        fac = db.query(Facility).one()
        fac.onboarded_at = fac.onboarded_by = None
        db.commit()
    assert client.get("/api/auth/me", headers=auth["admin"]).json()["facility_onboarded"] is False
    assert client.get("/api/admin/onboarding", headers=auth["doctor"]).status_code == 403

    status = client.get("/api/admin/onboarding", headers=auth["admin"]).json()
    assert status["completed"] is False and status["completed_at"] is None
    assert set(status["steps"]) == {"profile", "departments", "wards", "staff"}
    codes = {d["code"] for d in status["suggested_departments"]}
    assert {"EMERG", "GOPD", "LAB", "PHARM", "ICU", "OBG", "PAED"} <= codes
    assert "Matron" in status["positions"]["nurse"] and "Consultant" in status["positions"]["doctor"]

    # profile incomplete -> can't finish
    client.put("/api/admin/facility", headers=auth["admin"], json={"name": "General Hospital Ikeja", "address": ""})
    assert client.get("/api/admin/onboarding", headers=auth["admin"]).json()["steps"]["profile"] is False
    assert client.post("/api/admin/onboarding/complete", headers=auth["admin"]).status_code == 409

    r = client.put("/api/admin/facility", headers=auth["admin"], json={
        "name": "General Hospital Ikeja", "address": "1 Hospital Road", "phone": "0803 000 1234",
        "facility_type": "general", "ownership": "state", "license_number": "LSMOH/1", "city": "Ikeja",
        "lga": "Ikeja", "emergency_phone": "0809 112 2112", "website": "https://gh.example.ng",
        "bed_capacity": 120, "open_24h": True})
    assert r.status_code == 200 and r.json()["bed_capacity"] == 120 and r.json()["facility_type"] == "general"
    assert client.put("/api/admin/facility", headers=auth["admin"],
                      json={"name": "X Hospital", "facility_type": "castle"}).status_code == 422

    # suggested departments are idempotent and bring their wards
    r = client.post("/api/admin/onboarding/departments", headers=auth["admin"], json={"codes": ["emerg", "OBG"]})
    assert r.status_code == 200
    again = client.post("/api/admin/onboarding/departments", headers=auth["admin"], json={"codes": ["EMERG", "OBG"]})
    assert [d["code"] for d in again.json()["departments"]].count("EMERG") == 1
    ward_codes = {w["code"] for w in again.json()["wards"]}
    assert {"AE-RESUS", "LW"} <= ward_codes
    assert client.post("/api/admin/onboarding/departments", headers=auth["admin"],
                       json={"codes": ["NOPE"]}).status_code == 422

    steps = client.get("/api/admin/onboarding", headers=auth["admin"]).json()["steps"]
    assert steps == {"profile": True, "departments": True, "wards": True, "staff": True}
    done = client.post("/api/admin/onboarding/complete", headers=auth["admin"])
    assert done.status_code == 200 and done.json()["completed"] is True and done.json()["completed_at"]
    assert client.get("/api/auth/me", headers=auth["admin"]).json()["facility_onboarded"] is True

    profile = client.get("/api/admin/facility", headers=auth["admin"]).json()
    assert profile["onboarded_at"] and profile["license_number"] == "LSMOH/1" and profile["lga"] == "Ikeja"
    public = client.get("/api/facility").json()
    assert public["name"] == "General Hospital Ikeja" and "license_number" not in public


def test_onboarding_is_not_a_backend_gate(client, auth):
    with SessionLocal() as db:
        fac = db.query(Facility).one()
        saved = fac.onboarded_at
        fac.onboarded_at = None
        db.commit()
    try:
        assert client.get("/api/queues/TRIAGE", headers=auth["nurse"]).status_code == 200
    finally:
        with SessionLocal() as db:
            db.query(Facility).one().onboarded_at = saved
            db.commit()


# ------------------------------------------------------------------ departments and wards
def test_department_and_ward_crud(client, auth):
    code = _code("D")
    body = {"code": code.lower(), "name": "Dental Clinic", "kind": "clinical"}
    assert client.post("/api/admin/departments", headers=auth["doctor"], json=body).status_code == 403
    r = client.post("/api/admin/departments", headers=auth["admin"], json=body)
    assert r.status_code == 201 and r.json()["code"] == code and r.json()["staff_count"] == 0
    dept = r.json()
    assert client.post("/api/admin/departments", headers=auth["admin"], json=body).status_code == 409
    assert client.post("/api/admin/departments", headers=auth["admin"],
                       json={**body, "code": _code(), "kind": "spa"}).status_code == 422

    wcode = _code("W")
    r = client.post("/api/admin/wards", headers=auth["admin"],
                    json={"code": wcode, "name": "Dental Recovery", "department_id": dept["id"], "bed_count": 3,
                          "floor": "Ground"})
    assert r.status_code == 201 and r.json()["department_name"] == "Dental Clinic" and r.json()["bed_count"] == 3
    ward = r.json()
    assert client.post("/api/admin/wards", headers=auth["admin"],
                       json={"code": wcode, "name": "Again", "bed_count": 1}).status_code == 409
    assert client.post("/api/admin/wards", headers=auth["admin"], json={
        "code": _code("W"), "name": "Ghost", "department_id": str(uuid.uuid4()), "bed_count": 1}).status_code == 422

    r = client.patch(f"/api/admin/wards/{ward['id']}", headers=auth["admin"], json={"bed_count": 5, "is_active": False})
    assert r.json()["bed_count"] == 5 and r.json()["is_active"] is False
    r = client.patch(f"/api/admin/departments/{dept['id']}", headers=auth["admin"],
                     json={"name": "Dental Surgery", "is_active": False})
    assert r.status_code == 200 and r.json()["name"] == "Dental Surgery" and r.json()["is_active"] is False

    # any signed-in role can read the lists
    depts = client.get("/api/org/departments", headers=auth["nurse"]).json()
    assert any(d["id"] == dept["id"] and d["is_active"] is False for d in depts)
    wards = client.get("/api/org/wards", headers=auth["reception"]).json()
    assert any(w["id"] == ward["id"] and w["department_name"] == "Dental Surgery" for w in wards)


def test_departments_are_scoped_to_the_facility(client, auth):
    with SessionLocal() as db:
        other = Facility(name="Other Hospital", state_code="OYO")
        db.add(other)
        db.flush()
        foreign = Department(facility_id=other.id, code="EMERG", name="Their A&E", kind="clinical")
        db.add(foreign)
        db.commit()
        fid = foreign.id
    try:
        assert all(d["id"] != fid for d in client.get("/api/org/departments", headers=auth["admin"]).json())
        assert client.patch(f"/api/admin/departments/{fid}", headers=auth["admin"],
                            json={"name": "Mine now"}).status_code == 404
        r = client.post("/api/admin/staff", headers=auth["admin"], json={
            "username": f"x.{uuid.uuid4().hex[:6]}", "full_name": "Wrong Dept", "role": "nurse",
            "password": "Start-1234", "department_id": fid})
        assert r.status_code == 422
    finally:
        with SessionLocal() as db:                   # other tests read "the" facility with .one()
            db.query(Department).filter_by(id=fid).delete()
            db.query(Facility).filter_by(name="Other Hospital").delete()
            db.commit()


# ------------------------------------------------------------------ staff, roles, duty
def test_staff_positions_departments_and_new_roles(client, auth):
    lab = next(d for d in client.get("/api/org/departments", headers=auth["admin"]).json() if d["code"] == "LAB")
    s, h = _staff(client, auth, "lab", position="Medical Laboratory Scientist", department_id=lab["id"],
                  phone=" 0803 111 2222 ")
    assert s["role"] == "lab" and s["position"] == "Medical Laboratory Scientist"
    assert s["department_name"] == "Laboratory" and s["phone"] == "0803 111 2222" and s["on_duty"] is True
    p, _ = _staff(client, auth, "pharmacy", position="Pharmacist")
    assert p["role"] == "pharmacy" and p["department_id"] is None

    r = client.patch(f"/api/admin/staff/{s['id']}", headers=auth["admin"], json={"position": "Lab Technician"})
    assert r.json()["position"] == "Lab Technician" and r.json()["department_id"] == lab["id"]
    r = client.patch(f"/api/admin/staff/{s['id']}", headers=auth["admin"], json={"department_id": None})
    assert r.json()["department_id"] is None and r.json()["department_name"] is None
    assert client.post("/api/admin/staff", headers=auth["admin"], json={
        "username": "bad.role1", "full_name": "Bad Role", "role": "janitor", "password": "Start-1234"}
    ).status_code == 422

    me = client.get("/api/auth/me", headers=h).json()
    assert me["role"] == "lab" and "facility_onboarded" in me
    listed = client.get("/api/admin/staff", headers=auth["admin"]).json()
    assert {"position", "department_id", "department_name", "phone", "on_duty"} <= set(listed[0])
    assert client.get("/api/admin/staff", headers=h).status_code == 403


def test_duty_toggle_and_directory(client, auth):
    me = client.get("/api/auth/me", headers=auth["doctor"]).json()
    r = client.post("/api/auth/duty", headers=auth["doctor"], json={"on_duty": False})
    assert r.status_code == 200 and r.json()["on_duty"] is False
    entry = next(x for x in client.get("/api/org/directory", headers=auth["nurse"]).json() if x["id"] == me["id"])
    assert entry["on_duty"] is False and "username" not in entry and "phone" not in entry
    assert client.post("/api/auth/duty", headers=auth["doctor"], json={"on_duty": True}).json()["on_duty"] is True
    assert client.post("/api/auth/duty", json={"on_duty": True}).status_code == 401

    # a temporary password must be changed first, like every other endpoint
    username = f"temp.{uuid.uuid4().hex[:6]}"
    client.post("/api/admin/staff", headers=auth["admin"], json={
        "username": username, "full_name": "Temp Pharm", "role": "pharmacy", "password": "Start-1234"})
    token = client.post("/api/auth/login", json={"username": username, "password": "Start-1234"}).json()["token"]
    assert client.post("/api/auth/duty", headers=_bearer(token), json={"on_duty": False}).status_code == 403
    assert client.get("/api/org/directory", headers=_bearer(token)).status_code == 403


# ------------------------------------------------------------------ analytics
def _check_shape(a, days):
    assert a["days"] == days and a["generated_at"]
    assert set(a["today"]) == {"checked_in", "waiting_triage", "waiting_doctor", "in_consultation", "seen_by_doctor",
                               "avg_wait_triage_min", "avg_wait_doctor_min", "critical_flags", "labs_pending",
                               "labs_resulted_today", "staff_active", "staff_on_duty"}
    assert len(a["daily"]) == days
    dates = [d["date"] for d in a["daily"]]
    assert dates == sorted(dates) and len(set(dates)) == days
    assert set(a["daily"][0]) == {"date", "visits", "new_complaint", "follow_up", "emergency", "avg_wait_min",
                                  "critical_flags", "notes_signed"}
    assert [h["hour"] for h in a["hourly_today"]] == list(range(24))
    assert [t["priority"] for t in a["triage_mix"]] == ["EMERGENCY", "HIGH", "NORMAL", "FOLLOW_UP"]
    assert len(a["top_diagnoses"]) <= 8
    assert [b["label"] for b in a["demographics"]["age_bands"]] == ["0-4", "5-14", "15-24", "25-44", "45-64", "65+"]
    assert set(a["lab"]) == {"ordered", "resulted", "pending", "critical", "median_turnaround_min", "by_test"}
    assert len(a["lab"]["by_test"]) <= 6
    assert {r["role"] for r in a["staff"]["by_role"]} >= {"doctor", "nurse", "lab", "pharmacy"}
    assert all(set(w) == {"id", "name", "bed_count", "department_name"} for w in a["wards"])


def test_analytics_shape_and_access(client, auth):
    assert client.get("/api/admin/analytics", headers=auth["doctor"]).status_code == 403
    assert client.get("/api/admin/analytics?days=3", headers=auth["admin"]).status_code == 422
    assert client.get("/api/admin/analytics?days=91", headers=auth["admin"]).status_code == 422
    for days in (7, 14, 90):
        r = client.get(f"/api/admin/analytics?days={days}", headers=auth["admin"])
        assert r.status_code == 200, r.text
        _check_shape(r.json(), days)


def test_analytics_counts_a_new_visit(client, auth, make_patient, check_in):
    before = client.get("/api/admin/analytics", headers=auth["admin"]).json()
    p = make_patient()
    check_in(p["id"], visit_type="emergency")
    after = client.get("/api/admin/analytics", headers=auth["admin"]).json()
    _check_shape(after, 14)
    assert after["today"]["checked_in"] == before["today"]["checked_in"] + 1
    assert after["daily"][-1]["emergency"] == before["daily"][-1]["emergency"] + 1
    assert sum(h["arrivals"] for h in after["hourly_today"]) == after["today"]["checked_in"]
    assert after["today"]["waiting_triage"] >= 1
