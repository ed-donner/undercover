from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_get_policy_wording():
    response = client.get("/api/policy-wording")
    assert response.status_code == 200
    assert "Emergency Medical" in response.json()["content"]
