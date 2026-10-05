"""Deployment hardening: config guards, accounts, concurrency, day rollover, uploads, audit integrity."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.db import SessionLocal, local_today, utcnow
from app.modules.core.models import AuditLog
from app.modules.queues import service
from app.modules.queues.models import Ticket
from app.modules.registration.models import Visit


# ------------------------------------------------------------------ config
def test_production_refuses_unsafe_settings():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        Settings(env="production", secret_key="dev-secret-change-me").check()
    with pytest.raises(RuntimeError, match="CORS"):
        Settings(env="production", secret_key="x" * 40, cors_origins="*").check()
    Settings(env="production", secret_key="x" * 40, cors_origins="https://aracare.example").check()
    Settings().check()   # development defaults are fine


def test_health_checks_database(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


# ------------------------------------------------------------------ accounts
def _new_staff(client, auth, username, role="nurse", password="Start-1234"):
    r = client.post("/api/admin/staff", headers=auth["admin"],
                    json={"username": username, "full_name": f"Test {username}", "role": role, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


def _login(client, username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def test_admin_creates_staff_who_must_change_password(client, auth):
    s = _new_staff(client, auth, "nurse.ada")
    assert s["must_change_password"] is True
    assert client.post("/api/admin/staff", headers=auth["admin"], json={
        "username": "weak", "full_name": "Weak Pw", "role": "nurse", "password": "12345678"}).status_code == 422
    assert client.post("/api/admin/staff", headers=auth["admin"], json={
        "username": "nurse.ada", "full_name": "Dup", "role": "nurse", "password": "Start-1234"}).status_code == 409
    assert client.post("/api/admin/staff", headers=auth["doctor"], json={
        "username": "x1", "full_name": "No", "role": "nurse", "password": "Start-1234"}).status_code == 403
    token = _login(client, "nurse.ada", "Start-1234").json()["token"]
    r = client.post("/api/auth/change-password", headers={"Authorization": f"Bearer {token}"},
                    json={"current_password": "Start-1234", "new_password": "Better-5678"})
    assert r.status_code == 200 and r.json()["staff"]["must_change_password"] is False
    # the old token was revoked by the password change; the new one works
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['token']}"}).status_code == 200


def test_deactivation_and_role_change_revoke_tokens(client, auth):
    s = _new_staff(client, auth, "recep.bola", role="reception")
    h = {"Authorization": f"Bearer {_login(client, 'recep.bola', 'Start-1234').json()['token']}"}
    assert client.get("/api/auth/me", headers=h).status_code == 200
    assert client.patch(f"/api/admin/staff/{s['id']}", headers=auth["admin"], json={"is_active": False}).status_code == 200
    assert client.get("/api/auth/me", headers=h).status_code == 401
    assert _login(client, "recep.bola", "Start-1234").status_code == 401
    me = client.get("/api/auth/me", headers=auth["admin"]).json()
    assert client.patch(f"/api/admin/staff/{me['id']}", headers=auth["admin"],
                        json={"is_active": False}).status_code == 409          # can't lock yourself out


def test_login_lockout_after_repeated_failures(client, auth):
    s = _new_staff(client, auth, "doc.locked", role="doctor")
    for _ in range(5):
        assert _login(client, "doc.locked", "wrong-pass1").status_code == 401
    assert _login(client, "doc.locked", "Start-1234").status_code == 429     # even the right password waits
    # an admin reset unlocks the account
    assert client.post(f"/api/admin/staff/{s['id']}/reset-password", headers=auth["admin"],
                       json={"password": "Reset-9876"}).status_code == 200
    assert _login(client, "doc.locked", "Reset-9876").status_code == 200


# ------------------------------------------------------------------ concurrency
def test_concurrent_registrations_get_unique_patient_numbers(client, auth):
    def register(i):
        return client.post("/api/patients", headers=auth["reception"], json={
            "surname": f"Parallel{i}", "first_name": f"Reg{i}", "phone": f"0909{i:07d}",
            "date_of_birth": f"{1970 + i}-03-0{1 + i % 9}", "gender": "male"})
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(register, range(16)))
    assert all(r.status_code == 201 for r in results), [r.text for r in results if r.status_code != 201]
    numbers = [r.json()["patient_number"] for r in results]
    assert len(set(numbers)) == len(numbers)


# ------------------------------------------------------------------ queue correctness
def test_follow_up_ages_one_step_only_and_reads_do_not_write():
    now = utcnow()
    t = SimpleNamespace(priority_tier="FOLLOW_UP", entered_waiting_at=now - timedelta(minutes=200))
    assert service.effective_tier(t, now) == "NORMAL"          # used to cascade on to HIGH
    t = SimpleNamespace(priority_tier="NORMAL", entered_waiting_at=now - timedelta(minutes=50))
    assert service.effective_tier(t, now) == "HIGH"
    assert t.priority_tier == "NORMAL"                          # base tier untouched


def test_unfinished_visit_from_yesterday_does_not_block_check_in(client, auth, make_patient, check_in):
    p = make_patient()
    first = check_in(p["id"])
    with SessionLocal() as db:      # pretend the visit was opened yesterday and never finished
        v = db.get(Visit, first["visit_id"])
        v.checked_in_at = utcnow() - timedelta(days=1, hours=2)
        for t in db.query(Ticket).filter(Ticket.visit_id == v.id).all():
            t.day = local_today() - timedelta(days=1)
        db.commit()
    second = check_in(p["id"])       # used to fail with 409 "already has an open visit" forever
    with SessionLocal() as db:
        assert db.get(Visit, first["visit_id"]).status == "abandoned"
        assert {t.status for t in db.query(Ticket).filter(Ticket.visit_id == first["visit_id"]).all()} == {"cancelled"}
        assert db.get(Visit, second["visit_id"]).status == "checked_in"


def test_sweeper_closes_yesterdays_visits(client, auth, make_patient, check_in):
    ci = check_in(make_patient()["id"])
    with SessionLocal() as db:
        db.get(Visit, ci["visit_id"]).checked_in_at = utcnow() - timedelta(days=2)
        db.commit()
        assert service.close_stale_visits(db) >= 1
        db.commit()
        assert db.get(Visit, ci["visit_id"]).status == "abandoned"
    r = client.post(f"/api/ehr/visits/{ci['visit_id']}/triage", headers=auth["nurse"], json={"temperature": 37})
    assert r.status_code == 409                                   # closed visits take no new triage


def test_check_in_validates_payment_track(client, auth, make_patient):
    p = make_patient()
    url = f"/api/patients/{p['id']}/check-in"
    assert client.post(url, headers=auth["reception"], json={"payment_track": "bitcoin"}).status_code == 422
    assert client.post(url, headers=auth["reception"], json={"payment_track": "hmo"}).status_code == 422   # no HMO on file
    assert client.post(url, headers=auth["reception"], json={"payment_track": "waiver"}).status_code == 403


# ------------------------------------------------------------------ uploads
def test_photo_upload_rejects_wrong_type_and_oversize(client, auth, make_patient):
    p = make_patient()
    url = f"/api/patients/{p['id']}/photo"
    bad = client.post(url, headers=auth["reception"], data={"consent": "true"},
                      files={"file": ("x.exe", b"MZ...", "application/octet-stream")})
    assert bad.status_code == 415
    big = client.post(url, headers=auth["reception"], data={"consent": "true"},
                      files={"file": ("x.jpg", b"\xff" * (5 * 1024 * 1024 + 10), "image/jpeg")})
    assert big.status_code == 413
    ok = client.post(url, headers=auth["reception"], data={"consent": "true"},
                     files={"file": ("x.png", b"\x89PNG fake", "image/png")})
    assert ok.status_code == 200 and ok.json()["photo_saved"] is True


# ------------------------------------------------------------------ audit / scribe integrity
def test_audit_rows_carry_the_record_id(client, auth, make_patient):
    p = make_patient()
    r = client.post(f"/api/ehr/patients/{p['id']}/allergies", headers=auth["nurse"],
                    json={"allergen_name": "Penicillin", "severity": "severe"})
    assert r.status_code == 201
    with SessionLocal() as db:
        row = db.query(AuditLog).filter(AuditLog.record_type == "allergy", AuditLog.patient_id == p["id"]).one()
        assert row.record_id == r.json()["id"]
    assert client.post(f"/api/ehr/patients/{p['id']}/allergies", headers=auth["nurse"],
                       json={"allergen_name": "Sulfa", "severity": "deadly"}).status_code == 422


def test_scribe_draft_cannot_be_attached_to_another_visit(client, auth, make_patient, check_in):
    a, b = check_in(make_patient()["id"]), check_in(make_patient()["id"])
    client.post("/api/scribe/consent", headers=auth["nurse"], json={"visit_id": a["visit_id"], "granted": True})
    d = client.post("/api/scribe/draft", headers=auth["nurse"], json={
        "visit_id": a["visit_id"], "transcript": "Temperature 38.2, pulse 96, complains of fever"}).json()
    r = client.post(f"/api/ehr/visits/{b['visit_id']}/triage", headers=auth["nurse"],
                    json={"temperature": 38.2, "scribe_session_id": d["session_id"]})
    assert r.status_code == 422
