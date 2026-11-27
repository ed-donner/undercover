import runpy

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main
from backend.main import app

CLAIM = "CLM-1001"


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


class RecordingClient(TestClient):
    """A test client that remembers every path the agent calls."""

    paths: list[str] = []

    def request(self, method, url, *args, **kwargs):
        RecordingClient.paths.append(str(url))
        return super().request(method, url, *args, **kwargs)


@pytest.fixture
def backend(client, monkeypatch):
    RecordingClient.paths = []
    monkeypatch.setattr(main, "backend", lambda: RecordingClient(app))
    return client


def call(name, args, call_id):
    return {"name": name, "args": args, "id": call_id}


def decision(payout):
    return {
        "decision": "approve",
        "payout": payout,
        "calculation": "245 + 95 + 80 = 420",
        "reasons": "The airline canceled the flight. The costs are covered.",
        "policy_section": "3. Trip Delay",
    }


def stub(*replies):
    return StubModel(messages=iter(replies))


def test_run_approves_and_pays(backend):
    llm = stub(
        AIMessage(content="", tool_calls=[call("get_claim", {}, "1")]),
        AIMessage(
            content="",
            tool_calls=[
                call("get_policy", {"policy_id": "POL-2001"}, "2"),
                call("get_customer", {"customer_id": "CUS-3001"}, "3"),
                call("get_policy_wording", {}, "4"),
            ],
        ),
        AIMessage(content="", tool_calls=[call("record_decision", decision(420), "5")]),
        AIMessage(content="", tool_calls=[call("pay_claim", {"amount": 420}, "6")]),
        AIMessage(content="Approved and paid $420.00."),
    )
    assert main.run(CLAIM, "thread-1", llm) == "Approved and paid $420.00."
    claim = backend.get(f"/api/claims/{CLAIM}").json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 420.0
    steps = backend.get(f"/api/claims/{CLAIM}/steps").json()
    kinds = [s["kind"] for s in steps]
    assert kinds.count("tool_call") == 6
    assert kinds.count("tool_result") == 6
    assert kinds[-1] == "message"
    wording = next(s for s in steps if s["content"].startswith("get_policy_wording:"))
    assert wording["content"].endswith("...")
    assert all(path.startswith("/api/") for path in RecordingClient.paths)


def test_payment_over_limit_is_refused(backend):
    llm = stub(
        AIMessage(
            content="", tool_calls=[call("record_decision", decision(1500), "1")]
        ),
        AIMessage(content="", tool_calls=[call("pay_claim", {"amount": 1500}, "2")]),
        AIMessage(content="Approved; waiting for sign-off."),
    )
    main.run(CLAIM, "thread-1", llm)
    claim = backend.get(f"/api/claims/{CLAIM}").json()
    assert claim["status"] == "awaiting_signoff"
    assert claim["payment"] is None
    steps = backend.get(f"/api/claims/{CLAIM}/steps").json()
    refusal = next(s for s in steps if s["content"].startswith("pay_claim:"))
    assert "Refused (403)" in refusal["content"]


def test_failed_run_returns_claim_to_queue(backend):
    class FailingModel(StubModel):
        def _generate(self, *args, **kwargs):
            raise RuntimeError("model unavailable")

    with pytest.raises(RuntimeError):
        main.run(CLAIM, "thread-1", FailingModel(messages=iter([])))
    assert backend.get(f"/api/claims/{CLAIM}").json()["status"] == "waiting"
    steps = backend.get(f"/api/claims/{CLAIM}/steps").json()
    assert steps[-1] == steps[-1] | {"kind": "error", "content": "model unavailable"}


def test_run_without_decision_returns_claim_to_queue(backend):
    main.run(CLAIM, "thread-1", stub(AIMessage(content="I am not sure.")))
    assert backend.get(f"/api/claims/{CLAIM}").json()["status"] == "waiting"
    steps = backend.get(f"/api/claims/{CLAIM}/steps").json()
    assert steps[-1]["kind"] == "error"


def test_command_line(monkeypatch, capsys):
    monkeypatch.setattr(main, "run", lambda claim_id, thread_id: f"ran {claim_id}")
    monkeypatch.setattr("sys.argv", ["agent", CLAIM])
    runpy.run_module("agent", run_name="__main__")
    assert capsys.readouterr().out == f"ran {CLAIM}\n"


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"


def test_run_continues_a_claim_already_started(backend):
    backend.post(f"/api/claims/{CLAIM}/start")
    llm = stub(
        AIMessage(content="", tool_calls=[call("record_decision", decision(420), "1")]),
        AIMessage(content="Approved."),
    )
    assert main.run(CLAIM, "thread-1", llm) == "Approved."
    assert backend.get(f"/api/claims/{CLAIM}").json()["status"] == "decided"


def test_run_refuses_a_decided_claim(backend):
    backend.post(f"/api/claims/{CLAIM}/start")
    backend.post(
        f"/api/claims/{CLAIM}/decision",
        json=decision(420) | {"decision": "refer", "payout": 0},
    )
    with pytest.raises(ValueError, match="nothing to decide"):
        main.run(CLAIM, "thread-1", stub())
