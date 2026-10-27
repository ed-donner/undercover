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


def test_get_policy_wording(client):
    response = client.get("/api/policy-wording")
    assert response.status_code == 200
    assert "Trip Delay" in response.json()["policy_wording"]


def test_seeding_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    db.connect().close()
    conn = db.connect()
    count = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    conn.close()
    assert count == 25
