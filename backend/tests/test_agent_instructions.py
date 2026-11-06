from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_get_agent_instructions():
    response = client.get("/api/agent-instructions")
    assert response.status_code == 200
    assert "policy wording" in response.json()["content"]
