from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import update

from backend.main import app
from backend.store import Store, support_requests


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


def test_seed_refreshes_request_and_order_records_in_an_existing_database(tmp_path):
    store = Store(tmp_path / "evidence.sqlite3")
    store.initialize()
    with store.engine.begin() as connection:
        connection.execute(
            update(support_requests)
            .where(support_requests.c.request_id == "REQ-7002")
            .values(
                request_json='{"customer_message": "stale", "evidence": []}',
                order_json='{"items": []}',
            )
        )
    store.initialize()

    request = store.get_request("REQ-7002")

    assert request is not None
    assert "cracked handle" in request["request"]["customer_message"]
    references = [item["reference"] for item in request["request"]["evidence"]]
    assert "synthetic://evidence/EV-7002-3" in references
    assert request["order"]["items"][0]["name"] == "Ceramic travel mug, 450 ml"
    assert request["order"]["shipment"]["tracking_number"] == "SHP-2026-10002"


def test_every_request_has_evidence_and_a_fulfillment_timeline(tmp_path):
    store = Store(tmp_path / "timeline.sqlite3")
    store.initialize()

    for summary in store.list_requests():
        request = store.get_request(summary["request_id"])
        assert request is not None
        assert request["request"]["evidence"]
        events = request["order"]["fulfillment_events"]
        assert events[-1]["status"] == request["order"]["fulfillment_status"]


def test_final_runtime_queue_has_no_reference_decision_route(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / "runtime.sqlite3"))
    with TestClient(app) as client:
        queue = client.get("/api/requests")
        references = client.get("/api/evals/support_decisions.json")

    assert len(queue.json()) == 8
    assert references.status_code == 404
    api_routes = [route for route in app.routes if isinstance(route, APIRoute)]
    assert all("eval" not in route.path.casefold() for route in api_routes)


def test_request_queue_and_safe_detail(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / "queue.sqlite3"))
    with TestClient(app) as client:
        queue = client.get("/api/requests")
        detail = client.get("/api/requests/REQ-7001")
        missing = client.get("/api/requests/REQ-0000")

    assert queue.status_code == 200
    assert len(queue.json()) == 8
    assert {item["status"] for item in queue.json()} == {"waiting"}
    assert detail.status_code == 200
    request = detail.json()["request"]
    assert request["request_id"] == "REQ-7001"
    assert "reason_code" not in request
    assert "required_action" not in request
    assert "intent_summary" not in request
    assert "phone" not in detail.json()["customer"]
    assert detail.json()["order"]["order_id"] == "ORD-2026-10001"
    assert detail.json()["steps"] == []
    assert "history" not in detail.json()
    assert "action_result" not in detail.json()
    assert missing.status_code == 404


def test_api_routes_have_operation_ids_and_no_query_inputs():
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    assert routes
    for route in routes:
        assert route.operation_id
        assert route.endpoint.__doc__
        assert "\n" not in route.endpoint.__doc__
        assert route.dependant.query_params == []
    post_paths = {route.path for route in routes if "POST" in (route.methods or set())}
    assert post_paths == {
        "/api/runs",
        "/api/runs/{run_id}/todos/{request_id}",
        "/api/requests/{request_id}/steps",
        "/api/requests/{request_id}/refund",
        "/api/requests/{request_id}/start",
        "/api/requests/{request_id}/recommendation",
        "/api/requests/{request_id}/failure",
        "/api/requests/{request_id}/review",
    }
