from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event
from time import monotonic, sleep

import pytest
from fastapi.testclient import TestClient

from backend.execution import execute
from backend.harness import Harness
from backend.harness_models import QueueStart, Task
from backend.main import create_app
from backend.models import DecisionInput, PaymentInput, SignOffInput
from backend.store import Store
from backend.tests.helpers import read_sources, start, start_workflow
from backend.workflow import Workflow


def wait_for_finish(client, claim_id):
    deadline = monotonic() + 3
    while monotonic() < deadline:
        run = client.get(f"/api/claims/{claim_id}/runs").json()[-1]
        if run["status"] != "running":
            return run
        sleep(0.01)
    pytest.fail("Run did not finish")


def record(workflow, claim_id, payout="420"):
    active = workflow.runs(claim_id)[-1]
    read_sources(workflow.store, active.run_id, claim_id)
    return workflow.decide(
        claim_id,
        DecisionInput(
            run_id=active.run_id,
            outcome="approve",
            payout=Decimal(payout),
            calculation="Eligible costs total the payout.",
            explanation="Costs are covered. Receipts support the amount.",
            policy_sections=[3, 10],
            manual_version="2026.2",
            manual_sections=[4, 9],
        ),
    )


def test_background_run_is_responsive_and_observable(tmp_path):
    entered, release = Event(), Event()
    db = Store(tmp_path / "background.db")
    workflow = Workflow(db)

    def runner(claim_id, thread_id):
        active = workflow.runs(claim_id)[-1]
        assert active.thread_id == thread_id
        workflow.event(active.run_id, "context_read")
        entered.set()
        assert release.wait(3)
        record(workflow, claim_id)
        workflow.pay(claim_id, PaymentInput(amount=Decimal("420")))
        return "Done"

    with TestClient(create_app(db.path, runner=runner, queue_runner=None)) as client:
        try:
            response = start(client)
            assert response.status_code == 202
            assert entered.wait(3)
            assert client.get("/api/health").status_code == 200
            assert client.get("/api/claims/CLM-1001").json()["status"] == "in_progress"
            events = client.get("/api/claims/CLM-1001/events").json()
            assert [item["kind"] for item in events] == ["run_started", "context_read"]
            assert start(client).status_code == 409
        finally:
            release.set()
        assert wait_for_finish(client, "CLM-1001")["status"] == "completed"
        events = client.get("/api/claims/CLM-1001/events").json()
        assert [item["kind"] for item in events][-3:] == [
            "decision_recorded",
            "payment_recorded",
            "run_completed",
        ]
        assert [item["sequence"] for item in events] == sorted(
            {item["sequence"] for item in events}
        )


def test_concurrent_starts_and_distinct_threads(tmp_path):
    entered, release = Event(), Event()
    calls = []

    def runner(claim_id, thread_id):
        calls.append((claim_id, thread_id))
        entered.set()
        assert release.wait(3)
        return "No decision"

    with TestClient(
        create_app(tmp_path / "concurrent.db", runner=runner, queue_runner=None)
    ) as client:
        harness = Harness(Store(tmp_path / "concurrent.db"))
        parent_id = harness.create(QueueStart(mode="queue", max_claims=None)).run_id
        harness.plan(parent_id, [Task(claim_id="CLM-1001", state="todo")])
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(
                    pool.map(
                        lambda _: client.post(
                            "/api/claims/CLM-1001/runs",
                            json={"parent_run_id": parent_id},
                        ),
                        range(2),
                    )
                )
            assert sorted(response.status_code for response in responses) == [202, 409]
            assert entered.wait(3)
            assert len(calls) == 1
            assert start(client, "CLM-1002").status_code == 409
            release.set()
            wait_for_finish(client, "CLM-1001")
            other = start(client, "CLM-1002").json()
            first = client.get("/api/claims/CLM-1001/runs").json()[0]
            assert other["thread_id"] != first["thread_id"]
        finally:
            release.set()
        assert wait_for_finish(client, "CLM-1001")["status"] == "failed"
        assert wait_for_finish(client, "CLM-1002")["status"] == "failed"


@pytest.mark.parametrize("after_decision", [False, True])
def test_failed_run_preserves_committed_state(tmp_path, after_decision):
    db = Store(tmp_path / "failed.db")
    workflow = Workflow(db)

    def runner(claim_id, thread_id):
        if after_decision:
            record(workflow, claim_id, "1200")
        raise RuntimeError("secret-key and hidden model reasoning must not escape")

    with TestClient(create_app(db.path, runner=runner, queue_runner=None)) as client:
        start(client)
        run = wait_for_finish(client, "CLM-1001")
        assert run["status"] == "failed"
        assert "secret-key" not in str(run)
        events = client.get("/api/claims/CLM-1001/events").json()
        assert events[-1]["kind"] == "run_failed"
        assert "hidden model reasoning" not in str(events)
        claim = client.get("/api/claims/CLM-1001").json()
        if after_decision:
            assert claim["status"] == "waiting_for_sign_off"
            assert claim["decision"]["payout"] == 1200
            assert start(client).status_code == 409
            assert (
                client.post(
                    "/api/claims/CLM-1001/payment", json={"amount": 1200}
                ).status_code
                == 409
            )
        else:
            assert claim["status"] == "waiting"
            start(client)
            wait_for_finish(client, "CLM-1001")
            assert len(client.get("/api/claims/CLM-1001/runs").json()) == 2


def test_restart_recovers_runs_and_preserves_records(tmp_path):
    db = Store(tmp_path / "restart.db")
    db.initialize()
    workflow = Workflow(db)
    start_workflow(workflow, "CLM-1002")
    record(workflow, "CLM-1002", "1500")
    workflow.sign_off("CLM-1002", SignOffInput(handler_id="HND-01"))
    workflow.pay("CLM-1002", PaymentInput(amount=Decimal("1500")))
    workflow.finish(workflow.runs("CLM-1002")[-1].run_id, None)
    interrupted = start_workflow(workflow, "CLM-1001")
    before = workflow.detail("CLM-1002")
    with TestClient(create_app(db.path, runner=None, queue_runner=None)) as client:
        assert client.get("/api/claims/CLM-1001").json()["status"] == "waiting"
        assert (
            "interrupted" in client.get("/api/claims/CLM-1001/runs").json()[0]["error"]
        )
        assert client.get("/api/claims/CLM-1002").json() == before.model_dump(
            mode="json"
        )
        assert (
            client.get("/api/claims/CLM-1002/events").json()[-1]["kind"]
            == "run_completed"
        )
        assert start(client).status_code == 202
    workflow.finish(interrupted.run_id, None)
    assert workflow.runs("CLM-1001")[0].status == "failed"


def test_activity_contract(client):
    run = start(client).json()
    path = f"/api/runs/{run['run_id']}/events"
    assert client.post(path, json={"activity": "context_started"}).status_code == 200
    assert (
        client.post(path, json={"activity": "reasoning", "text": "secret"}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/runs/no/events", json={"activity": "context_read"}
        ).status_code
        == 404
    )
    workflow = Workflow(client.app.state.store)
    workflow.finish(run["run_id"], "Interrupted")
    assert client.post(path, json={"activity": "context_read"}).status_code == 409


def test_completed_execution_does_not_lose_decision(client):
    workflow = Workflow(client.app.state.store)
    run = start_workflow(workflow, "CLM-1001")

    def runner(claim_id, thread_id):
        record(workflow, claim_id)
        return "Done"

    execute(client.app.state.store, run, runner)
    assert workflow.runs("CLM-1001")[0].status == "completed"
