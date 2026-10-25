"""API smoke tests on an isolated temporary database."""





from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Institution, User  # noqa: E402
from app.security import hash_password  # noqa: E402

init_db()
_db = SessionLocal()
inst = Institution(aicte_id="1-TEST-1", name="Test Institute", trust_name="Test Trust")
_db.add(inst)
_db.flush()
_db.add(User(email="inst@test", role="institution", institution_id=inst.id, password_hash=hash_password("pw12345")))
_db.add(User(email="off@test", role="officer", password_hash=hash_password("pw12345")))
_db.commit()
client = TestClient(app)


def token(email):
    r = client.post("/api/auth/login", json={"email": email, "password": "pw12345"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_bad_login():
    assert client.post("/api/auth/login", json={"email": "off@test", "password": "nope"}).status_code == 401


def test_requires_auth():
    assert client.get("/api/applications").status_code == 401


def test_institution_creates_draft_officer_cannot_see_it():
    h = token("inst@test")
    r = client.post("/api/applications", json={"type": "EOA", "academic_year": "2026-27", "requested_intake": 240}, headers=h)
    assert r.status_code == 200
    app_id = r.json()["id"]
    assert client.get(f"/api/applications/{app_id}", headers=token("off@test")).status_code == 404


def test_upload_rejects_fake_pdf():
    h = token("inst@test")
    app_id = client.post("/api/applications", json={"type": "EOA", "academic_year": "2026-27", "requested_intake": 240},
                         headers=h).json()["id"]
    r = client.post(f"/api/applications/{app_id}/documents", data={"category": "affidavit"},
                    files={"files": ("x.pdf", b"MZ not a pdf", "application/pdf")}, headers=h)
    assert r.status_code == 400


def test_officer_cannot_create_application():
    r = client.post("/api/applications", json={"type": "EOA", "academic_year": "2026-27", "requested_intake": 1},
                    headers=token("off@test"))
    assert r.status_code == 403


def test_aph_ask_cites_clause():
    r = client.post("/api/aph/ask", json={"question": "What is the faculty student ratio for B.Tech?"}, headers=token("off@test"))
    body = r.json()
    assert r.status_code == 200 and "A7.2" in body["citations"]
