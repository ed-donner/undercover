import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from backend.main import app
from backend.policies import policy_for_request_type
from backend.store import Store


def test_health(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / "health.sqlite3"))
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_seed_is_idempotent(tmp_path):
    store = Store(tmp_path / "seed.sqlite3")
    store.initialize()
    store.initialize()
    assert len(store.list_requests()) == 8


def test_request_queue_and_safe_detail(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / "queue.sqlite3"))
    with TestClient(app) as client:
        queue = client.get("/api/requests")
        detail = client.get("/api/requests/REQ-7001")
        missing = client.get("/api/requests/REQ-0000")

    assert queue.status_code == 200
    assert len(queue.json()) == 8
    assert {item["status"] for item in queue.json()} == {"waiting", "decided"}
    assert detail.status_code == 200
    request = detail.json()["request"]
    assert request["request_id"] == "REQ-7001"
    assert "reason_code" not in request
    assert "required_action" not in request
    assert "intent_summary" not in request
    assert "phone" not in detail.json()["customer"]
    assert detail.json()["order"]["order_id"] == "ORD-2026-10001"
    assert detail.json()["steps"] == []
    assert missing.status_code == 404


def test_api_routes_have_operation_ids_and_no_query_inputs():
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    assert routes
    for route in routes:
        assert route.operation_id
        assert route.endpoint.__doc__
        assert "\n" not in route.endpoint.__doc__
        assert route.dependant.query_params == []


def test_policy_context_and_read_only_instructions(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / "context.sqlite3"))
    with TestClient(app) as client:
        cancellation = client.get("/api/requests/REQ-7001/context").json()
        returns = client.get("/api/requests/REQ-7003/context").json()
        missing = client.get("/api/requests/REQ-0000/context")
        instructions = client.get("/api/agent/instructions")

    assert "Cancellation Policy" in cancellation["policy"]["content"]
    assert cancellation["request"]["request_id"] == "REQ-7001"
    assert "reason_code" not in cancellation["request"]
    assert "required_action" not in cancellation["request"]
    assert "email" not in cancellation["customer"]
    assert "phone" not in cancellation["customer"]
    assert "Return" in returns["policy"]["name"]
    assert "Returns, Replacements, and Refunds" in returns["policy"]["content"]
    assert missing.status_code == 404
    assert instructions.status_code == 200
    assert instructions.json()["instructions"].startswith("You are the Shoppie Agent")
    assert set(instructions.json()) == {"instructions"}


def test_policy_selection_includes_shopping_and_rejects_unknown_types():
    assert "Shopping Policy" in policy_for_request_type("order_question")["content"]
    assert "Shopping" in policy_for_request_type("product_question")["name"]
    with pytest.raises(KeyError):
        policy_for_request_type("unknown")


def test_request_context_rejects_an_unsupported_type(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / "unsupported.sqlite3"))
    monkeypatch.setattr(
        Store, "get_request", lambda store, request_id: {"request": {"type": "unknown"}}
    )
    with TestClient(app) as client:
        response = client.get("/api/requests/REQ-7001/context")
    assert response.status_code == 422
