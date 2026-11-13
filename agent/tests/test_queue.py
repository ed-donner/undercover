from threading import Event
from time import monotonic, sleep

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from agent import api, delegation, main, queue
from agent.tests.test_agent import StubModel, call, scripted_model
from backend.execution import execute_queue
from backend.harness import Harness
from backend.harness_models import Task
from backend.main import create_app
from backend.store import Store
from backend.tests.helpers import agent_backend
from backend.workflow import Workflow


def plan_message(ids, states=None):
    return call(
        "write_todos",
        {
            "tasks": [
                {"claim_id": key, "state": (states or {}).get(key, "todo")}
                for key in ids
            ]
        },
    )


def supervisor(ids, delegates=None):
    replies = [call("read_queue", {}), plan_message(ids)]
    for key in delegates or ids:
        replies.extend(
            [call("delegate_claim", {"claim_id": key}), call("read_queue", {})]
        )
    replies.extend([call("check_completion", {}), call("finish_run", {})])
    return StubModel(messages=iter(replies))


@pytest.fixture
def setup(tmp_path, monkeypatch):
    failures, seen = {}, []

    def child(claim_id, thread_id):
        seen.append((claim_id, thread_id))
        if failures.get(claim_id, 0):
            failures[claim_id] -= 1
            raise RuntimeError("Synthetic secret model failure")
        return main.run(claim_id, thread_id, scripted_model("refer", "0"))

    with TestClient(
        create_app(tmp_path / "queue.db", runner=child, queue_runner=None)
    ) as client:
        monkeypatch.setattr(api, "connect", lambda: agent_backend(client))
        monkeypatch.setattr(delegation, "POLL_SECONDS", 0.001)
        yield client, failures, seen


def create(client, cap=5):
    return client.post(
        "/api/agent-runs", json={"mode": "queue", "max_claims": cap}
    ).json()


def test_agent_chooses_order_and_only_short_child_summaries(setup):
    client, _, seen = setup
    run = create(client, 3)
    ids = ["CLM-1003", "CLM-1001", "CLM-1002"]
    result = queue.run_queue(run["run_id"], run["thread_id"], supervisor(ids))
    assert "3 claims worked" in result
    assert [key for key, _ in seen] == ids
    assert len({thread for _, thread in seen}) == 3
    final = client.get(f"/api/agent-runs/{run['run_id']}").json()
    assert [task["claim_id"] for task in final["tasks"]] == ids
    assert all(task["state"] == "needs_handler" for task in final["tasks"])
    assert "story" not in result
    assert "Synthetic secret" not in str(final)


@pytest.mark.parametrize("cap", [1, 5, None, 50])
def test_cap_and_smaller_queue_leave_other_claims_untouched(setup, cap):
    client, _, seen = setup
    store = client.app.state.store
    ids = [f"CLM-{1001 + index}" for index in range(5)]
    with store.transaction() as connection:
        connection.execute("UPDATE claims SET needs_handler = 1 WHERE id > 'CLM-1005'")
    run = create(client, cap)
    expected = 1 if cap == 1 else 5
    queue.run_queue(
        run["run_id"], run["thread_id"], supervisor(list(reversed(ids))[:expected])
    )
    assert len(seen) == expected
    assert len({key for key, _ in seen}) == expected
    with store.connect() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
            == expected
        )
    assert client.get("/api/claims/CLM-1006/runs").json() == []
    assert client.get("/api/claims/CLM-1006").json()["status"] == "waiting"


def test_first_failure_retries_after_another_claim_at_full_cap(setup):
    client, failures, seen = setup
    failures["CLM-1001"] = 1
    run = create(client, 2)
    ids = ["CLM-1001", "CLM-1002"]
    llm = supervisor(ids, ["CLM-1001", "CLM-1002", "CLM-1001"])
    queue.run_queue(run["run_id"], run["thread_id"], llm)
    assert [key for key, _ in seen] == ["CLM-1001", "CLM-1002", "CLM-1001"]
    attempts = client.get("/api/claims/CLM-1001/runs").json()
    assert [attempt["status"] for attempt in attempts] == ["failed", "completed"]
    assert attempts[0]["thread_id"] != attempts[1]["thread_id"]
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["failures"] == 1
    assert not claim["needs_handler"]


def test_twice_failed_claim_is_left_for_handler_and_not_restarted(setup):
    client, failures, seen = setup
    failures["CLM-1001"] = 2
    run = create(client, 2)
    queue.run_queue(
        run["run_id"],
        run["thread_id"],
        supervisor(["CLM-1001", "CLM-1002"], ["CLM-1001", "CLM-1001", "CLM-1002"]),
    )
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "waiting"
    assert claim["needs_handler"]
    assert claim["decision"] is None
    assert claim["payment"] is None
    assert (
        client.post(
            "/api/agent-runs", json={"mode": "claim", "claim_id": "CLM-1001"}
        ).status_code
        == 409
    )
    assert len(seen) == 3


def test_missed_claim_check_returns_work_to_the_agent(setup):
    client, _, seen = setup
    run = create(client, 2)
    replies = [
        call("read_queue", {}),
        plan_message(["CLM-1001"]),
        call("delegate_claim", {"claim_id": "CLM-1001"}),
        call("check_completion", {}),
        call("read_queue", {}),
        plan_message(["CLM-1001", "CLM-1002"], {"CLM-1001": "needs_handler"}),
        call("delegate_claim", {"claim_id": "CLM-1002"}),
        call("check_completion", {}),
        call("finish_run", {}),
    ]
    queue.run_queue(run["run_id"], run["thread_id"], StubModel(messages=iter(replies)))
    assert [key for key, _ in seen] == ["CLM-1001", "CLM-1002"]
    assert client.get(f"/api/agent-runs/{run['run_id']}").json()["checked"]


def test_premature_supervisor_retries_once_then_fails(setup):
    client, _, _ = setup
    data = create(client)
    run = Harness(client.app.state.store).get(data["run_id"])
    calls = []

    def premature(run_id, thread_id):
        calls.append(thread_id)
        return queue.run_queue(
            run_id,
            thread_id,
            StubModel(messages=iter([AIMessage(content="Done, trust me")])),
        )

    execute_queue(client.app.state.store, run, premature)
    assert len(calls) == 2
    assert calls[0] != calls[1]
    final = Harness(client.app.state.store).get(run.run_id)
    assert final.status == "failed"
    assert final.error == "Agent could not finish."
    assert all(
        claim["status"] == "waiting" for claim in client.get("/api/claims").json()
    )


def test_supervisor_recovery_does_not_replay_completed_work(setup):
    client, _, seen = setup
    data = create(client, 2)
    harness = Harness(client.app.state.store)
    run = harness.get(data["run_id"])
    invocations = []

    def recovery(run_id, thread_id):
        invocations.append(thread_id)
        if len(invocations) == 1:
            replies = [
                plan_message(["CLM-1001", "CLM-1002"]),
                call("delegate_claim", {"claim_id": "CLM-1001"}),
            ]
            queue.run_queue(run_id, thread_id, StubModel(messages=iter(replies)))
        replies = [
            call("read_queue", {}),
            plan_message(["CLM-1001", "CLM-1002"], {"CLM-1001": "needs_handler"}),
            call("delegate_claim", {"claim_id": "CLM-1002"}),
            call("check_completion", {}),
            call("finish_run", {}),
        ]
        return queue.run_queue(run_id, thread_id, StubModel(messages=iter(replies)))

    execute_queue(client.app.state.store, run, recovery)
    assert len(invocations) == 2
    assert [key for key, _ in seen] == ["CLM-1001", "CLM-1002"]
    assert harness.get(run.run_id).status == "completed"


def test_delegation_timeout_fences_child_before_return(tmp_path, monkeypatch):
    release = Event()

    def child(claim_id, thread_id):
        release.wait(3)
        return "No decision"

    with TestClient(
        create_app(tmp_path / "timeout.db", runner=child, queue_runner=None)
    ) as client:
        run = create(client, 1)
        client.put(
            f"/api/agent-runs/{run['run_id']}/tasks",
            json={"tasks": [{"claim_id": "CLM-1001", "state": "todo"}]},
        )
        monkeypatch.setattr(delegation, "DELEGATION_SECONDS", -1)
        try:
            with agent_backend(client) as backend:
                line = delegation.delegate(backend, run["run_id"], "CLM-1001")
            assert "retry available" in line
            assert client.get("/api/claims/CLM-1001").json()["status"] == "waiting"
            assert (
                client.get("/api/claims/CLM-1001/runs").json()[0]["status"] == "failed"
            )
        finally:
            release.set()


def test_top_level_start_is_responsive_and_background(tmp_path):
    entered, release = Event(), Event()
    store = Store(tmp_path / "background.db")

    def runner(run_id, thread_id):
        entered.set()
        assert release.wait(3)
        harness = Harness(store)
        harness.check(run_id)
        return harness.finish(run_id, None).summary

    with TestClient(create_app(store.path, runner=None, queue_runner=runner)) as client:
        with store.transaction() as connection:
            connection.execute("UPDATE claims SET needs_handler = 1")
        try:
            response = client.post(
                "/api/agent-runs", json={"mode": "queue", "max_claims": 5}
            )
            assert response.status_code == 202
            assert entered.wait(3)
            assert client.get("/api/health").status_code == 200
            assert (
                client.get(f"/api/agent-runs/{response.json()['run_id']}").json()[
                    "status"
                ]
                == "running"
            )
        finally:
            release.set()
        deadline = monotonic() + 3
        while monotonic() < deadline:
            if client.get("/api/agent-runs").json()[0]["status"] == "completed":
                break
            sleep(0.01)
        assert client.get("/api/agent-runs").json()[0]["status"] == "completed"


def test_duplicate_delegation_returns_backend_result_not_another_attempt(setup):
    client, _, seen = setup
    run = create(client, 1)
    queue.run_queue(
        run["run_id"],
        run["thread_id"],
        supervisor(["CLM-1001"], ["CLM-1001", "CLM-1001"]),
    )
    assert len(seen) == 1
    assert (
        client.post(
            "/api/runs/no/finish", json={"error": "Agent could not finish."}
        ).status_code
        == 404
    )
    with pytest.raises(RuntimeError, match="no longer active"):
        queue.run_queue(run["run_id"], run["thread_id"], supervisor([]))


def test_queue_can_correct_rejected_plan(setup):
    client, _, seen = setup
    run = create(client, 1)
    replies = [
        plan_message(["CLM-1001"], {"CLM-1001": "done"}),
        *list(supervisor(["CLM-1001"]).messages),
    ]
    queue.run_queue(run["run_id"], run["thread_id"], StubModel(messages=iter(replies)))
    assert len(seen) == 1


def test_failed_supervisor_fences_orphaned_attempt(setup):
    client, _, _ = setup
    data = create(client, 1)
    harness = Harness(client.app.state.store)
    run = harness.get(data["run_id"])
    harness.plan(run.run_id, [Task(claim_id="CLM-1001", state="todo")])
    workflow = Workflow(client.app.state.store)
    calls = []

    def interrupted(run_id, thread_id):
        calls.append(thread_id)
        workflow.start("CLM-1001", run_id)
        raise RuntimeError("Interrupted supervisor with active child")

    execute_queue(client.app.state.store, run, interrupted)
    assert len(calls) == 2
    assert all(child.status == "failed" for child in workflow.runs("CLM-1001"))
    assert workflow.detail("CLM-1001").needs_handler
    assert harness.get(run.run_id).status == "failed"
