import pytest
from fastapi.testclient import TestClient

from agent.cli import main
from agent.model import DEFAULT_MODEL, model
from agent.runner import run
from agent.tests.stub_model import StubModel


def claims(client: TestClient) -> list[dict]:
    return client.get("/api/claims").json()


def by_status(client: TestClient, status: str) -> list[str]:
    return [c["claim_id"] for c in claims(client) if c["status"] == status]


def test_default_model_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert model().model_name == DEFAULT_MODEL
    assert model().reasoning_effort == "low"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert model().model_name == "openrouter/free"


def test_run_respects_cap_and_stores_todos(backend_in_process: TestClient) -> None:
    summary = run(cap=2, llm=StubModel())
    client = backend_in_process
    assert "run complete" in summary
    assert len(by_status(client, "waiting")) == len(claims(client)) - 2
    todos = client.get("/api/runs/current").json()["todos"]
    assert [t["state"] for t in todos] == ["done", "done"]


def test_failed_claim_does_not_stop_run_and_is_retried(
    backend_in_process: TestClient,
) -> None:
    client = backend_in_process
    first = client.get("/api/claims").json()
    waiting = [c["claim_id"] for c in first if c["status"] == "waiting"][:3]
    run(cap=3, llm=StubModel(errors={waiting[0]: 1}))
    assert by_status(client, "in_progress") == []
    for claim_id in waiting:
        detail = client.get(f"/api/claims/{claim_id}").json()
        assert detail["decision"] is not None
    assert client.get(f"/api/claims/{waiting[0]}").json()["attempts"] == 2


def test_claim_failing_twice_is_left_for_handler(
    backend_in_process: TestClient,
) -> None:
    client = backend_in_process
    waiting = [c["claim_id"] for c in claims(client) if c["status"] == "waiting"][:2]
    run(cap=2, llm=StubModel(errors={waiting[0]: 2}))
    assert by_status(client, "left_for_handler") == [waiting[0]]
    assert client.get(f"/api/claims/{waiting[1]}").json()["decision"] is not None
    assert by_status(client, "in_progress") == []


def test_no_double_decision_or_payment(backend_in_process: TestClient) -> None:
    client = backend_in_process
    run(cap=1, llm=StubModel(repeat_decision=True))
    claim_id = next(c["claim_id"] for c in claims(client) if c["status"] != "waiting")
    detail = client.get(f"/api/claims/{claim_id}").json()
    assert detail["decision"] is not None
    assert detail["payment"] is not None


def test_missed_claims_check_makes_runner_finish(
    backend_in_process: TestClient,
) -> None:
    client = backend_in_process
    run(cap=3, llm=StubModel(stop_early=True))
    done = [c for c in claims(client) if c["status"] != "waiting"]
    assert len(done) == 3


def test_provider_error_in_runner_is_survived(backend_in_process: TestClient) -> None:
    client = backend_in_process
    run(cap=1, llm=StubModel(errors={"runner": 1}))
    assert by_status(client, "in_progress") == []
    assert len(by_status(client, "waiting")) == len(claims(client)) - 1


def test_lazy_subagent_is_requeued(backend_in_process: TestClient) -> None:
    client = backend_in_process
    waiting = [c["claim_id"] for c in claims(client) if c["status"] == "waiting"][:1]
    run(cap=1, llm=StubModel(lazy={waiting[0]: 1}))
    assert client.get(f"/api/claims/{waiting[0]}").json()["decision"] is not None


def test_named_claim_run_and_signoff(backend_in_process: TestClient) -> None:
    client = backend_in_process
    claim_id = by_status(client, "waiting")[0]
    run(claim_id=claim_id, llm=StubModel(payouts={claim_id: 5000.0}))
    detail = client.get(f"/api/claims/{claim_id}").json()
    assert detail["status"] == "awaiting_signoff"
    assert detail["payment"] is None
    assert len(by_status(client, "waiting")) == len(claims(client)) - 1


def test_steps_and_reads_recorded(backend_in_process: TestClient) -> None:
    client = backend_in_process
    claim_id = by_status(client, "waiting")[0]
    run(claim_id=claim_id, llm=StubModel())
    detail = client.get(f"/api/claims/{claim_id}").json()
    assert len(detail["steps"]) >= 4
    assert detail["reads"]


def test_cli(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    monkeypatch.setattr("agent.runner.model", StubModel)
    assert "run complete" in main(["--limit", "1"])
    assert "run complete" in capsys.readouterr().out
