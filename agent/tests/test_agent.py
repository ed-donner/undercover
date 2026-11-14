from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main
from backend import db
from backend.main import app


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    seen: list = []

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, *args, **kwargs):
        self.seen.append(messages)
        return super()._generate(messages, *args, **kwargs)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "test.db"))
    db.seed()
    client = TestClient(app)
    monkeypatch.setattr(main, "backend", lambda: client)
    return client


def tool_call(name, **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": name}])


def stub(*replies):
    return StubModel(messages=iter(replies), seen=[])


def decision(payout):
    return tool_call(
        "record_decision",
        claim_id="CLM-1001",
        decision="approve",
        payout=payout,
        reason="Meridian Air canceled the flight for a crew problem.",
        policy_section="3. Trip Delay",
    )


READS = [
    tool_call("get_claim", claim_id="CLM-1001"),
    tool_call("get_policy", policy_id="POL-2001"),
    tool_call("get_claim_history", customer_id="CUS-3001"),
    tool_call("get_policy_wording"),
]


def test_full_run(client):
    llm = stub(
        *READS,
        decision(420.0),
        tool_call("pay_claim", claim_id="CLM-1001", amount=420.0),
        AIMessage(content="Approved and paid $420.00."),
    )
    assert main.run("CLM-1001", "thread-1", llm) == "Approved and paid $420.00."
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["paid_amount"] == 420.0
    steps = client.get("/api/claims/CLM-1001/steps").json()
    calls = [s["content"].split("(")[0] for s in steps if s["kind"] == "tool_call"]
    assert calls == [
        "get_claim",
        "get_policy",
        "get_claim_history",
        "get_policy_wording",
        "record_decision",
        "pay_claim",
    ]
    assert steps[1]["kind"] == "tool_result"
    assert steps[1]["content"].startswith("get_claim: ")
    assert steps[1]["content"].endswith("...")
    assert steps[-1] == steps[-1] | {"kind": "message"}


def test_large_payout_waits_for_signoff(client):
    llm = stub(
        decision(1150.0),
        tool_call("pay_claim", claim_id="CLM-1001", amount=1150.0),
        AIMessage(content="Approved; the payment waits for sign-off."),
    )
    main.run("CLM-1001", "thread-1", llm)
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "awaiting_signoff"
    assert claim["paid_at"] is None
    results = [
        s["content"]
        for s in client.get("/api/claims/CLM-1001/steps").json()
        if s["kind"] == "tool_result"
    ]
    assert results[-1] == (
        "pay_claim: Refused: The payout is over $1,000.00, so the payment waits "
        "for a handler's sign-off"
    )


def test_instructions_come_from_the_backend(client, monkeypatch, tmp_path):
    served = tmp_path / "instructions.md"
    served.write_text("Served instructions for the test.")
    monkeypatch.setattr("backend.main.INSTRUCTIONS", served)
    llm = stub(AIMessage(content="Done."))
    main.run("CLM-1001", "thread-1", llm)
    assert llm.seen[0][0].content == "Served instructions for the test."


def test_run_refused_for_a_claim_not_waiting(client):
    client.post("/api/claims/CLM-1001/start")
    llm = stub(AIMessage(content="Done."))
    assert main.run("CLM-1001", "thread-1", llm) == (
        "Refused: CLM-1001 is in_progress, not waiting"
    )
    assert llm.seen == []


class FailingModel(StubModel):
    """A chat model that fails the way an unavailable model does."""

    def _generate(self, messages, *args, **kwargs):
        raise RuntimeError("model unavailable")


def test_failed_run_puts_the_claim_back(client):
    with pytest.raises(RuntimeError, match="model unavailable"):
        main.run("CLM-1001", "thread-1", FailingModel(messages=iter([])))
    assert client.get("/api/claims/CLM-1001").json()["status"] == "waiting"
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert steps[-1]["kind"] == "error"
    assert steps[-1]["content"] == "The agent stopped with an error: model unavailable"


def test_run_without_a_decision_puts_the_claim_back(client):
    llm = stub(AIMessage(content="Decision: decline, payout $0."))
    main.run("CLM-1001", "thread-1", llm)
    assert client.get("/api/claims/CLM-1001").json()["status"] == "waiting"
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert steps[-1]["content"] == "The agent finished without recording a decision"


def test_refused_run_leaves_the_other_run_alone(client):
    client.post("/api/claims/CLM-1001/start")
    main.run("CLM-1001", "thread-2", stub(AIMessage(content="Done.")))
    assert client.get("/api/claims/CLM-1001").json()["status"] == "in_progress"
    assert client.get("/api/claims/CLM-1001/steps").json() == []


def test_tools_only_call_the_backend():
    names = [t.name for t in main.TOOLS]
    assert names == [
        "get_claim",
        "get_policy",
        "get_claim_history",
        "get_policy_wording",
        "record_decision",
        "pay_claim",
    ]
    source = Path(main.__file__).read_text(encoding="utf-8")
    assert "data/" not in source
    assert "open(" not in source


def test_server_errors_raise(monkeypatch):
    transport = httpx.MockTransport(lambda _: httpx.Response(500))
    monkeypatch.setattr(
        main, "backend", lambda: httpx.Client(transport=transport, base_url="http://x")
    )
    with pytest.raises(httpx.HTTPStatusError):
        main.call("GET", "/api/policy-wording")


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    assert main.model().reasoning_effort == "low"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
