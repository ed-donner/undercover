import threading

import pytest

from backend import db, decisions, runner
from backend.models import DecisionIn
from backend.seed import init_db


def approve_small(claim_id: str, thread_id: str) -> str:
    """A stand-in for the agent that records a small approval."""
    body = DecisionIn(
        decision="approve", payout=100.0, explanation="ok", policy_section="3"
    )
    with db.session() as conn:
        decisions.record_decision(conn, claim_id, body)
    return "done"


@pytest.fixture(autouse=True)
def fresh_runner(monkeypatch):
    monkeypatch.setattr(runner, "RUNNER", runner.Runner())
    monkeypatch.setattr(runner, "run_agent", approve_small)


def finish():
    thread = runner.RUNNER.thread
    assert thread
    thread.join(timeout=10)


def state(client, claim_id="CLM-1001"):
    return client.get(f"/api/claims/{claim_id}").json()["state"]


def test_a_claim_is_in_progress_while_it_runs(client, monkeypatch):
    started, proceed = threading.Event(), threading.Event()

    def slow(claim_id, thread_id):
        started.set()
        proceed.wait(timeout=10)
        return approve_small(claim_id, thread_id)

    monkeypatch.setattr(runner, "run_agent", slow)
    response = client.post("/api/claims/CLM-1001/run")
    assert response.status_code == 202
    assert response.json() == {"active": True, "claim_id": "CLM-1001"}
    started.wait(timeout=10)
    assert state(client) == "in progress"
    assert client.get("/api/runs/current").json()["active"] is True
    proceed.set()
    finish()
    assert state(client) == "decided"
    assert client.get("/api/runs/current").json() == {"active": False, "claim_id": None}


def test_a_second_run_is_refused_while_one_is_active(client, monkeypatch):
    proceed = threading.Event()
    monkeypatch.setattr(runner, "run_agent", lambda *_: proceed.wait(timeout=10) and "")
    assert client.post("/api/claims/CLM-1001/run").status_code == 202
    assert client.post("/api/claims/CLM-1002/run").status_code == 409
    assert client.post("/api/runs").status_code == 409
    proceed.set()
    finish()


def test_a_decided_or_unknown_claim_cannot_be_run(client):
    assert client.post("/api/claims/CLM-1001/run").status_code == 202
    finish()
    assert client.post("/api/claims/CLM-1001/run").status_code == 409
    assert client.post("/api/claims/CLM-0000/run").status_code == 404


def test_the_queue_runs_one_claim_after_another(client, monkeypatch):
    running, overlap, order = [], [], []

    def watched(claim_id, thread_id):
        running.append(claim_id)
        overlap.append(len(running))
        order.append(claim_id)
        result = approve_small(claim_id, thread_id)
        running.remove(claim_id)
        return result

    monkeypatch.setattr(runner, "run_agent", watched)
    client.post("/api/claims/CLM-1003/run")
    finish()
    assert client.post("/api/runs").json()["active"] is True
    finish()
    assert order[0] == "CLM-1003"
    assert order[1:] == [f"CLM-{n}" for n in range(1001, 1026) if n != 1003]
    assert set(overlap) == {1}
    assert {c["state"] for c in client.get("/api/claims").json()} == {"decided"}
    assert client.post("/api/runs").status_code == 409


def test_a_failed_run_leaves_the_claim_waiting(client, monkeypatch):
    def broken(claim_id, thread_id):
        raise RuntimeError("no key")

    monkeypatch.setattr(runner, "run_agent", broken)
    client.post("/api/claims/CLM-1001/run")
    finish()
    assert state(client) == "waiting"
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert steps[-1] == {
        **steps[-1],
        "kind": "error",
        "text": "The agent stopped: RuntimeError: no key",
    }
    assert client.get("/api/runs/current").json()["active"] is False
    monkeypatch.setattr(runner, "run_agent", approve_small)
    assert client.post("/api/claims/CLM-1001/run").status_code == 202
    finish()
    assert state(client) == "decided"


def test_a_run_without_a_decision_is_recorded(client, monkeypatch):
    monkeypatch.setattr(runner, "run_agent", lambda *_: "I give up")
    client.post("/api/claims/CLM-1001/run")
    finish()
    assert state(client) == "waiting"
    last = client.get("/api/claims/CLM-1001/steps").json()[-1]
    assert last["text"] == "The agent finished without recording a decision."


def test_a_run_cut_off_by_a_restart_is_not_left_in_progress(client):
    runner.begin("CLM-1001")
    assert state(client) == "in progress"
    init_db()
    assert state(client) == "waiting"


def test_the_default_runner_calls_the_agent(monkeypatch):
    calls = []
    monkeypatch.undo()
    monkeypatch.setattr("agent.main.run", lambda *args: calls.append(args) or "reply")
    assert runner.run_agent("CLM-1001", "thread-9") == "reply"
    assert calls == [("CLM-1001", "thread-9")]
