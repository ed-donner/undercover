import json
from contextlib import nullcontext
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main
from backend.main import create_app


class StubModel(GenericFakeChatModel):
    """A scripted model that never calls a provider."""

    def bind_tools(self, tools, **kwargs):
        return self


@pytest.fixture
def client(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path / "agent.db")) as test_client:
        monkeypatch.setattr(main, "backend", lambda: nullcontext(test_client))
        yield test_client


def call(name, args):
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": name,
                "args": args,
                "id": name,
            }
        ],
    )


def scripted_model(outcome="approve", payout="420.00"):
    messages = [
        call("read_context", {}),
        call("read_wording", {}),
        call(
            "record_decision",
            {
                "outcome": outcome,
                "payout": payout,
                "calculation": "Eligible expenses, less compensation and deductible.",
                "explanation": "Documents support this decision. See cited wording.",
                "policy_sections": [3, 10],
            },
        ),
    ]
    if outcome == "approve":
        messages.append(call("request_payment", {"amount": payout}))
    messages.append(AIMessage(content="Decision recorded."))
    return StubModel(messages=iter(messages))


@pytest.mark.parametrize(
    ("outcome", "payout", "paid"),
    [
        ("approve", "420.00", True),
        ("decline", "0", False),
        ("refer", "0", False),
        ("approve", "1000.01", False),
    ],
)
def test_run(client, outcome, payout, paid):
    active = client.post("/api/claims/CLM-1001/runs").json()
    assert main.run(
        "CLM-1001", active["thread_id"], scripted_model(outcome, payout)
    ) == ("Decision recorded.")
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["decision"]["outcome"] == outcome
    assert (claim["payment"] is not None) == paid


def test_scoped_tools_and_api_context(client):
    active = client.post("/api/claims/CLM-1001/runs").json()
    tools = main.ClaimTools(client, "CLM-1001", active["run_id"]).tools()
    assert [item.name for item in tools] == [
        "read_context",
        "read_wording",
        "record_decision",
        "request_payment",
    ]
    for item in tools:
        assert "claim_id" not in item.args
        assert "url" not in item.args
        assert "path" not in item.args
    context = json.loads(tools[0].invoke({}))
    assert context["claim"]["claim_id"] == "CLM-1001"
    assert context["policy"]["policy_id"] == "POL-2001"
    assert context["customer"]["previous_claims"]
    assert context["plan"]["plan"]["plan"] == "premium"
    assert "repeat_claim_review" not in context["company"]
    assert "## 3. Trip Delay" in tools[1].invoke({})


def test_must_read_before_deciding(client):
    active = client.post("/api/claims/CLM-1001/runs").json()
    tools = main.ClaimTools(client, "CLM-1001", active["run_id"]).tools()
    with pytest.raises(RuntimeError, match="Read context"):
        tools[2].invoke(
            {
                "outcome": "refer",
                "payout": "0",
                "calculation": "No payout.",
                "explanation": "Missing evidence. Please review.",
                "policy_sections": [11],
            }
        )
    assert client.get("/api/claims/CLM-1001").json()["decision"] is None


def test_failures_are_not_success(client):
    with pytest.raises(Exception, match="404 Not Found"):
        main.run("no", "no", scripted_model())
    with pytest.raises(RuntimeError, match="No active run"):
        main.run("CLM-1001", "no", scripted_model())
    active = client.post("/api/claims/CLM-1001/runs").json()
    with pytest.raises(RuntimeError, match="without recording"):
        main.run("CLM-1001", active["thread_id"], StubModel(messages=iter(["Done"])))


def test_entry_point_uses_backend_instructions_and_thread(client, monkeypatch):
    original = main.create_agent
    captured = {}

    def capture(*args, **kwargs):
        captured.update(kwargs)
        captured["agent"] = Mock(wraps=original(*args, **kwargs))
        return captured["agent"]

    monkeypatch.setattr(main, "create_agent", capture)
    active = client.post("/api/claims/CLM-1001/runs").json()
    main.run("CLM-1001", active["thread_id"], scripted_model())
    assert captured["system_prompt"] == client.get("/api/instructions").json()["text"]
    assert captured["agent"].invoke.call_args.kwargs["config"]["configurable"] == {
        "thread_id": active["thread_id"]
    }
    assert (
        client.get("/api/claims/CLM-1001").json()["decision"]["run_id"]
        == active["run_id"]
    )


def test_model_configuration(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    default = main.model()
    assert default.model_name == "openai/gpt-6-luna"
    assert default.reasoning_effort == "low"
    assert default.openai_api_base == main.OPENROUTER_BASE_URL
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    custom = main.model()
    assert custom.model_name == "openrouter/free"
    assert custom.reasoning_effort is None


def test_backend_configuration(monkeypatch):
    monkeypatch.setenv("BACKEND_URL", "http://127.0.0.1:8123")
    with main.backend() as client:
        assert str(client.base_url) == "http://127.0.0.1:8123"
