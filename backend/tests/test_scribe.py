from app.modules.scribe import structure


def test_grounding_drops_numbers_not_in_transcript():
    t = "Blood pressure 120 over 80, temperature 38.4, pulse 92."
    v = structure.NurseVitals(bp_systolic=120, bp_diastolic=80, temperature=38.4, pulse_rate=92, spo2=98)  # 98 hallucinated
    clean, dropped = structure.ground_vitals(v, t)
    assert clean.spo2 is None and clean.temperature == 38.4
    assert dropped == ["spo2=98 (not found in transcript)"]


def test_rules_nurse_extraction():
    t = ("Patient complains of fever and headache since yesterday. Blood pressure 120 over 80, temperature 38.4, "
         "pulse 92, respiratory rate 18, SpO2 98, weight 62 kg, height 163 cm, pain score 4.")
    d = structure.rules_nurse(t)
    assert (d.vitals.bp_systolic, d.vitals.bp_diastolic, d.vitals.temperature) == (120, 80, 38.4)
    assert (d.vitals.pulse_rate, d.vitals.respiratory_rate, d.vitals.spo2) == (92, 18, 98)
    assert (d.vitals.weight_kg, d.vitals.height_cm, d.vitals.pain_score) == (62, 163, 4)
    assert "fever and headache" in d.chief_complaint


def test_consent_gate_then_draft_then_accept_via_note(client, auth, make_patient, check_in):
    ci = check_in(make_patient()["id"])
    text = "Fever and headache for two days with chills. On examination he is febrile with mild pallor. " \
           "I think this is malaria. Send for malaria RDT and FBC. Prescribe artemether-lumefantrine and paracetamol. Review in 3 days."
    # 1. no consent -> blocked
    r = client.post("/api/scribe/draft", json={"visit_id": ci["visit_id"], "transcript": text}, headers=auth["doctor"])
    assert r.status_code == 403
    # 2. consent recorded -> draft is produced
    assert client.post("/api/scribe/consent", json={"visit_id": ci["visit_id"], "granted": True}, headers=auth["doctor"]).status_code == 200
    r = client.post("/api/scribe/draft", json={"visit_id": ci["visit_id"], "transcript": text}, headers=auth["doctor"])
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "ai_draft" and body["engine"]["llm"].startswith("rules")
    assert body["draft"]["assessment"] and "malaria" in body["draft"]["assessment"].lower()
    assert any(s["code"] == "B50.9" or s["code"].startswith("B5") for s in body["icd10_suggestions"])
    assert {d["drug_name"].lower() for d in body["draft"]["suggested_drugs"]} >= {"artemether-lumefantrine", "paracetamol"}
    # 3. drafting writes NOTHING to the record
    assert client.get(f"/api/ehr/visits/{ci['visit_id']}", headers=auth["doctor"]).json()["note"] is None
    # 4. clinician saves the (edited) note, linking the session -> provenance recorded
    n = client.put(f"/api/ehr/visits/{ci['visit_id']}/note", headers=auth["doctor"], json={
        "subjective": body["draft"]["subjective"], "assessment": "Malaria", "diagnoses": ["B50.9"],
        "scribe_session_id": body["session_id"]}).json()
    assert client.get(f"/api/ehr/visits/{ci['visit_id']}", headers=auth["doctor"]).json()["note"]["source"] == "ai_scribe"
    signed = client.post(f"/api/ehr/notes/{n['id']}/sign", headers=auth["doctor"]).json()
    assert signed["source"] == "ai_scribe"


def test_nurse_scribe_drops_hallucinated_vitals_and_doctor_role_is_protected(client, auth, make_patient, check_in):
    ci = check_in(make_patient()["id"])
    client.post("/api/scribe/consent", json={"visit_id": ci["visit_id"], "granted": True}, headers=auth["nurse"])
    r = client.post("/api/scribe/draft", headers=auth["nurse"], json={
        "visit_id": ci["visit_id"], "transcript": "Temperature 38.4 pulse 92 blood pressure 120 over 80. Complains of cough."}).json()
    assert r["draft"]["vitals"]["temperature"] == 38.4 and r["draft"]["vitals"]["spo2"] is None
    # a nurse cannot ask for a doctor's SOAP draft
    assert client.post("/api/scribe/draft", headers=auth["nurse"], json={
        "visit_id": ci["visit_id"], "transcript": "some long dictation here", "role": "doctor"}).status_code == 403


def test_transcribe_degrades_gracefully_without_whisper(client, auth, make_patient, check_in):
    ci = check_in(make_patient()["id"])
    client.post("/api/scribe/consent", json={"visit_id": ci["visit_id"], "granted": True}, headers=auth["doctor"])
    r = client.post("/api/scribe/transcribe", data={"visit_id": ci["visit_id"]},
                    files={"audio": ("a.webm", b"fake", "audio/webm")}, headers=auth["doctor"])
    assert r.status_code == 503 and "type or paste" in r.json()["detail"]


# ---- local model paths, exercised with stubs (real Whisper/Ollama are installed on the hospital box) ----
def test_ollama_output_is_grounded_and_validated(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "llm_engine", "auto")
    hallucinated = {"vitals": {"temperature": 38.4, "pulse_rate": 92, "spo2": 99, "bp_systolic": 120, "bp_diastolic": 80},
                    "chief_complaint": "fever", "triage_priority": "URGENT-ISH"}      # spo2 never said; bad priority value
    monkeypatch.setattr(structure, "_ollama", lambda role, t, c: hallucinated)
    draft, dropped, engine = structure.build_draft("nurse", "Temperature 38.4, pulse 92, blood pressure 120 over 80. Fever.")
    assert engine.startswith("ollama:")
    assert draft["vitals"]["spo2"] is None and any("spo2" in d for d in dropped)
    assert draft["triage_priority"] == "NORMAL"                                          # invalid value normalised


def test_ollama_down_falls_back_to_rules(monkeypatch):
    import httpx
    from app.config import settings
    monkeypatch.setattr(settings, "llm_engine", "auto")
    def boom(*a, **k):
        raise httpx.ConnectError("no ollama")
    monkeypatch.setattr(structure.httpx, "post", boom)
    draft, _, engine = structure.build_draft("nurse", "Temperature 38.4 pulse 92. Complains of cough.")
    assert "rules" in engine and draft["vitals"]["temperature"] == 38.4


def test_transcribe_endpoint_with_stubbed_whisper_discards_audio(client, auth, make_patient, check_in, monkeypatch):
    import glob, tempfile
    from app.modules.scribe import asr
    seen = {}
    monkeypatch.setattr(asr, "available", lambda: True)
    def fake(path, language="en"):
        import os
        seen["existed"] = os.path.exists(path); seen["path"] = path
        return "Temperature 38.4 pulse 92"
    monkeypatch.setattr(asr, "transcribe", fake)
    ci = check_in(make_patient()["id"])
    # consent still required
    r0 = client.post("/api/scribe/transcribe", data={"visit_id": ci["visit_id"]},
                     files={"audio": ("a.webm", b"x", "audio/webm")}, headers=auth["nurse"])
    assert r0.status_code == 403
    client.post("/api/scribe/consent", json={"visit_id": ci["visit_id"], "granted": True}, headers=auth["nurse"])
    r = client.post("/api/scribe/transcribe", data={"visit_id": ci["visit_id"]},
                    files={"audio": ("a.webm", b"x", "audio/webm")}, headers=auth["nurse"])
    assert r.status_code == 200 and r.json()["transcript"] == "Temperature 38.4 pulse 92"
    import os
    assert seen["existed"] and not os.path.exists(seen["path"])       # temp audio deleted after use
