"""Allergy aliases, scribe fallback, forced password change, facility branding, QR receipts and scanning."""
import builtins
from types import SimpleNamespace

from app.modules.ehr.clinical_rules import allergy_conflicts, drug_class_of
from app.modules.registration.service import parse_code
from app.modules.scribe import asr

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ allergies
def test_allergy_class_aliases():
    assert drug_class_of("Sulfa drugs") == "sulfonamide"
    assert drug_class_of("sulpha") == "sulfonamide"
    assert drug_class_of("NSAIDs") == "nsaid"
    assert drug_class_of("Fluoroquinolones") == "quinolone"
    assert drug_class_of("Paracetamol") is None


def test_old_allergy_records_still_match_by_name():
    # saved before the alias existed: drug_class holds the raw text, not the class
    old = SimpleNamespace(allergen_name="Sulfa drugs", drug_class="sulfa drugs")
    assert allergy_conflicts("Septrin 960mg", [old]) == [old]
    assert allergy_conflicts("Paracetamol", [old]) == []


def test_sulfa_allergy_from_reception_blocks_septrin(client, auth, make_patient, check_in):
    p = make_patient(allergies=[{"allergen_name": "Sulfa drugs", "severity": "severe"}])
    v = check_in(p["id"])["visit_id"]
    r = client.post(f"/api/ehr/visits/{v}/prescriptions", headers=auth["doctor"], json={"drug_name": "Septrin"})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "allergy_conflict"


# ------------------------------------------------------------------ scribe
def test_broken_whisper_install_degrades_instead_of_crashing(client, auth, monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *a, **kw):
        if name == "faster_whisper":
            raise FileNotFoundError("Could not find module 'ctranslate2.dll'")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(asr.settings, "asr_engine", "auto")
    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert asr.engine_name() == "none" and asr.available() is False
    r = client.get("/api/scribe/status", headers=auth["doctor"])
    assert r.status_code == 200 and r.json()["asr_available"] is False


# ------------------------------------------------------------------ forced password change
def test_temporary_password_only_opens_password_change(client, auth):
    r = client.post("/api/admin/staff", headers=auth["admin"], json={
        "username": "temp.nurse", "full_name": "Temp Nurse", "role": "nurse", "password": "Start-1234"})
    assert r.status_code == 201
    token = client.post("/api/auth/login", json={"username": "temp.nurse", "password": "Start-1234"}).json()["token"]
    blocked = client.get("/api/queues/TRIAGE", headers=_bearer(token))
    assert blocked.status_code == 403 and blocked.json()["detail"]["code"] == "password_change_required"
    assert client.get("/api/auth/me", headers=_bearer(token)).status_code == 200
    r = client.post("/api/auth/change-password", headers=_bearer(token),
                    json={"current_password": "Start-1234", "new_password": "Fresh-5678"})
    assert r.status_code == 200
    assert client.get("/api/queues/TRIAGE", headers=_bearer(r.json()["token"])).status_code == 200


# ------------------------------------------------------------------ facility branding
def test_facility_branding_and_logo(client, auth):
    assert client.get("/api/facility").status_code == 200          # public: login page and TV use it
    body = {"name": "St. Mary's Hospital", "address": "12 Allen Ave, Ikeja", "phone": "0803 000 0000",
            "email": "info@stmarys.ng", "motto": "Care with dignity"}
    assert client.put("/api/admin/facility", headers=auth["reception"], json=body).status_code == 403
    r = client.put("/api/admin/facility", headers=auth["admin"], json=body)
    assert r.status_code == 200 and r.json()["motto"] == "Care with dignity" and r.json()["logo_url"] is None

    bad = client.post("/api/admin/facility/logo", headers=auth["admin"],
                      files={"file": ("logo.png", b"<svg onload=alert(1)>", "image/png")})
    assert bad.status_code == 415                                    # declared PNG, but not a PNG
    r = client.post("/api/admin/facility/logo", headers=auth["admin"], files={"file": ("logo.png", PNG, "image/png")})
    assert r.status_code == 200 and r.json()["logo_url"].startswith("/api/facility/logo")
    logo = client.get("/api/facility/logo")
    assert logo.status_code == 200 and logo.content == PNG and logo.headers["content-type"] == "image/png"

    assert client.delete("/api/admin/facility/logo", headers=auth["admin"]).json()["logo_url"] is None
    assert client.get("/api/facility/logo").status_code == 404


# ------------------------------------------------------------------ QR code, scanning, receipts
def test_parse_code_tolerates_scanner_noise():
    assert parse_code("ARACARE:ARC-LAG-2026-000123") == "ARC-LAG-2026-000123"
    assert parse_code("arc-lag-2026-000123\r\n") == "ARC-LAG-2026-000123"
    assert parse_code("ARACARE>ARC-LAG-2026-000123") == "ARC-LAG-2026-000123"   # ':' typed on a UK layout
    assert parse_code("hello") is None


def test_scan_lookup(client, auth, make_patient):
    p = make_patient()
    payload = client.get(f"/api/patients/{p['id']}/receipt", headers=auth["reception"]).json()["qr"]
    assert payload == f"ARACARE:{p['patient_number']}"
    r = client.get("/api/patients/lookup", params={"code": payload}, headers=auth["reception"])
    assert r.status_code == 200 and r.json()["id"] == p["id"]
    assert client.get("/api/patients/lookup", params={"code": "nonsense"}, headers=auth["reception"]).status_code == 422
    assert client.get("/api/patients/lookup", params={"code": "ARC-LAG-1999-999999"},
                      headers=auth["reception"]).status_code == 404
    # a handheld scanner types the payload into the ordinary search box
    found = client.get("/api/patients/search", params={"q": payload}, headers=auth["reception"]).json()
    assert [x["id"] for x in found] == [p["id"]]


def test_receipt_before_and_after_check_in(client, auth, make_patient, check_in):
    p = make_patient(hmo_provider="Hygeia", hmo_number="HY-77", blood_group="O+")
    r = client.get(f"/api/patients/{p['id']}/receipt", headers=auth["reception"]).json()
    assert r["visit"] is None and r["patient"]["open_visit_id"] is None and r["facility"]["name"]
    ci = client.post(f"/api/patients/{p['id']}/check-in", headers=auth["reception"],
                     json={"visit_type": "follow_up", "payment_track": "hmo"}).json()
    r = client.get(f"/api/patients/{p['id']}/receipt", headers=auth["reception"]).json()
    assert r["visit"]["ticket"] == ci["ticket"] and r["visit"]["payment_track"] == "hmo"
    assert r["patient"]["open_visit_id"] == ci["visit_id"] and r["patient"]["hmo_number"] == "HY-77"
    other = make_patient()
    assert client.get(f"/api/patients/{p['id']}/receipt", params={"visit_id": "nope"},
                      headers=auth["reception"]).status_code == 404
    assert client.get(f"/api/patients/{other['id']}/receipt", headers=auth["nurse"]).status_code == 200


def test_patient_photo_is_served_only_to_staff(client, auth, make_patient):
    p = make_patient()
    url = f"/api/patients/{p['id']}/photo"
    assert client.get(url, headers=auth["reception"]).status_code == 404
    client.post(url, headers=auth["reception"], data={"consent": "true"}, files={"file": ("p.png", PNG, "image/png")})
    r = client.get(url, headers=auth["reception"])
    assert r.status_code == 200 and r.content == PNG and r.headers["cache-control"] == "no-store"
    assert client.get(url).status_code == 401
