"""The defence demo as an automated test: register -> check in -> queue -> triage -> SOAP -> sign -> journey done."""


def test_auth_required_and_roles(client, auth):
    assert client.get("/api/queues/TRIAGE").status_code == 401
    assert client.post("/api/auth/login", json={"username": "doctor", "password": "wrong"}).status_code == 401
    # reception cannot open a clinical chart
    assert client.get("/api/ehr/patients/x/chart", headers=auth["reception"]).status_code == 403


def test_registration_card_and_patient_number(client, auth, make_patient):
    p = make_patient()
    assert p["patient_number"].startswith("ARC-LAG-")
    assert p["patient_number"].count("-") == 3
    assert "Your AraCare Patient ID" in p["card_text"]
    msgs = client.get("/api/admin/messages", headers=auth["admin"]).json()
    assert any(p["patient_number"] in m["body"] for m in msgs)           # SMS card queued


def test_duplicate_detection_and_fuzzy_search(client, auth, make_patient):
    p = make_patient(surname="Okonkwo", first_name="Adaeze", phone="08031112222")
    dup = client.post("/api/patients", headers=auth["reception"], json={
        "surname": "Okonkwo", "first_name": "Adaeze", "phone": "08031112222", "date_of_birth": "1990-05-12", "gender": "female"})
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "possible_duplicate"
    # spelling variants and phone-suffix both find her
    assert any(x["id"] == p["id"] for x in client.get("/api/patients/search?q=Okonkow", headers=auth["reception"]).json())
    assert any(x["id"] == p["id"] for x in client.get("/api/patients/search?q=08031112222", headers=auth["reception"]).json())
    assert any(x["id"] == p["id"] for x in client.get("/api/patients/search?q=%2B2348031112222", headers=auth["reception"]).json())


def test_photo_consent_refusal_is_recorded_and_no_photo_saved(client, auth, make_patient):
    p = make_patient()
    r = client.post(f"/api/patients/{p['id']}/photo", data={"consent": "false"}, headers=auth["reception"])
    assert r.status_code == 200 and r.json() == {"photo_saved": False, "consent": False}


def test_full_visit_journey(client, auth, make_patient, check_in):
    p = make_patient()
    ci = check_in(p["id"])
    assert ci["ticket"].startswith("TRI-") and ci["department"] == "TRIAGE"
    assert client.post(f"/api/patients/{p['id']}/check-in", json={"visit_type": "new_complaint"},
                       headers=auth["reception"]).status_code == 409          # no double check-in

    # nurse calls the patient, patient arrives
    called = client.post("/api/queues/TRIAGE/call-next", json={"counter": "Triage 1"}, headers=auth["nurse"]).json()
    assert called["status"] == "called"
    arr = client.post(f"/api/tickets/{called['id']}/arrived", headers=auth["nurse"])
    assert arr.json()["status"] == "in_service"

    # triage: fever flagged, saving it cascades the patient to the doctor's queue
    vit = client.post(f"/api/ehr/visits/{ci['visit_id']}/triage", headers=auth["nurse"], json={
        "bp_systolic": 120, "bp_diastolic": 80, "pulse_rate": 92, "temperature": 38.4, "spo2": 98,
        "weight_kg": 62, "height_cm": 163, "chief_complaint": "fever and headache", "triage_priority": "NORMAL"})
    assert vit.status_code == 201
    assert any(f["field"] == "temperature" for f in vit.json()["flags"])
    assert vit.json()["bmi"] == 23.3
    opd = client.get("/api/queues/OPD-GEN", headers=auth["doctor"]).json()
    assert any(t["visit_id"] == ci["visit_id"] for t in opd["waiting"])

    # doctor sees the patient and writes the note
    t = client.post("/api/queues/OPD-GEN/call-next", json={"counter": "Room 2"}, headers=auth["doctor"]).json()
    assert t["visit_id"] == ci["visit_id"]
    client.post(f"/api/tickets/{t['id']}/arrived", headers=auth["doctor"])
    note = client.put(f"/api/ehr/visits/{ci['visit_id']}/note", headers=auth["doctor"], json={
        "subjective": "Fever 2 days", "objective": "Febrile", "assessment": "Malaria", "plan": "ACT",
        "diagnoses": ["B50.9"]})
    assert note.status_code == 200
    client.post(f"/api/ehr/visits/{ci['visit_id']}/lab-orders", headers=auth["doctor"],
                json={"test_code": "LAB-MAL", "test_name": "Malaria RDT", "priority": "stat"})
    rx = client.post(f"/api/ehr/visits/{ci['visit_id']}/prescriptions", headers=auth["doctor"],
                     json={"drug_name": "Artemether-Lumefantrine 80/480mg", "dose": "4 tabs", "frequency": "BD", "duration_days": 3})
    assert rx.status_code == 201

    signed = client.post(f"/api/ehr/notes/{note.json()['id']}/sign", headers=auth["doctor"])
    assert signed.status_code == 200 and signed.json()["status"] == "signed" and signed.json()["content_hash"]

    # immutable after signing; addendum is the only way
    assert client.put(f"/api/ehr/visits/{ci['visit_id']}/note", headers=auth["doctor"],
                      json={"subjective": "changed"}).status_code == 409
    add = client.post(f"/api/ehr/notes/{note.json()['id']}/addendum", headers=auth["doctor"],
                      json={"text": "Patient called back: improving", "reason": "follow-up call"})
    assert add.status_code == 201 and len(add.json()["addenda"]) == 1

    # cascade: journey completed, lab/pharmacy steps recorded as deferred (modules not live)
    j = client.get(f"/api/visits/{ci['visit_id']}/journey", headers=auth["doctor"]).json()
    assert j["status"] == "completed"
    assert {s["department"]: s["status"] for s in j["steps"]} == {
        "TRIAGE": "completed", "OPD-GEN": "completed", "LAB": "deferred", "PHARM": "deferred"}

    # events the future Billing/Inventory modules will consume are already in the outbox
    types = [e["type"] for e in client.get("/api/admin/events?limit=200", headers=auth["admin"]).json()]
    for needed in ("VisitCheckedIn", "TriageCompleted", "NoteSigned", "LabOrdered", "Prescribed", "JourneyClinicalCompleted"):
        assert needed in types
    audit = client.get("/api/admin/audit", headers=auth["admin"]).json()
    assert any(a["action"] == "sign" for a in audit)


def test_sign_requires_icd10_and_content(client, auth, make_patient, check_in):
    ci = check_in(make_patient()["id"])
    n = client.put(f"/api/ehr/visits/{ci['visit_id']}/note", headers=auth["doctor"],
                   json={"subjective": "x cough", "assessment": "URTI"}).json()
    assert client.post(f"/api/ehr/notes/{n['id']}/sign", headers=auth["doctor"]).status_code == 422


def test_allergy_hard_block_and_documented_override(client, auth, make_patient, check_in):
    p = make_patient(allergies=[{"allergen_name": "Penicillin", "reaction": "throat swelling", "severity": "severe"}])
    ci = check_in(p["id"])
    blocked = client.post(f"/api/ehr/visits/{ci['visit_id']}/prescriptions", headers=auth["doctor"],
                          json={"drug_name": "Augmentin 625mg"})        # brand of a penicillin
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "allergy_conflict"
    ok = client.post(f"/api/ehr/visits/{ci['visit_id']}/prescriptions", headers=auth["doctor"],
                     json={"drug_name": "Ciprofloxacin 500mg"})
    assert ok.status_code == 201 and ok.json()["allergy_overridden"] is False
    ov = client.post(f"/api/ehr/visits/{ci['visit_id']}/prescriptions", headers=auth["doctor"],
                     json={"drug_name": "Amoxicillin 500mg", "allergy_override_reason": "Tolerated before; infective endocarditis"})
    assert ov.status_code == 201 and ov.json()["allergy_overridden"] is True
    actions = [a["action"] for a in client.get("/api/admin/audit", headers=auth["admin"]).json()]
    assert "allergy_block" in actions and "allergy_override" in actions


def test_critical_vitals_force_emergency_priority(client, auth, make_patient, check_in):
    ci = check_in(make_patient()["id"])
    v = client.post(f"/api/ehr/visits/{ci['visit_id']}/triage", headers=auth["nurse"],
                    json={"spo2": 85, "temperature": 37.0, "triage_priority": "NORMAL"}).json()
    assert v["triage_priority"] == "EMERGENCY"
    opd = client.get("/api/queues/OPD-GEN", headers=auth["doctor"]).json()
    mine = [t for t in opd["waiting"] if t["visit_id"] == ci["visit_id"]][0]
    assert mine["priority"] == "EMERGENCY"


def test_nurse_cannot_write_notes_doctor_cannot_register(client, auth, make_patient, check_in):
    ci = check_in(make_patient()["id"])
    assert client.put(f"/api/ehr/visits/{ci['visit_id']}/note", headers=auth["nurse"], json={}).status_code == 403
    assert client.post("/api/patients", headers=auth["doctor"], json={}).status_code == 403
