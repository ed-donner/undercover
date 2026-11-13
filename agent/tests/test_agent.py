import json
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main
from backend.main import create_app
from backend.tests.helpers import http_backend, start


class StubModel(GenericFakeChatModel):
    """A scripted model that never calls a provider."""

    def bind_tools(self, tools, **kwargs):
        return self


@pytest.fixture
def client(tmp_path, monkeypatch):
    with TestClient(
        create_app(tmp_path / "agent.db", runner=None, queue_runner=None)
    ) as test_client:
        monkeypatch.setattr(main, "backend", lambda: http_backend(test_client))
        yield test_client


def call(name, args):
    if name == "record_decision":
        args = {"decision": args}
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
        call("list_sections", {}),
        call("search_sections", {"document_id": "wording", "query": "delay"}),
        call("read_section", {"document_id": "wording", "section": 3}),
        call("read_section", {"document_id": "wording", "section": 10}),
        call("read_section", {"document_id": "manual", "section": 4}),
        call(
            "record_decision",
            {
                "outcome": outcome,
                "payout": payout,
                "calculation": "Eligible expenses, less compensation and deductible.",
                "explanation": "Documents support this decision. See cited wording.",
                "policy_sections": [3, 10],
                "manual_version": "2026.2",
                "manual_sections": [4],
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
    active = start(client).json()
    assert main.run(
        "CLM-1001", active["thread_id"], scripted_model(outcome, payout)
    ) == ("Decision recorded.")
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["decision"]["outcome"] == outcome
    assert (claim["payment"] is not None) == paid


def test_scoped_tools_and_api_context(client):
    active = start(client).json()
    tools = main.ClaimTools(client, "CLM-1001", active["run_id"]).tools()
    assert [item.name for item in tools] == [
        "read_context",
        "list_sections",
        "search_sections",
        "read_section",
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
    assert "## 3. Trip Delay" in tools[3].invoke(
        {"document_id": "wording", "section": 3}
    )


def test_must_read_before_deciding(client):
    active = start(client).json()
    tools = main.ClaimTools(client, "CLM-1001", active["run_id"]).tools()
    with pytest.raises(RuntimeError, match="Read context"):
        tools[4].invoke(
            {
                "decision": {
                    "outcome": "refer",
                    "payout": "0",
                    "calculation": "No payout.",
                    "explanation": "Missing evidence. Please review.",
                    "policy_sections": [11],
                    "manual_version": "2026.2",
                    "manual_sections": [4],
                }
            }
        )
    assert client.get("/api/claims/CLM-1001").json()["decision"] is None


def test_failures_are_not_success(client):
    with pytest.raises(Exception, match="404 Not Found"):
        main.run("no", "no", scripted_model())
    with pytest.raises(RuntimeError, match="No active run"):
        main.run("CLM-1001", "no", scripted_model())
    active = start(client).json()
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
    active = start(client).json()
    main.run("CLM-1001", active["thread_id"], scripted_model())
    assert (
        captured["system_prompt"]
        == client.get("/api/instructions/claim").json()["text"]
    )
    assert captured["agent"].invoke.call_args.kwargs["config"]["configurable"] == {
        "thread_id": active["thread_id"]
    }
    assert (
        client.get("/api/claims/CLM-1001").json()["decision"]["run_id"]
        == active["run_id"]
    )


def test_missing_payment_is_reconciled_without_redeciding(client):
    active = start(client).json()
    replies = list(scripted_model().messages)
    without_payment = StubModel(messages=iter([*replies[:-2], replies[-1]]))
    main.run("CLM-1001", active["thread_id"], without_payment)
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["decision"]["outcome"] == "approve"
    assert claim["payment"]["amount"] == 420


def test_backend_tool_failure_does_not_record_a_decision(client):
    active = start(client).json()
    with client.app.state.store.transaction() as connection:
        connection.execute("DELETE FROM records WHERE kind = 'policies'")
    with pytest.raises(RuntimeError, match="Read context"):
        main.run("CLM-1001", active["thread_id"], scripted_model())
    assert client.get("/api/claims/CLM-1001").json()["decision"] is None


def test_model_configuration(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    default = main.model()
    assert default.model_name == "deepseek/deepseek-v4.1-flash"
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
