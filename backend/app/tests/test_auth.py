"""Institution self-registration."""
from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app

init_db()
client = TestClient(app)

SIGNUP = {"name": "Dr. Test Principal", "email": "principal@newcollege.test", "password": "Secure123",
          "institution_name": "New Test College of Engineering", "aicte_id": "1-TEST-90001", "state": "Goa"}


def test_signup_creates_institution_account_and_signs_in():
    r = client.post("/api/auth/signup", json=SIGNUP)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["role"] == "institution" and body["institution"]["aicte_id"] == "1-TEST-90001"
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
    assert me.json()["user"]["email"] == "principal@newcollege.test"


def test_signup_rejects_duplicates_and_weak_passwords():
    assert client.post("/api/auth/signup", json=SIGNUP).status_code == 409  # same email
    other = {**SIGNUP, "email": "someone@else.test"}
    assert client.post("/api/auth/signup", json=other).status_code == 409  # institution already has an account
    weak = {**SIGNUP, "email": "weak@x.test", "aicte_id": "1-TEST-90002", "password": "onlyletters"}
    assert client.post("/api/auth/signup", json=weak).status_code == 400


def test_signup_cannot_create_officer_accounts():
    r = client.post("/api/auth/signup", json={**SIGNUP, "email": "sneaky@x.test", "aicte_id": "1-TEST-90004", "role": "officer"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "institution"
