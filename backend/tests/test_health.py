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


def test_request_run_persists_recommendation_and_progress(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / "run.sqlite3"))
    monkeypatch.setattr(
        "backend.main.run_agent",
        lambda request_id, thread_id: {
            "outcome": "request_information",
            "rationale": "Need the item photo.",
            "policy_citations": ["Returns Policy"],
            "next_action": "Ask support agent to request a photo.",
            "priority_human_review": False,
        },
    )
    with TestClient(app) as client:
        response = client.post("/api/requests/REQ-7001/run")
        detail = client.get("/api/requests/REQ-7001").json()
        duplicate = client.post("/api/requests/REQ-7001/run")

    assert response.status_code == 200
    assert response.json() == {"request_id": "REQ-7001", "status": "in_progress"}
    assert detail["status"] == "waiting_for_agent_review"
    assert detail["recommendation"]["outcome"] == "request_information"
    assert [step["stage"] for step in detail["steps"]] == [
        "started",
        "preparing_recommendation",
    ]
    assert duplicate.status_code == 200


def test_agent_progress_endpoint_and_failed_run(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / "failed.sqlite3"))
    monkeypatch.setattr(
        "backend.main.run_agent", lambda *args: (_ for _ in ()).throw(RuntimeError())
    )
    with TestClient(app) as client:
        started = client.post("/api/requests/REQ-7001/run")
        detail = client.get("/api/requests/REQ-7001").json()
        invalid_stage = client.post(
            "/api/requests/REQ-7001/steps", json={"stage": "finished"}
        )

    assert started.status_code == 200
    assert detail["status"] == "waiting_for_agent_review"
    assert detail["recommendation"] is None
    assert detail["steps"][-1]["stage"] == "error"
    assert invalid_stage.status_code == 422


def test_support_review_decides_without_running_an_order_action(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / "review.sqlite3"))
    monkeypatch.setattr(
        "backend.main.run_agent",
        lambda *args: {
            "outcome": "approve",
            "rationale": "Eligible under the sample policy.",
            "policy_citations": ["Cancellation Policy"],
            "next_action": "Support agent to review.",
            "priority_human_review": False,
        },
    )
    with TestClient(app) as client:
        client.post("/api/requests/REQ-7001/run")
        response = client.post(
            "/api/requests/REQ-7001/review",
            json={"outcome": "approve", "notes": "Confirmed by support."},
        )
        detail = client.get("/api/requests/REQ-7001").json()
        duplicate = client.post(
            "/api/requests/REQ-7001/review", json={"outcome": "approve"}
        )

    assert response.status_code == 200
    assert detail["status"] == "decided"
    assert detail["review"]["outcome"] == "approve"
    assert detail["review"]["notes"] == "Confirmed by support."
    assert detail["action_result"] is None
    assert duplicate.status_code == 409
