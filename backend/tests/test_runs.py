import pytest

from agent import queue as runner

TODOS = [
    {"claim_id": "CLM-1001", "content": "Flight canceled", "status": "done"},
    {"claim_id": "CLM-1002", "content": "Lost bag", "status": "in_progress"},
]


@pytest.fixture
def started(client, monkeypatch):
    runs = []
    monkeypatch.delenv("UNDERCOVER_AGENT")
    monkeypatch.setattr(runner, "run_queue", runs.append)
    return runs


def test_no_run_yet(client):
    assert client.get("/api/runs/latest").json() is None


def test_start_run(client, started):
    run = client.post("/api/runs", json={"cap": 5}).json()
    assert run["status"] == "running"
    assert run["cap"] == 5
    assert run["claim_id"] is None
    assert run["todos"] == []
    assert run["started_at"]
    assert started == [run["id"]]
    assert client.get("/api/runs/latest").json() == run
    assert client.get(f"/api/runs/{run['id']}").json() == run


def test_one_run_at_a_time(client, started):
    client.post("/api/runs", json={"cap": 5})
    response = client.post("/api/runs", json={"cap": 5})
    assert response.status_code == 409
    assert response.json()["detail"] == "A run is already going; wait for it to finish"
    assert client.post("/api/claims/CLM-1001/run").status_code == 409
    assert len(started) == 1


@pytest.mark.parametrize("cap", [0, -1])
def test_cap_below_one(client, started, cap):
    assert client.post("/api/runs", json={"cap": cap}).status_code == 422
    assert started == []


def test_unknown_run(client):
    response = client.get("/api/runs/99")
    assert response.status_code == 404
    assert response.json()["detail"] == "Run 99 was not found"


def test_write_todos(client, started):
    run_id = client.post("/api/runs", json={"cap": 2}).json()["id"]
    run = client.post(f"/api/runs/{run_id}/todos", json={"todos": TODOS}).json()
    assert run["todos"] == TODOS
    assert client.get("/api/runs/latest").json()["todos"] == TODOS


def test_todo_with_an_unknown_status(client, started):
    run_id = client.post("/api/runs", json={"cap": 2}).json()["id"]
    bad = [TODOS[0] | {"status": "maybe"}]
    response = client.post(f"/api/runs/{run_id}/todos", json={"todos": bad})
    assert response.status_code == 422


def test_finish_run(client, started):
    run_id = client.post("/api/runs", json={"cap": 2}).json()["id"]
    run = client.post(
        f"/api/runs/{run_id}/finish", json={"summary": "Two claims decided."}
    ).json()
    assert run["status"] == "finished"
    assert run["summary"] == "Two claims decided."
    assert run["finished_at"]
    response = client.post(f"/api/runs/{run_id}/todos", json={"todos": TODOS})
    assert response.status_code == 409
    assert response.json()["detail"] == f"Run {run_id} is finished, not running"
    assert client.post("/api/runs", json={"cap": 1}).status_code == 200


def test_fail_run(client, started):
    run_id = client.post("/api/runs", json={"cap": 2}).json()["id"]
    run = client.post(
        f"/api/runs/{run_id}/fail", json={"problem": "The model provider is down"}
    ).json()
    assert run["status"] == "failed"
    assert run["problem"] == "The model provider is down"
    assert run["finished_at"]
    response = client.post(f"/api/runs/{run_id}/finish", json={"summary": "Done."})
    assert response.status_code == 409


def test_run_agent_starts_a_one_claim_run(client, started):
    run = client.post("/api/claims/CLM-1001/run").json()
    assert run["claim_id"] == "CLM-1001"
    assert run["cap"] == 1
    assert started == [run["id"]]


def test_run_agent_needs_a_waiting_claim(client, started):
    client.post("/api/claims/CLM-1001/start")
    assert client.post("/api/claims/CLM-1001/run").status_code == 409
    assert started == []


def test_agent_can_be_turned_off(client, started, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_AGENT", "off")
    assert client.post("/api/runs", json={"cap": 1}).status_code == 200
    assert started == []
