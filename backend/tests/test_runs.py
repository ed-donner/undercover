import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.main import app
from backend.store import Store

RECOMMENDATION = {
    "outcome": "approve",
    "rationale": "Eligible under the sample policy.",
    "policy_citations": ["Cancellation Policy: 2. Customer-requested cancellations"],
    "next_action": "Support agent to review.",
    "priority_human_review": False,
}


@pytest.fixture
def store(tmp_path):
    result = Store(tmp_path / "runs.sqlite3")
    result.initialize()
    return result


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / "api.sqlite3"))
    monkeypatch.setattr(main, "run_in_background", lambda *args: None)
    with TestClient(app) as test_client:
        yield test_client


def test_first_failure_returns_a_request_to_the_queue(store):
    assert store.start_request("REQ-7001") == 1
    assert store.fail_request("REQ-7001") == "waiting"
    request = store.get_request("REQ-7001")
    assert request is not None
    assert request["status"] == "waiting"
    assert request["attempts"] == 1
    assert request["steps"][-1]["stage"] == "error"


def test_second_failure_leaves_a_request_for_support(store):
    store.start_request("REQ-7001")
    store.fail_request("REQ-7001")
    assert store.start_request("REQ-7001") == 2
    assert store.fail_request("REQ-7001") == "left_for_support"
    request = store.get_request("REQ-7001")
    assert request is not None
    assert request["status"] == "waiting_for_agent_review"
    assert request["recommendation"] is None
    stages = [step["stage"] for step in request["steps"]]
    assert stages == ["started", "error", "started", "left_for_support"]
    assert "Attempt 2 of 2" in request["steps"][2]["message"]
    assert store.start_request("REQ-7001") is None


def test_a_request_never_gets_a_second_recommendation(store):
    store.start_request("REQ-7001")
    assert store.save_recommendation("REQ-7001", RECOMMENDATION)
    assert not store.save_recommendation("REQ-7001", {**RECOMMENDATION, "x": 1})
    assert store.start_request("REQ-7001") is None
    assert store.record_review("REQ-7001", {"outcome": "approve", "notes": ""})
    assert not store.record_review("REQ-7001", {"outcome": "decline", "notes": ""})
    request = store.get_request("REQ-7001")
    assert request is not None
    assert request["recommendation"] == RECOMMENDATION
    assert request["review"]["outcome"] == "approve"


def test_restart_recovers_requests_and_runs_left_in_progress(store):
    run_id = store.create_run(5)
    store.start_request("REQ-7001")
    store.initialize()
    request = store.get_request("REQ-7001")
    run = store.current_run()
    assert request is not None
    assert request["status"] == "waiting"
    assert run is not None
    assert run["run_id"] == run_id
    assert run["status"] == "failed"


def test_reseed_rebuilds_every_request_as_waiting(store):
    store.start_request("REQ-7001")
    store.save_recommendation("REQ-7001", RECOMMENDATION)
    store.create_run(2)
    store.reseed()
    assert {item["status"] for item in store.list_requests()} == {"waiting"}
    assert len(store.list_requests()) == 8
    assert store.current_run() is None


def test_existing_database_gains_the_attempts_column(tmp_path):
    path = tmp_path / "old.sqlite3"
    store = Store(path)
    with store.connect() as connection:
        connection.execute(
            """CREATE TABLE support_requests (
                request_id TEXT PRIMARY KEY, order_id TEXT NOT NULL,
                customer_id TEXT NOT NULL, customer_name TEXT NOT NULL,
                request_type TEXT NOT NULL, created_at TEXT NOT NULL,
                source_status TEXT NOT NULL, queue_status TEXT NOT NULL,
                request_json TEXT NOT NULL, order_json TEXT NOT NULL,
                recommendation_json TEXT, review_json TEXT)"""
        )
    connection.close()
    store.initialize()
    assert store.list_requests()[0]["attempts"] == 0


def test_runs_are_one_at_a_time_and_keep_a_to_do_list(client):
    started = client.post("/api/runs", json={"cap": 5})
    second = client.post("/api/runs", json={"cap": 5})
    run_id = started.json()["run_id"]
    todos = [
        {"request_id": "REQ-7001", "title": "Cancellation", "status": "to_do"},
        {"request_id": "REQ-7002", "title": "Return", "status": "to_do"},
    ]
    written = client.put(f"/api/runs/{run_id}/todos", json={"todos": todos})
    ticked = client.post(f"/api/runs/{run_id}/todos/REQ-7002", json={"status": "done"})
    added = client.post(
        f"/api/runs/{run_id}/todos/REQ-7003", json={"status": "left_for_support"}
    )
    current = client.get("/api/runs/current").json()

    assert started.status_code == 200
    assert started.json()["status"] == "running"
    assert second.status_code == 409
    assert written.status_code == 200
    assert ticked.status_code == 200
    assert added.status_code == 200
    assert current["run_id"] == run_id
    assert current["cap"] == 5
    assert [(t["request_id"], t["status"]) for t in current["todos"]] == [
        ("REQ-7001", "to_do"),
        ("REQ-7002", "done"),
        ("REQ-7003", "left_for_support"),
    ]


def test_to_do_list_is_refused_once_a_run_has_finished(client):
    run_id = client.post("/api/runs", json={"cap": 1}).json()["run_id"]
    app.state.store.finish_run(run_id, "finished", "Done.")
    written = client.put(f"/api/runs/{run_id}/todos", json={"todos": []})
    ticked = client.post(f"/api/runs/{run_id}/todos/REQ-7001", json={"status": "done"})
    assert written.status_code == 409
    assert ticked.status_code == 409
    assert client.post("/api/runs", json={"cap": 1}).status_code == 200


def test_a_run_needs_a_cap_of_at_least_one(client):
    assert client.post("/api/runs", json={"cap": 0}).status_code == 422
    assert client.get("/api/runs/current").json() is None


def test_waiting_requests_hold_no_customer_or_order_fields(client):
    client.post("/api/requests/REQ-7001/start")
    waiting = client.get("/api/requests/waiting").json()
    assert len(waiting) == 7
    assert "REQ-7001" not in {item["request_id"] for item in waiting}
    assert set(waiting[0]) == {"request_id", "type", "created_at"}


def test_agent_operations_start_save_and_fail_requests(client):
    started = client.post("/api/requests/REQ-7001/start")
    again = client.post("/api/requests/REQ-7001/start")
    missing = client.post("/api/requests/REQ-0000/start")
    saved = client.post("/api/requests/REQ-7001/recommendation", json=RECOMMENDATION)
    duplicate = client.post(
        "/api/requests/REQ-7001/recommendation", json=RECOMMENDATION
    )
    client.post("/api/requests/REQ-7002/start")
    failed = client.post("/api/requests/REQ-7002/failure")
    not_running = client.post("/api/requests/REQ-7003/failure")

    assert started.json() == {
        "request_id": "REQ-7001",
        "status": "in_progress",
        "attempt": 1,
    }
    assert again.status_code == 409
    assert missing.status_code == 404
    assert saved.json()["status"] == "waiting_for_agent_review"
    assert duplicate.status_code == 409
    assert failed.json() == {"request_id": "REQ-7002", "status": "waiting"}
    assert not_running.status_code == 409


def test_agent_progress_steps_need_a_request_in_progress(client):
    invalid = client.post("/api/requests/REQ-7001/steps", json={"stage": "finished"})
    idle = client.post(
        "/api/requests/REQ-7001/steps", json={"stage": "checking_policy"}
    )
    client.post("/api/requests/REQ-7001/start")
    recorded = client.post(
        "/api/requests/REQ-7001/steps", json={"stage": "checking_policy"}
    )
    assert invalid.status_code == 422
    assert idle.status_code == 409
    assert recorded.status_code == 200


def test_support_review_decides_without_running_an_order_action(client):
    client.post("/api/requests/REQ-7001/start")
    early = client.post(
        "/api/requests/REQ-7002/review", json={"outcome": "approve", "notes": ""}
    )
    client.post("/api/requests/REQ-7001/recommendation", json=RECOMMENDATION)
    response = client.post(
        "/api/requests/REQ-7001/review",
        json={"outcome": "approve", "notes": "Confirmed by support."},
    )
    detail = client.get("/api/requests/REQ-7001").json()
    duplicate = client.post(
        "/api/requests/REQ-7001/review", json={"outcome": "approve", "notes": ""}
    )

    assert early.status_code == 409
    assert response.status_code == 200
    assert detail["status"] == "decided"
    assert detail["review"]["notes"] == "Confirmed by support."
    assert "action_result" not in detail
    assert duplicate.status_code == 409


def test_background_run_works_up_to_its_cap(store, monkeypatch):
    calls = []

    def fake_agent(request_id, thread_id):
        calls.append(request_id)
        if request_id == "REQ-7002":
            raise RuntimeError("provider error")
        return RECOMMENDATION

    monkeypatch.setattr(main, "run_agent", fake_agent)
    run_id = store.create_run(2)
    assert run_id is not None
    main.run_in_background(store, run_id, 2)

    statuses = {item["request_id"]: item["status"] for item in store.list_requests()}
    run = store.current_run()
    assert len(calls) == 2
    assert statuses[calls[0]] == "waiting_for_agent_review"
    assert statuses["REQ-7002"] == "waiting"
    assert list(statuses.values()).count("waiting") == 7
    assert run is not None
    assert run["status"] == "finished"
