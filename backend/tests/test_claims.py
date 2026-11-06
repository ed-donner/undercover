from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_list_claims():
    response = client.get("/api/claims")
    assert response.status_code == 200
    claims = response.json()
    assert len(claims) == 25
    assert all(claim["status"] == "waiting" for claim in claims)
    assert all(claim["decision"] is None for claim in claims)


def test_get_claim():
    response = client.get("/api/claims/CLM-1003")
    assert response.status_code == 200
    claim = response.json()
    assert claim["claim_id"] == "CLM-1003"
    assert claim["amount_claimed"] == 3800.0
    assert claim["policy"]["plan"] == "premium"
    assert claim["policy"]["plan_limits"]["emergency_medical_max"] == 100000.0
    assert claim["policy"]["plan_limits"]["deductible"] == 50.0
    assert claim["customer"]["customer_id"] == claim["customer_id"]
    assert isinstance(claim["customer"]["previous_claims"], list)


def test_get_claim_not_found():
    response = client.get("/api/claims/CLM-9999")
    assert response.status_code == 404
