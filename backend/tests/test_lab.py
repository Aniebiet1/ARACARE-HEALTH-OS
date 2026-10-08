"""Lab and pharmacy worklists: start, result, dispense, and the alerts they send back to the doctor."""
from sqlalchemy import select

from app.db import SessionLocal
from app.modules.core.models import Department, Staff, Ward
from app.modules.core.security import hash_password, make_token


# ------------------------------------------------------------------ helpers (also used by test_pulse.py)
def ensure_dept(code: str, name: str, kind: str = "clinical") -> str:
    with SessionLocal() as db:
        d = db.scalar(select(Department).where(Department.code == code))
        if not d:
            fid = db.scalar(select(Staff.facility_id).where(Staff.username == "admin"))
            d = Department(facility_id=fid, code=code, name=name, kind=kind)
            db.add(d)
            db.commit()
        return d.id


def ensure_ward(code: str, name: str, department_id: str | None = None) -> str:
    with SessionLocal() as db:
        w = db.scalar(select(Ward).where(Ward.code == code))
        if not w:
            fid = db.scalar(select(Staff.facility_id).where(Staff.username == "admin"))
            w = Ward(facility_id=fid, code=code, name=name, department_id=department_id, floor="Ground floor",
                     bed_count=12)
            db.add(w)
            db.commit()
        return w.id


def make_staff(username: str, role: str, department_id: str | None = None, on_duty: bool = True,
               position: str | None = None, name: str | None = None) -> tuple[str, dict]:
    """Created directly so the tests don't depend on the seed or the admin endpoints' timing."""
    with SessionLocal() as db:
        s = db.scalar(select(Staff).where(Staff.username == username))
        if not s:
            fid = db.scalar(select(Staff.facility_id).where(Staff.username == "admin"))
            s = Staff(facility_id=fid, username=username, full_name=name or username.title(), role=role,
                      position=position, department_id=department_id, on_duty=on_duty,
                      password_hash=hash_password("demo123"))
            db.add(s)
            db.commit()
        return s.id, {"Authorization": f"Bearer {make_token(s)}"}


def signed_visit(client, auth, make_patient, check_in, labs=(), drugs=(), **patient):
    """A visit whose note is signed with the given lab tests / drugs, so they are 'sent'."""
    p = make_patient(**patient)
    v = check_in(p["id"])["visit_id"]
    note = client.put(f"/api/ehr/visits/{v}/note", headers=auth["doctor"], json={
        "subjective": "Fever 3 days", "objective": "Febrile", "assessment": "Malaria", "plan": "Tests",
        "diagnoses": ["B50.9"]}).json()
    lab_ids = [client.post(f"/api/ehr/visits/{v}/lab-orders", headers=auth["doctor"],
                           json={"test_code": c, "test_name": n, "priority": pr}).json()["id"] for c, n, pr in labs]
    rx_ids = [client.post(f"/api/ehr/visits/{v}/prescriptions", headers=auth["doctor"],
                          json={"drug_name": d, "dose": "1 tab", "frequency": "BD", "duration_days": 3}).json()["id"]
              for d in drugs]
    assert client.post(f"/api/ehr/notes/{note['id']}/sign", headers=auth["doctor"]).status_code == 200
    return p, v, lab_ids, rx_ids


def doctor_alerts(client, auth, status="open"):
    return client.get(f"/api/pulse/alerts?status={status}", headers=auth["doctor"]).json()


# ------------------------------------------------------------------ lab
def test_lab_worklist_orders_stat_first_and_only_sent(client, auth, make_patient, check_in):
    _, lab = make_staff("lab.tester", "lab", position="Medical Laboratory Scientist")
    _, v1, (routine,), _ = signed_visit(client, auth, make_patient, check_in,
                                        labs=[("LAB-FBC", "Full Blood Count", "routine")])
    _, v2, (stat,), _ = signed_visit(client, auth, make_patient, check_in, labs=[("LAB-MAL", "Malaria RDT", "stat")])
    # an order on an unsigned note has not been sent to the lab
    p = make_patient()
    v3 = check_in(p["id"])["visit_id"]
    unsent = client.post(f"/api/ehr/visits/{v3}/lab-orders", headers=auth["doctor"],
                         json={"test_code": "LAB-UA", "test_name": "Urinalysis"}).json()["id"]

    assert client.get("/api/lab/worklist", headers=auth["nurse"]).status_code == 403
    rows = client.get("/api/lab/worklist?status=pending", headers=lab).json()
    ids = [r["id"] for r in rows]
    assert stat in ids and routine in ids and unsent not in ids
    assert ids.index(stat) < ids.index(routine)
    row = next(r for r in rows if r["id"] == stat)
    assert row["patient"]["patient_number"] and row["ordered_by"]["name"] and row["visit_id"] == v2
    assert client.get("/api/lab/worklist?status=pending", headers=auth["admin"]).status_code == 200
    assert client.post(f"/api/lab/orders/{unsent}/start", headers=lab).status_code == 409


def test_result_reaches_ordering_doctor_and_visit_workspace(client, auth, make_patient, check_in):
    _, lab = make_staff("lab.tester", "lab")
    _, v, (oid,), _ = signed_visit(client, auth, make_patient, check_in, labs=[("LAB-FBC", "Full Blood Count", "routine")])
    assert client.post(f"/api/lab/orders/{oid}/result", headers=auth["doctor"],
                       json={"result_text": "x", "result_flag": "normal"}).status_code == 403   # lab only
    r = client.post(f"/api/lab/orders/{oid}/start", headers=lab)
    assert r.status_code == 200 and r.json()["status"] == "in_progress" and r.json()["started_at"]
    assert client.post(f"/api/lab/orders/{oid}/start", headers=lab).status_code == 409
    assert client.post(f"/api/lab/orders/{oid}/result", headers=lab,
                       json={"result_text": "Hb 12", "result_flag": "weird"}).status_code == 422
    r = client.post(f"/api/lab/orders/{oid}/result", headers=lab,
                    json={"result_text": "Hb 12.1 g/dL, WBC 6.8, Plt 250", "result_flag": "abnormal"})
    assert r.status_code == 200 and r.json()["status"] == "resulted"
    assert client.post(f"/api/lab/orders/{oid}/result", headers=lab,
                       json={"result_text": "again", "result_flag": "normal"}).status_code == 409

    alert = next(a for a in doctor_alerts(client, auth) if a["ref_id"] == oid)
    assert alert["kind"] == "lab_result" and alert["priority"] == "urgent" and not alert["ack_required"]
    assert "Full Blood Count" in alert["title"] and alert["visit_id"] == v

    ws = client.get(f"/api/ehr/visits/{v}", headers=auth["doctor"]).json()
    lo = ws["lab_orders"][0]
    assert lo["result_flag"] == "abnormal" and lo["result_text"].startswith("Hb") and lo["resulted_at"] and lo["started_at"]
    done = client.get("/api/lab/worklist?status=done", headers=lab).json()
    assert any(x["id"] == oid and x["resulted_by"] for x in done)


def test_critical_result_needs_ack_and_escalates(client, auth, make_patient, check_in):
    from datetime import timedelta

    from app.modules.pulse import service
    from app.modules.pulse.models import PulseAlert, PulseMessage

    _, lab = make_staff("lab.tester", "lab")
    _, _, (oid,), _ = signed_visit(client, auth, make_patient, check_in, labs=[("LAB-EUC", "E/U/Cr", "urgent")])
    client.post(f"/api/lab/orders/{oid}/result", headers=lab,
                json={"result_text": "K+ 6.9 mmol/L", "result_flag": "critical"})
    alert = next(a for a in doctor_alerts(client, auth) if a["ref_id"] == oid)
    assert alert["kind"] == "lab_critical" and alert["priority"] == "critical" and alert["ack_required"]
    assert client.get("/api/pulse/summary", headers=auth["doctor"]).json()["critical_alerts"] >= 1

    # seen is not acknowledged
    seen = client.post(f"/api/pulse/alerts/{alert['id']}/seen", headers=auth["doctor"]).json()
    assert seen["seen_at"] and not seen["acked_at"]
    assert any(a["id"] == alert["id"] for a in doctor_alerts(client, auth))

    with SessionLocal() as db:   # ten minutes pass without an acknowledgement
        a = db.get(PulseAlert, alert["id"])
        a.created_at -= timedelta(minutes=11)
        db.commit()
        service.tick(db)
        db.commit()
        assert db.get(PulseAlert, alert["id"]).escalated_at is not None
        copies = lambda: db.scalars(select(PulseMessage).where(  # noqa: E731
            PulseMessage.priority == "critical", PulseMessage.body.like(f"%{alert['patient']['patient_number']}%"),
            PulseMessage.body.like("%E/U/Cr%"))).all()
        assert len(copies()) == 1 and copies()[0].ack_required
        service.tick(db)       # idempotent: a second sweep does not post it again
        db.commit()
        assert len(copies()) == 1

    acked = client.post(f"/api/pulse/alerts/{alert['id']}/ack", headers=auth["doctor"]).json()
    assert acked["acked_at"] and acked["acked_by"]["id"]
    assert not any(a["id"] == alert["id"] for a in doctor_alerts(client, auth))
    assert any(a["id"] == alert["id"] for a in doctor_alerts(client, auth, "all"))
    assert client.post(f"/api/pulse/alerts/{alert['id']}/ack", headers=auth["nurse"]).status_code == 404


# ------------------------------------------------------------------ pharmacy
def test_pharmacy_dispense_groups_per_visit_and_confirms_to_doctor(client, auth, make_patient, check_in):
    _, ph = make_staff("pharm.tester", "pharmacy", position="Pharmacist")
    p, v, _, (a, b) = signed_visit(client, auth, make_patient, check_in, drugs=["Paracetamol 500mg", "Vitamin C"])
    assert client.get("/api/pharmacy/worklist", headers=auth["doctor"]).status_code == 403
    card = next(g for g in client.get("/api/pharmacy/worklist", headers=ph).json() if g["visit_id"] == v)
    assert {i["id"] for i in card["items"]} == {a, b} and card["patient"]["id"] == p["id"]
    assert card["ordered_by"]["name"] and card["items"][0]["route"] == "oral"

    assert client.post(f"/api/pharmacy/orders/{a}/dispense", headers=auth["doctor"]).status_code == 403
    r = client.post(f"/api/pharmacy/orders/{a}/dispense", headers=ph)
    assert r.status_code == 200 and r.json()["status"] == "dispensed" and r.json()["dispensed_at"]
    assert client.post(f"/api/pharmacy/orders/{a}/dispense", headers=ph).status_code == 409
    client.post(f"/api/pharmacy/orders/{b}/dispense", headers=ph)

    # two items, one confirmation for the doctor
    mine = [x for x in doctor_alerts(client, auth) if x["kind"] == "dispensed" and x["visit_id"] == v]
    assert len(mine) == 1 and "Paracetamol" in mine[0]["body"] and "Vitamin C" in mine[0]["body"]
    assert all(g["visit_id"] != v for g in client.get("/api/pharmacy/worklist", headers=ph).json())
    assert any(g["visit_id"] == v for g in client.get("/api/pharmacy/worklist?status=done", headers=ph).json())
    rx = client.get(f"/api/ehr/visits/{v}", headers=auth["doctor"]).json()["prescriptions"]
    assert all(m["dispensed_at"] for m in rx)
