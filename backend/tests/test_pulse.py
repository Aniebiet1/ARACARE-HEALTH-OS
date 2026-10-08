"""AraPulse: department channels, direct messages, alerts, Pulse Codes with escalation, and the socket."""
from datetime import timedelta

import pytest
from starlette.websockets import WebSocketDisconnect

from app.db import SessionLocal
from app.modules.pulse import service
from app.modules.pulse.models import PulsePage

from .test_lab import ensure_dept, ensure_ward, make_staff, signed_visit


def _me(client, headers):
    return client.get("/api/auth/me", headers=headers).json()


def _channel(client, headers, **match):
    return next(c for c in client.get("/api/pulse/channels", headers=headers).json()
                if all(c.get(k) == v for k, v in match.items()))


def _messages(client, headers, channel_id):
    return client.get(f"/api/pulse/channels/{channel_id}/messages", headers=headers).json()


# ------------------------------------------------------------------ channels
def test_departments_talk_to_each_other(client, auth):
    emerg = ensure_dept("PT-EMERG", "Emergency (A&E)")
    _, lab = make_staff("pulse.lab", "lab", position="Lab Technician")
    chans = client.get("/api/pulse/channels", headers=auth["nurse"]).json()
    assert chans[0]["kind"] == "broadcast" and chans[0]["name"] == "All staff"
    ch = next(c for c in chans if c["department_id"] == emerg)
    assert ch["kind"] == "department" and ch["slug"] == "emergency" and ch["department_code"] == "PT-EMERG"

    # the lab is not in A&E but can still read and answer there: cross-department talk is the point
    r = client.post(f"/api/pulse/channels/{ch['id']}/messages", headers=auth["nurse"],
                    json={"body": "Bed 3 sample is ready for pickup"})
    assert r.status_code == 201 and r.json()["sender"]["role"] == "nurse"
    assert _channel(client, lab, id=ch["id"])["unread"] >= 1
    assert client.post(f"/api/pulse/channels/{ch['id']}/messages", headers=lab,
                       json={"body": "Porter on the way"}).status_code == 201
    msgs = _messages(client, auth["nurse"], ch["id"])
    assert [m["body"] for m in msgs[-2:]] == ["Bed 3 sample is ready for pickup", "Porter on the way"]
    assert client.post(f"/api/pulse/channels/{ch['id']}/read", headers=lab).status_code == 200
    assert _channel(client, lab, id=ch["id"])["unread"] == 0
    assert _channel(client, auth["nurse"], id=ch["id"])["last_message"]["body"] == "Porter on the way"
    assert client.post(f"/api/pulse/channels/{ch['id']}/messages", headers=lab,
                       json={"body": "x", "priority": "panic"}).status_code == 422


def test_broadcast_counts_toward_everyones_badge(client, auth):
    b = _channel(client, auth["doctor"], kind="broadcast")
    client.post(f"/api/pulse/channels/{b['id']}/read", headers=auth["doctor"])
    before = client.get("/api/pulse/summary", headers=auth["doctor"]).json()["unread_messages"]
    client.post(f"/api/pulse/channels/{b['id']}/messages", headers=auth["admin"],
                json={"body": "Generator test at 2pm: expect a 10 second power dip"})
    s = client.get("/api/pulse/summary", headers=auth["doctor"]).json()
    assert s["unread_messages"] == before + 1 and s["on_duty"] is True


def test_direct_messages_are_private(client, auth):
    doc = _me(client, auth["doctor"])
    r1 = client.post("/api/pulse/channels/direct", headers=auth["nurse"], json={"staff_id": doc["id"]})
    r2 = client.post("/api/pulse/channels/direct", headers=auth["nurse"], json={"staff_id": doc["id"]})
    assert r1.status_code == 200 and r1.json()["id"] == r2.json()["id"]          # idempotent
    assert r1.json()["kind"] == "direct" and r1.json()["other"]["id"] == doc["id"]
    cid = r1.json()["id"]
    client.post(f"/api/pulse/channels/{cid}/messages", headers=auth["nurse"], json={"body": "Can you review bed 4?"})
    assert _channel(client, auth["doctor"], id=cid)["other"]["role"] == "nurse"
    assert client.get(f"/api/pulse/channels/{cid}/messages", headers=auth["reception"]).status_code == 404
    assert all(c["id"] != cid for c in client.get("/api/pulse/channels", headers=auth["reception"]).json())
    me = _me(client, auth["nurse"])
    assert client.post("/api/pulse/channels/direct", headers=auth["nurse"],
                       json={"staff_id": me["id"]}).status_code == 422


def test_critical_message_needs_a_colleague_to_acknowledge(client, auth, make_patient):
    p = make_patient()
    b = _channel(client, auth["nurse"], kind="broadcast")
    m = client.post(f"/api/pulse/channels/{b['id']}/messages", headers=auth["nurse"],
                    json={"body": "Blood bank: O-negative needed for this patient", "priority": "critical",
                          "patient_id": p["id"]}).json()
    assert m["ack_required"] and m["patient"]["patient_number"] == p["patient_number"]
    assert client.post(f"/api/pulse/messages/{m['id']}/ack", headers=auth["nurse"]).status_code == 409
    r = client.post(f"/api/pulse/messages/{m['id']}/ack", headers=auth["doctor"])
    assert r.status_code == 200 and r.json()["acknowledged_by"]["name"] and r.json()["acknowledged_at"]


def test_orders_appear_in_lab_and_pharmacy_channels(client, auth, make_patient, check_in):
    lab_dept = ensure_dept("LAB", "Laboratory", "diagnostic")
    ph_dept = ensure_dept("PHARM", "Pharmacy", "support")
    p, v, _, _ = signed_visit(client, auth, make_patient, check_in, labs=[("LAB-MAL", "Malaria RDT", "stat")],
                              drugs=["Paracetamol 500mg"])
    lab_ch = _channel(client, auth["nurse"], department_id=lab_dept)
    m = _messages(client, auth["nurse"], lab_ch["id"])[-1]
    assert m["kind"] == "lab_order" and m["sender"] is None and m["priority"] == "urgent"
    assert "Malaria RDT (STAT)" in m["body"] and m["patient"]["id"] == p["id"] and m["payload"]["visit_id"] == v
    ph = _messages(client, auth["nurse"], _channel(client, auth["nurse"], department_id=ph_dept)["id"])[-1]
    assert ph["kind"] == "prescription" and "Paracetamol" in ph["body"]


# ------------------------------------------------------------------ alerts
def test_critical_vitals_alert_every_on_duty_doctor_and_one_ack_closes_all(client, auth, make_patient, check_in):
    d2_id, d2 = make_staff("pulse.doc.vitals", "doctor", name="Dr. Kelechi Nwosu")
    p = make_patient()
    v = check_in(p["id"])["visit_id"]
    client.post(f"/api/ehr/visits/{v}/triage", headers=auth["nurse"], json={"spo2": 84, "pulse_rate": 140})
    mine = [a for a in client.get("/api/pulse/alerts", headers=auth["doctor"]).json() if a["visit_id"] == v]
    theirs = [a for a in client.get("/api/pulse/alerts", headers=d2).json() if a["visit_id"] == v]
    assert mine and theirs and mine[0]["kind"] == "critical_vitals" and mine[0]["priority"] == "critical"
    assert "SpO2 84%" in mine[0]["body"]
    client.post(f"/api/pulse/alerts/{theirs[0]['id']}/ack", headers=d2)
    assert not [a for a in client.get("/api/pulse/alerts", headers=auth["doctor"]).json() if a["visit_id"] == v]
    closed = next(a for a in client.get("/api/pulse/alerts?status=all", headers=auth["doctor"]).json()
                  if a["visit_id"] == v)
    assert closed["acked_by"]["id"] == d2_id


# ------------------------------------------------------------------ Pulse Codes
@pytest.fixture
def icu():
    dept = ensure_dept("PT-ICU", "Intensive Care test", "ward")
    ward = ensure_ward("PT-ICU-W", "ICU test ward", dept)
    doc_id, doc = make_staff("pulse.icu.doc", "doctor", department_id=dept, position="Registrar",
                             name="Dr. Ada Obi")
    return {"dept": dept, "ward": ward, "doc_id": doc_id, "doc": doc}


def test_code_blue_reaches_the_ward_doctor_with_patient_stats(client, auth, make_patient, check_in, icu):
    p = make_patient(allergies=[{"allergen_name": "Penicillin", "severity": "severe", "reaction": "Rash"}],
                     blood_group="O+")
    v = check_in(p["id"])["visit_id"]
    client.post(f"/api/ehr/visits/{v}/triage", headers=auth["nurse"],
                json={"bp_systolic": 76, "bp_diastolic": 40, "pulse_rate": 38, "spo2": 82})
    r = client.post("/api/pulse/pages", headers=auth["nurse"],
                    json={"code": "code_blue", "ward_id": icu["ward"], "bed": "4", "patient_id": p["id"],
                          "note": "No pulse, CPR started"})
    assert r.status_code == 201, r.text
    page = r.json()
    assert page["status"] == "paging" and page["code_label"] == "Code Blue" and page["duplicate"] is False
    assert [t["id"] for t in page["targets"]] == [icu["doc_id"]]        # on-duty doctor of the ward's department
    assert page["ward"]["name"] == "ICU test ward" and page["bed"] == "4"
    pt = page["patient"]
    assert pt["allergies"][0]["allergen_name"] == "Penicillin" and pt["age"] >= 0 and pt["gender"] == "female"
    assert pt["latest_vitals"]["spo2"] == 82 and pt["latest_vitals"]["flags"] and pt["active_visit_id"] == v
    assert "blood_group" in pt and "diagnoses" in pt

    # the ward doctor sees it on their summary; the channel got a system line
    s = client.get("/api/pulse/summary", headers=icu["doc"]).json()
    assert any(x["id"] == page["id"] for x in s["active_pages_for_me"])
    line = _messages(client, auth["nurse"], _channel(client, auth["nurse"], department_id=icu["dept"])["id"])[-1]
    assert line["kind"] == "page" and "CODE BLUE" in line["body"] and "bed 4" in line["body"]

    # a second press for the same patient and code does not create a second emergency
    dup = client.post("/api/pulse/pages", headers=auth["nurse"],
                      json={"code": "code_blue", "ward_id": icu["ward"], "patient_id": p["id"]})
    assert dup.status_code == 200 and dup.json()["id"] == page["id"] and dup.json()["duplicate"] is True

    # reception is not a target and not a doctor
    assert client.post(f"/api/pulse/pages/{page['id']}/ack", headers=auth["reception"]).status_code == 403
    ack = client.post(f"/api/pulse/pages/{page['id']}/ack", headers=icu["doc"], json={"eta_minutes": 2}).json()
    assert ack["status"] == "acknowledged" and ack["responder"]["id"] == icu["doc_id"] and ack["eta_minutes"] == 2
    assert ack["response_seconds"] is not None and ack["acked_at"]
    again = client.post(f"/api/pulse/pages/{page['id']}/ack", headers=auth["doctor"])
    assert again.status_code == 409 and "already responding" in again.json()["detail"]
    assert client.post(f"/api/pulse/pages/{page['id']}/arrive", headers=auth["doctor"]).status_code == 409
    assert client.post(f"/api/pulse/pages/{page['id']}/arrive", headers=icu["doc"]).json()["status"] == "arrived"
    assert client.post(f"/api/pulse/pages/{page['id']}/cancel", headers=auth["nurse"]).status_code == 409
    done = client.post(f"/api/pulse/pages/{page['id']}/resolve", headers=icu["doc"],
                       json={"outcome": "ROSC after 2 cycles, transferred to ICU bed 2"}).json()
    assert done["status"] == "resolved" and done["outcome"].startswith("ROSC")
    assert all(x["id"] != page["id"] for x in client.get("/api/pulse/pages?scope=active", headers=auth["nurse"]).json())
    assert any(x["id"] == page["id"] for x in client.get("/api/pulse/pages?scope=mine", headers=auth["nurse"]).json())


def test_named_target_and_cancel_rules(client, auth, icu):
    doc = _me(client, auth["doctor"])
    r = client.post("/api/pulse/pages", headers=auth["nurse"],
                    json={"code": "urgent_review", "ward_id": icu["ward"], "bed": "9", "target_staff_id": doc["id"]})
    page = r.json()
    assert [t["id"] for t in page["targets"]] == [doc["id"]] and page["patient"] is None
    assert client.post(f"/api/pulse/pages/{page['id']}/cancel", headers=auth["reception"]).status_code == 403
    c = client.post(f"/api/pulse/pages/{page['id']}/cancel", headers=auth["nurse"], json={"reason": "Wrong bed"})
    assert c.status_code == 200 and c.json()["status"] == "cancelled" and c.json()["outcome"] == "Wrong bed"
    assert client.post("/api/pulse/pages", headers=auth["nurse"],
                       json={"code": "code_red", "ward_id": icu["ward"]}).status_code == 422
    assert client.post("/api/pulse/pages", headers=auth["nurse"],
                       json={"code": "trauma", "ward_id": "nope"}).status_code == 404


def test_unanswered_page_widens_to_all_on_duty_then_all_doctors(client, auth, icu):
    off_id, _ = make_staff("pulse.offduty.doc", "doctor", on_duty=False, name="Dr. Off Duty")
    page = client.post("/api/pulse/pages", headers=auth["nurse"],
                       json={"code": "rapid_response", "ward_id": icu["ward"], "bed": "7"}).json()
    doc = _me(client, auth["doctor"])
    assert doc["id"] not in [t["id"] for t in page["targets"]]

    def backdate_and_tick(seconds=130):
        with SessionLocal() as db:
            pg = db.get(PulsePage, page["id"])
            pg.created_at -= timedelta(seconds=seconds)
            if pg.escalated_at:
                pg.escalated_at -= timedelta(seconds=seconds)
            db.commit()
            service.tick(db)
            db.commit()
        return client.get(f"/api/pulse/pages/{page['id']}", headers=auth["nurse"]).json()

    p1 = backdate_and_tick()
    ids = [t["id"] for t in p1["targets"]]
    assert p1["escalation_level"] == 1 and p1["escalated_at"] and doc["id"] in ids and off_id not in ids
    with SessionLocal() as db:              # immediately again: nothing to do
        service.tick(db)
        db.commit()
    assert client.get(f"/api/pulse/pages/{page['id']}", headers=auth["nurse"]).json()["escalation_level"] == 1
    raiser_alerts = client.get("/api/pulse/alerts", headers=auth["nurse"]).json()
    assert any(a["kind"] == "page_escalated" and a["ref_id"] == page["id"] for a in raiser_alerts)

    p2 = backdate_and_tick()
    assert p2["escalation_level"] == 2 and off_id in [t["id"] for t in p2["targets"]]
    assert backdate_and_tick()["escalation_level"] == 2          # nobody left to add: it stops
    assert client.post(f"/api/pulse/pages/{page['id']}/ack", headers=auth["doctor"]).json()["status"] == "acknowledged"


def test_admin_stats(client, auth, icu):
    assert client.get("/api/pulse/stats", headers=auth["nurse"]).status_code == 403
    s = client.get("/api/pulse/stats", headers=auth["admin"]).json()
    assert {"pages_today", "open_pages", "median_ack_seconds", "messages_today", "open_alerts", "by_code",
            "recent_pages"} <= set(s)
    assert [c["code"] for c in s["by_code"]][0] == "code_blue" and all(p["patient"] is None for p in s["recent_pages"])
    assert [c["label"] for c in client.get("/api/pulse/codes", headers=auth["nurse"]).json()] == [
        "Code Blue", "Obstetric Emergency", "Trauma Call", "Rapid Response", "Urgent Review"]


def test_patient_lookup(client, auth, make_patient):
    p = make_patient(surname="Pulsefinder")
    assert client.get("/api/pulse/patients?q=P", headers=auth["nurse"]).status_code == 422
    rows = client.get("/api/pulse/patients?q=Pulsefinder", headers=auth["nurse"]).json()
    assert any(r["id"] == p["id"] and r["patient_number"] for r in rows)


# ------------------------------------------------------------------ socket
def test_socket_rejects_bad_tokens(client):
    with pytest.raises(WebSocketDisconnect) as e:
        with client.websocket_connect("/api/ws/pulse?token=not-a-token") as ws:
            ws.receive_json()
    assert e.value.code == 4401


def test_socket_tells_the_paged_doctor_without_patient_data(client, auth, icu):
    token = icu["doc"]["Authorization"].removeprefix("Bearer ")
    with client.websocket_connect(f"/api/ws/pulse?token={token}") as ws:
        page = client.post("/api/pulse/pages", headers=auth["nurse"],
                           json={"code": "obstetric", "ward_id": icu["ward"], "bed": "S1"}).json()
        for _ in range(10):
            msg = ws.receive_json()
            assert set(msg) <= {"event", "id"}
            if msg["event"] == "page":
                assert msg["id"] == page["id"]
                break
        else:
            pytest.fail("no page event")
    client.post(f"/api/pulse/pages/{page['id']}/cancel", headers=auth["nurse"])


def test_queue_socket_still_works(client):
    with client.websocket_connect("/api/ws/queue") as ws:
        ws.send_text("ping")
