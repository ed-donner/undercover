import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.harness import Harness
from backend.harness_models import QueueStart, Task
from backend.store import Store
from backend.tests.helpers import start
from backend.tests.test_workflow import decide
from backend.workflow import Workflow


def create(client, cap=5):
    return client.post("/api/agent-runs", json={"mode": "queue", "max_claims": cap})


def plan(client, run_id, ids):
    return client.put(
        f"/api/agent-runs/{run_id}/tasks",
        json={"tasks": [{"claim_id": key, "state": "todo"} for key in ids]},
    )


def test_creation_contract(client):
    for body in (
        {},
        {"mode": "queue"},
        {"mode": "queue", "max_claims": 0},
        {"mode": "queue", "max_claims": -1},
        {"mode": "queue", "max_claims": 1.5},
        {"mode": "queue", "max_claims": True},
        {"mode": "claim", "claim_id": "CLM-1001", "max_claims": 1},
    ):
        assert client.post("/api/agent-runs", json=body).status_code == 422
    assert (
        client.post(
            "/api/agent-runs", json={"mode": "claim", "claim_id": "no"}
        ).status_code
        == 404
    )
    response = create(client)
    assert response.status_code == 202
    run = response.json()
    assert run["thread_id"]
    assert run["max_claims"] == 5
    assert len(run["scope"]) == 25
    assert run["tasks"] == []
    assert client.post("/api/claims/CLM-1001/runs").status_code == 422
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/agent-runs/no").status_code == 404


def test_concurrent_parent_starts(client):
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: create(client), range(2)))
    assert sorted(r.status_code for r in responses) == [202, 409]
    assert len(client.get("/api/agent-runs").json()) == 1


def test_planning_and_scope_guards(client):
    run = create(client, 1).json()
    key = run["run_id"]
    assert plan(client, key, ["CLM-1001", "CLM-1002"]).status_code == 409
    assert plan(client, key, ["CLM-1001", "CLM-1001"]).status_code == 409
    assert plan(client, key, ["no"]).status_code == 409
    assert plan(client, key, ["CLM-1001"]).status_code == 200
    premature = client.put(
        f"/api/agent-runs/{key}/tasks",
        json={"tasks": [{"claim_id": "CLM-1001", "state": "done"}]},
    )
    assert premature.status_code == 409
    first = client.post("/api/claims/CLM-1001/runs", json={"parent_run_id": key})
    assert first.status_code == 202
    assert (
        client.post(
            "/api/claims/CLM-1002/runs", json={"parent_run_id": key}
        ).status_code
        == 409
    )
    assert plan(client, key, []).status_code == 409
    assert (
        client.get(f"/api/agent-runs/{key}").json()["tasks"][0]["state"]
        == "in_progress"
    )


def test_five_distinct_claim_cap_and_retry_slots(client):
    key = create(client, 5).json()["run_id"]
    ids = [f"CLM-{1001 + index}" for index in range(5)]
    assert plan(client, key, ids).status_code == 200
    workflow = Workflow(client.app.state.store)
    for claim_id in ids:
        for _ in range(2):
            response = client.post(
                f"/api/claims/{claim_id}/runs", json={"parent_run_id": key}
            )
            assert response.status_code == 202
            workflow.finish(response.json()["run_id"], "Synthetic failure")
    assert (
        client.post(
            "/api/claims/CLM-1006/runs", json={"parent_run_id": key}
        ).status_code
        == 409
    )
    assert plan(client, key, [*ids, "CLM-1006"]).status_code == 409
    assert client.get("/api/claims/CLM-1006/runs").json() == []
    assert client.get("/api/claims/CLM-1006").json()["status"] == "waiting"
    assert client.post(f"/api/agent-runs/{key}/check").json()["ready"]


def test_two_failures_persist_handler_hold(client):
    run = create(client, 1).json()
    plan(client, run["run_id"], ["CLM-1001"])
    workflow = Workflow(client.app.state.store)
    for count in (1, 2):
        attempt = start(client).json()
        workflow.finish(attempt["run_id"], "Synthetic failure")
        claim = client.get("/api/claims/CLM-1001").json()
        assert claim["failures"] == count
        assert claim["needs_handler"] == (count == 2)
        assert claim["status"] == "waiting"
        assert claim["decision"] is None
    assert start(client).status_code == 409
    harness = Harness(client.app.state.store)
    assert harness.check(run["run_id"]).ready
    completed = harness.finish(run["run_id"], None)
    assert completed.tasks[0].state == "needs_handler"
    assert "1 left for a handler" in completed.summary
    assert (
        client.post(
            "/api/agent-runs", json={"mode": "claim", "claim_id": "CLM-1001"}
        ).status_code
        == 409
    )


def test_cap_reconciliation_and_persistence(client):
    run = create(client, 1).json()
    harness = Harness(client.app.state.store)
    key = run["run_id"]
    assert not harness.check(key).ready
    assert (
        client.post(f"/api/agent-runs/{key}/finish", json={"error": None}).status_code
        == 409
    )
    decide(client, outcome="decline", payout=0)
    attempt = client.get("/api/claims/CLM-1001/runs").json()[0]
    Workflow(client.app.state.store).finish(attempt["run_id"], None)
    check = harness.check(key)
    assert check.ready
    assert check.missing == []
    final = harness.finish(key, None)
    assert final.status == "completed"
    assert final.checked
    assert final.tasks[0].state == "done"
    assert final.tasks[0].admitted
    reopened = Harness(Store(client.app.state.store.path)).get(key)
    assert reopened == final
    assert (
        client.put(f"/api/agent-runs/{key}/tasks", json={"tasks": []}).status_code
        == 409
    )
    assert client.post(f"/api/agent-runs/{key}/check").status_code == 409
    assert (
        client.post(f"/api/agent-runs/{key}/finish", json={"error": None}).status_code
        == 409
    )


def test_named_scope_and_terminal_tasks(client):
    response = client.post(
        "/api/agent-runs", json={"mode": "claim", "claim_id": "CLM-1001"}
    )
    key = response.json()["run_id"]
    assert plan(client, key, ["CLM-1002"]).status_code == 409
    decide(client, outcome="refer", payout=0)
    workflow = Workflow(client.app.state.store)
    workflow.finish(workflow.runs("CLM-1001")[0].run_id, None)
    harness = Harness(client.app.state.store)
    assert harness.check(key).ready
    assert harness.finish(key, None).tasks[0].reason == "Referred for business review"


def test_migrate_legacy_schema(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE claims (id TEXT PRIMARY KEY, status TEXT NOT NULL);
            CREATE TABLE runs (run_id TEXT PRIMARY KEY, claim_id TEXT NOT NULL,
                thread_id TEXT NOT NULL UNIQUE, status TEXT NOT NULL,
                started_at TEXT NOT NULL, finished_at TEXT, error TEXT);
        """)
    store = Store(path)
    store.initialize()
    assert len(store.queue()) == 25
    run = Harness(store).create(QueueStart(mode="queue", max_claims=None))
    Harness(store).plan(
        run.run_id,
        [
            Task(claim_id="CLM-1002", state="todo"),
            Task(claim_id="CLM-1001", state="todo"),
        ],
    )
    store.initialize()
    store.initialize()
    assert [task.claim_id for task in Harness(store).get(run.run_id).tasks] == [
        "CLM-1002",
        "CLM-1001",
    ]


def test_active_child_prevents_finalization_and_completion(client):
    attempt = start(client).json()
    key = attempt["parent_run_id"]
    assert (
        client.post(
            f"/api/agent-runs/{key}/finish", json={"error": "Agent could not finish."}
        ).status_code
        == 409
    )
    assert "CLM-1001" in client.post(f"/api/agent-runs/{key}/check").json()["missing"]
    workflow = Workflow(client.app.state.store)
    workflow.finish(attempt["run_id"], "Failure")
    assert (
        client.post(
            f"/api/agent-runs/{key}/finish", json={"error": "Agent could not finish."}
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    ("outcome", "payout", "reason"),
    [("approve", 1200, "sign-off"), ("approve", 420, "unresolved")],
)
def test_unpaid_task_is_left_for_handler(client, outcome, payout, reason):
    decide(client, outcome=outcome, payout=payout)
    workflow = Workflow(client.app.state.store)
    attempt = workflow.runs("CLM-1001")[0]
    workflow.finish(attempt.run_id, None)
    assert attempt.parent_run_id is not None
    task = Harness(client.app.state.store).get(attempt.parent_run_id).tasks[0]
    assert task.state == "needs_handler"
    assert reason in task.reason
