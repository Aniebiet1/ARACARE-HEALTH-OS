import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["ARACARE_DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["ARACARE_DATA_DIR"] = f"{_tmp}/data"
os.environ["ARACARE_LLM_ENGINE"] = "rules"      # tests never need Ollama
os.environ["ARACARE_ASR_ENGINE"] = "none"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, username):
    r = client.post("/api/auth/login", json={"username": username, "password": "demo123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="session")
def auth(client):
    return {u: _login(client, u) for u in ("reception", "nurse", "doctor", "admin")}


_counter = {"n": 0}


@pytest.fixture
def make_patient(client, auth):
    def _make(**over):
        _counter["n"] += 1
        n = _counter["n"]
        sur = ["Balogun", "Chukwu", "Danjuma", "Eze", "Fashola", "Garba", "Hassan", "Ibe", "Jegede", "Kalu",
               "Lawal", "Musa", "Nwosu", "Obi", "Peters", "Quadri", "Rabiu", "Suleiman", "Tijani", "Udo"]
        first = ["Amaka", "Bola", "Chidi", "Dayo", "Emeka", "Funke", "Gozie", "Halima", "Ifeoma", "Jide",
                 "Kemi", "Lola", "Musa", "Ngozi", "Ola", "Paul", "Rita", "Segun", "Tunde", "Uche"]
        body = {"surname": f"{sur[n % 20]}{n}", "first_name": f"{first[(n * 7) % 20]}{n * 13}", "phone": f"0803{n:07d}",
                "date_of_birth": f"{1960 + n % 40}-{1 + n % 12:02d}-{1 + n % 27:02d}", "gender": "female", **over}
        r = client.post("/api/patients", json=body, headers=auth["reception"])
        assert r.status_code == 201, r.text
        return r.json()
    return _make


@pytest.fixture
def check_in(client, auth):
    def _ci(patient_id, visit_type="new_complaint"):
        r = client.post(f"/api/patients/{patient_id}/check-in", json={"visit_type": visit_type}, headers=auth["reception"])
        assert r.status_code == 201, r.text
        return r.json()
    return _ci
