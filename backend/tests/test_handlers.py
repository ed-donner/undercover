from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_list_handlers():
    response = client.get("/api/handlers")
    assert response.status_code == 200
    handlers = response.json()
    assert len(handlers) == 3
    assert all(handler["can_approve_over_limit"] for handler in handlers)
    assert {handler["handler_id"] for handler in handlers} == {
        "HND-01",
        "HND-02",
        "HND-03",
    }
