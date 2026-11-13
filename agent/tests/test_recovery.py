import json
from itertools import repeat
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langgraph.errors import GraphRecursionError

from agent import main
from agent.middleware import PublicActivity, transient
from agent.tests.test_agent import StubModel, call, scripted_model
from backend.harness import Harness
from backend.main import create_app
from backend.tests.helpers import http_backend, start
from backend.workflow import Workflow


@pytest.fixture
def client(tmp_path, monkeypatch):
    with TestClient(
        create_app(tmp_path / "recovery.db", runner=None, queue_runner=None)
    ) as test_client:
        monkeypatch.setattr(main, "backend", lambda: http_backend(test_client))
        yield test_client


class TransientModel(StubModel):
    failures_left: int = 1
    calls: int = 0

    def _generate(self, *args, **kwargs):
        self.calls += 1
        if self.failures_left:
            self.failures_left -= 1
            raise httpx.ReadTimeout("secret-provider-detail")
        return super()._generate(*args, **kwargs)


def test_bounded_model_retry_is_not_a_claim_failure(client):
    attempt = start(client).json()
    llm = TransientModel(messages=scripted_model().messages)
    main.run("CLM-1001", attempt["thread_id"], llm)
    assert llm.calls > 1
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["failures"] == 0
    assert claim["payment"]["amount"] == 420
    assert (
        "secret-provider-detail" not in client.get("/api/claims/CLM-1001/events").text
    )


def test_model_retry_exhaustion_and_step_limit(client):
    attempt = start(client).json()
    llm = TransientModel(messages=iter([]), failures_left=3)
    with pytest.raises(httpx.ReadTimeout):
        main.run("CLM-1001", attempt["thread_id"], llm)
    assert llm.calls == 2
    with pytest.raises(GraphRecursionError):
        main.run(
            "CLM-1001",
            attempt["thread_id"],
            StubModel(messages=repeat(call("list_sections", {}))),
        )


@pytest.mark.parametrize("suffix", ["decision", "agent-payment"])
def test_lost_commit_response_is_reconciled(client, monkeypatch, suffix):
    attempt = start(client).json()
    original = client.request
    writes = []

    def lose_response(method, url, **kwargs):
        response = original(method, url, **kwargs)
        if url.endswith(f"/{suffix}"):
            writes.append(url)
            raise httpx.ReadTimeout("Lost response after commit")
        return response

    monkeypatch.setattr(client, "request", lose_response)
    main.run("CLM-1001", attempt["thread_id"], scripted_model())
    assert len(writes) == 1
    store = client.app.state.store
    with store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 1


def test_transient_payment_failure_retries_only_the_payment(client, monkeypatch):
    attempt = start(client).json()
    original = client.request
    writes = []

    def fail_first(method, url, **kwargs):
        if url.endswith("/agent-payment"):
            writes.append(url)
            if len(writes) == 1:
                raise httpx.ConnectError("Connection lost")
        return original(method, url, **kwargs)

    monkeypatch.setattr(client, "request", fail_first)
    main.run("CLM-1001", attempt["thread_id"], scripted_model())
    assert len(writes) == 2
    assert client.get("/api/claims/CLM-1001").json()["payment"]["amount"] == 420


def test_exhausted_payment_recovery_preserves_the_decision(client, monkeypatch):
    attempt = start(client).json()
    original = client.request
    calls = []

    def refuse_payment(method, url, **kwargs):
        if url.endswith("/agent-payment"):
            calls.append(url)
            raise httpx.ConnectError("Synthetic payment outage")
        return original(method, url, **kwargs)

    monkeypatch.setattr(client, "request", refuse_payment)
    with pytest.raises(httpx.ConnectError):
        main.run("CLM-1001", attempt["thread_id"], scripted_model())
    assert len(calls) == 2
    store = client.app.state.store
    workflow = Workflow(store)
    workflow.finish(attempt["run_id"], "Agent could not finish.")
    claim = workflow.detail("CLM-1001")
    assert claim.decision
    assert claim.decision.outcome == "approve"
    assert claim.status == "decided"
    assert claim.payment is None
    task = Harness(store).get(attempt["parent_run_id"]).tasks[0]
    assert task.state == "needs_handler"
    assert "unresolved" in task.reason
    assert workflow.runs("CLM-1001")[0].status == "failed"


def test_failed_decision_write_does_not_invent_a_commit(client, monkeypatch):
    attempt = start(client).json()
    original = client.request

    def refuse_decision(method, url, **kwargs):
        if url.endswith("/decision"):
            raise httpx.ConnectError("Synthetic decision outage")
        return original(method, url, **kwargs)

    monkeypatch.setattr(client, "request", refuse_decision)
    with pytest.raises(httpx.ConnectError):
        main.run("CLM-1001", attempt["thread_id"], scripted_model())
    assert client.get("/api/claims/CLM-1001").json()["decision"] is None


def test_expired_attempt_cannot_write_or_read_sources(client):
    attempt = start(client).json()
    store = client.app.state.store
    with store.transaction() as connection:
        connection.execute(
            "UPDATE runs SET deadline = '2000-01-01' WHERE run_id = ?",
            (attempt["run_id"],),
        )
    body = {"amount": 1, "run_id": attempt["run_id"]}
    assert (
        client.post("/api/claims/CLM-1001/agent-payment", json=body).status_code == 409
    )
    assert (
        client.post(
            "/api/claims/CLM-1001/reads",
            json={"run_id": attempt["run_id"], "document_id": "manual", "section": 4},
        ).status_code
        == 409
    )
    with pytest.raises(Exception, match="409"):
        main.run("CLM-1001", attempt["thread_id"], scripted_model())
    assert client.get("/api/claims/CLM-1001").json()["decision"] is None


def test_rejected_step_can_be_corrected_without_sensitive_error(client):
    attempt = start(client).json()
    replies = [
        call("read_section", {"document_id": "unknown-secret", "section": 1}),
        *list(scripted_model().messages),
    ]
    main.run("CLM-1001", attempt["thread_id"], StubModel(messages=iter(replies)))
    events = client.get("/api/claims/CLM-1001/events").text
    assert "tool_failed" in events
    assert "unknown-secret" not in events


def test_fresh_helpers_never_share_messages(client, monkeypatch):
    captured = []
    original = main.create_agent

    def capture(*args, **kwargs):
        agent = Mock(wraps=original(*args, **kwargs))
        captured.append(agent)
        return agent

    monkeypatch.setattr(main, "create_agent", capture)
    first = start(client).json()
    main.run("CLM-1001", first["thread_id"], scripted_model())
    Workflow(client.app.state.store).finish(first["run_id"], None)
    second = start(client, "CLM-1002").json()
    main.run("CLM-1002", second["thread_id"], scripted_model("refer", "0"))
    assert first["thread_id"] != second["thread_id"]
    assert captured[0] is not captured[1]
    assert captured[1].invoke.call_args.args[0] == {
        "messages": [{"role": "user", "content": "Process claim CLM-1002."}]
    }


@pytest.mark.parametrize(
    ("story", "outcome", "payout", "section"),
    [
        (
            "Synthetic third claim filed within 12 months; two earlier claims exist.",
            "refer",
            "0",
            9,
        ),
        (
            "Synthetic wild animal loss with guide evidence, not theft; "
            "eligible net loss $215.",
            "approve",
            "215",
            7,
        ),
        (
            "Synthetic covered 30-hour trip delay, two travelers, "
            "receipt-free meals: 35 * 2 * 2.",
            "approve",
            "140",
            10,
        ),
    ],
)
def test_synthetic_manual_workflows(client, story, outcome, payout, section):
    attempt = start(client).json()
    with client.app.state.store.transaction() as connection:
        row = connection.execute(
            "SELECT body FROM records WHERE kind = 'claims' AND id = 'CLM-1001'"
        ).fetchone()
        claim = json.loads(row["body"])
        claim["story"] = story
        connection.execute(
            "UPDATE records SET body = ? WHERE kind = 'claims' AND id = 'CLM-1001'",
            (json.dumps(claim),),
        )
    replies = [
        call("read_context", {}),
        call("read_section", {"document_id": "wording", "section": 3}),
        call("read_section", {"document_id": "manual", "section": section}),
        call(
            "record_decision",
            {
                "outcome": outcome,
                "payout": payout,
                "calculation": story,
                "explanation": "Synthetic manual workflow fixture. See the cited rule.",
                "policy_sections": [3],
                "manual_version": "2026.2",
                "manual_sections": [section],
            },
        ),
        AIMessage(content="Done"),
    ]
    main.run("CLM-1001", attempt["thread_id"], StubModel(messages=iter(replies)))
    final = client.get("/api/claims/CLM-1001").json()
    assert final["decision"]["outcome"] == outcome
    assert final["decision"]["payout"] == float(payout)
    assert final["decision"]["manual_sections"] == [section]


def test_role_instructions_and_retry_classification(client):
    assert client.get("/api/instructions/no").status_code == 404
    assert (
        "Delegate one claim at a time"
        in client.get("/api/instructions/queue").json()["text"]
    )
    assert not transient(ValueError("invalid"))
    request = httpx.Request("GET", "http://test")
    for status, retry in ((400, False), (429, True), (503, True)):
        error = httpx.HTTPStatusError(
            "safe", request=request, response=httpx.Response(status, request=request)
        )
        assert transient(error) == retry
    assert PublicActivity(lambda _: None)
