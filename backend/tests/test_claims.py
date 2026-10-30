from backend import db


def test_list_claims(client):
    response = client.get("/api/claims")
    assert response.status_code == 200
    claims = response.json()
    assert len(claims) == 25
    assert all(claim["status"] == "waiting" for claim in claims)
    assert claims[0]["claim_id"] == "CLM-1001"


def test_get_claim(client):
    response = client.get("/api/claims/CLM-1001")
    assert response.status_code == 200
    claim = response.json()
    assert claim["policy"]["policy_id"] == "POL-2001"
    assert claim["customer_previous_claims"][0]["claim_id"] == "CLM-0412"
    assert claim["status"] == "waiting"


def test_get_unknown_claim(client):
    response = client.get("/api/claims/CLM-9999")
    assert response.status_code == 404


def test_list_sections(client):
    wording = client.get("/api/documents/policy_wording/sections").json()
    assert len(wording) == 12
    assert wording[0] == "1. Your plan"

    manual = client.get("/api/documents/claims_manual/sections").json()
    assert len(manual) == 14
    assert "10. Meals without receipts" in manual


def test_list_sections_unknown_document(client):
    response = client.get("/api/documents/not_a_document/sections")
    assert response.status_code == 404


def test_get_section(client):
    response = client.get(
        "/api/documents/policy_wording/section", params={"heading": "3. Trip Delay"}
    )
    assert response.status_code == 200
    assert "delay" in response.json()["text"].lower()

    response = client.get(
        "/api/documents/claims_manual/section",
        params={"heading": "9. Repeat claims"},
    )
    assert "12 months" in response.json()["text"]


def test_get_section_unknown_heading(client):
    response = client.get(
        "/api/documents/claims_manual/section",
        params={"heading": "99. No such section"},
    )
    assert response.status_code == 404


def test_list_handlers(client):
    response = client.get("/api/handlers")
    assert response.status_code == 200
    handlers = response.json()
    assert len(handlers) == 3
    assert all(h["can_approve_over_limit"] for h in handlers)


def test_seeding_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    db.connect().close()
    conn = db.connect()
    count = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    conn.close()
    assert count == 25
