from datetime import timedelta

from app.db import SessionLocal, utcnow
from app.modules.queues import service
from app.modules.queues.models import Ticket


def _make_waiting(client, auth, make_patient, check_in, n, **kw):
    out = []
    for _ in range(n):
        p = make_patient(**kw.get("patient", {}))
        out.append(check_in(p["id"], kw.get("visit_type", "new_complaint")))
    return out


def _drain_triage(client, auth):
    """Clear leftover tickets from earlier tests so ordering assertions are deterministic."""
    while client.post("/api/queues/TRIAGE/call-next", json={}, headers=auth["nurse"]).status_code == 200:
        pass
    with SessionLocal() as db:
        for t in db.query(Ticket).filter(Ticket.status.in_(("called", "no_show", "waiting"))).all():
            t.status = "completed"
        db.commit()


def test_emergency_jumps_queue_and_elders_outrank_adults(client, auth, make_patient, check_in):
    _drain_triage(client, auth)
    normal = check_in(make_patient()["id"])
    elder = check_in(make_patient(date_of_birth="1950-01-01")["id"])               # 65+ -> HIGH
    emerg = check_in(make_patient()["id"], "emergency")
    order = [t["visit_id"] for t in client.get("/api/queues/TRIAGE", headers=auth["nurse"]).json()["waiting"]]
    assert order == [emerg["visit_id"], elder["visit_id"], normal["visit_id"]]
    assert client.post("/api/queues/TRIAGE/call-next", json={}, headers=auth["nurse"]).json()["visit_id"] == emerg["visit_id"]


def test_weighted_fair_queuing_prevents_starvation(client, auth, make_patient, check_in):
    _drain_triage(client, auth)
    normal = check_in(make_patient()["id"])                                         # arrived first
    highs = [check_in(make_patient(date_of_birth="1950-01-01")["id"]) for _ in range(5)]
    served = []
    for _ in range(4):
        served.append(client.post("/api/queues/TRIAGE/call-next", json={}, headers=auth["nurse"]).json()["visit_id"])
    # burst limit is 3: after 3 HIGH, the waiting NORMAL patient gets a turn
    assert served[:3] == [h["visit_id"] for h in highs[:3]]
    assert served[3] == normal["visit_id"]


def test_aging_promotes_long_waiters(client, auth, make_patient, check_in):
    _drain_triage(client, auth)
    old = check_in(make_patient()["id"])
    new_high = check_in(make_patient(date_of_birth="1950-01-01")["id"])
    with SessionLocal() as db:   # pretend the NORMAL patient has waited 50 minutes
        t = db.query(Ticket).filter(Ticket.visit_id == old["visit_id"]).one()
        t.entered_waiting_at = utcnow() - timedelta(minutes=50)
        db.commit()
    order = client.get("/api/queues/TRIAGE", headers=auth["nurse"]).json()["waiting"]
    assert order[0]["visit_id"] == old["visit_id"] and order[0]["aged"] is True


def test_no_show_rejoin_and_second_no_show_cancels(client, auth, make_patient, check_in):
    _drain_triage(client, auth)
    ci = check_in(make_patient()["id"])
    t = client.post("/api/queues/TRIAGE/call-next", json={}, headers=auth["nurse"]).json()
    ns = client.post(f"/api/tickets/{t['id']}/no-show", headers=auth["nurse"]).json()
    assert ns["status"] == "no_show"
    back = client.post(f"/api/tickets/{t['id']}/rejoin", headers=auth["reception"]).json()
    assert back["status"] == "waiting"
    t2 = client.post("/api/queues/TRIAGE/call-next", json={}, headers=auth["nurse"]).json()
    assert client.post(f"/api/tickets/{t2['id']}/no-show", headers=auth["nurse"]).json()["status"] == "cancelled"
    assert client.get(f"/api/visits/{ci['visit_id']}/journey", headers=auth["nurse"]).json()["status"] == "abandoned"


def test_sweeper_times_out_called_tickets(client, auth, make_patient, check_in):
    _drain_triage(client, auth)
    check_in(make_patient()["id"])
    t = client.post("/api/queues/TRIAGE/call-next", json={}, headers=auth["nurse"]).json()
    with SessionLocal() as db:
        row = db.get(Ticket, t["id"])
        row.called_at = utcnow() - timedelta(seconds=400)
        db.commit()
        assert service.tick(db) == 1
        db.commit()
    assert [x["status"] for x in client.get("/api/queues/TRIAGE", headers=auth["nurse"]).json()["active"]
            if x["id"] == t["id"]] == ["no_show"]


def test_public_tv_display_has_no_full_names(client, auth, make_patient, check_in):
    _drain_triage(client, auth)
    p = make_patient(surname="Okonkwo", first_name="Adaeze")
    check_in(p["id"])
    client.post("/api/queues/TRIAGE/call-next", json={"counter": "Triage 1"}, headers=auth["nurse"])
    tv = client.get("/api/display/TRIAGE").json()            # no auth: it's a TV
    assert tv["now_serving"][0]["who"] == "A. OKONKWO"
    assert "Adaeze" not in str(tv) and "phone" not in str(tv)


def test_tv_shows_estimated_wait_for_each_waiting_patient(client, auth, make_patient, check_in):
    _drain_triage(client, auth)
    _make_waiting(client, auth, make_patient, check_in, 3)
    etas = [t["eta_min"] for t in client.get("/api/display/TRIAGE").json()["next_up"]]
    assert len(etas) == 3 and etas == sorted(etas) and etas[-1] > 0   # later in the queue never waits less
