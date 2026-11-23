import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from pydantic import Field

from agent import main
from backend.main import INSTRUCTIONS, app


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    seen: list[list[BaseMessage]] = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, *args, **kwargs):
        self.seen.append(messages)
        return super()._generate(messages, *args, **kwargs)


def script(*calls: tuple[str, dict], reply: str) -> StubModel:
    """A stub that makes each tool call in turn, then gives the final reply."""
    messages = [
        AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": str(i)}])
        for i, (name, args) in enumerate(calls)
    ]
    return StubModel(messages=iter([*messages, AIMessage(content=reply)]))


def decision(claim_id: str, kind: str, payout: float) -> tuple[str, dict]:
    return "record_decision", {
        "claim_id": claim_id,
        "decision": kind,
        "payout": payout,
        "explanation": "It is covered.",
        "policy_section": "3. Trip Delay",
    }


@pytest.fixture(autouse=True)
def wired(client, monkeypatch):
    """Point the agent at the test backend, on its fresh database."""
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))


def test_the_agent_decides_and_pays(client):
    llm = script(
        ("get_claim_context", {"claim_id": "CLM-1001"}),
        ("get_policy_wording", {}),
        decision("CLM-1001", "approve", 420.0),
        ("pay_claim", {"claim_id": "CLM-1001", "amount": 420.0}),
        reply="Approved, $420.00.",
    )
    assert main.run("CLM-1001", "thread-1", llm) == "Approved, $420.00."
    detail = client.get("/api/claims/CLM-1001").json()
    assert detail["decision"]["decision"] == "approve"
    assert detail["payment"]["amount"] == 420.0
    assert detail["state"] == "decided"


def test_a_payout_over_the_limit_waits_for_sign_off(client):
    llm = script(
        decision("CLM-1002", "approve", 1500.0),
        ("pay_claim", {"claim_id": "CLM-1002", "amount": 1500.0}),
        reply="Approved, the payment waits for a handler.",
    )
    main.run("CLM-1002", "thread-1", llm)
    detail = client.get("/api/claims/CLM-1002").json()
    assert detail["state"] == "waiting for sign-off"
    assert detail["payment"] is None
    steps = client.get("/api/claims/CLM-1002/steps").json()
    refusal = next(
        s for s in steps if s["kind"] == "tool_result" and "Refused" in s["text"]
    )
    assert "sign-off" in refusal["text"]


def test_the_system_prompt_comes_from_the_backend(client):
    llm = script(reply="Nothing to do.")
    main.run("CLM-1001", "thread-1", llm)
    system = llm.seen[0][0]
    assert isinstance(system, SystemMessage)
    assert system.content == INSTRUCTIONS.read_text(encoding="utf-8")
    assert system.content == client.get("/api/instructions").json()["text"]


def test_the_agent_records_its_steps_in_order(client):
    llm = script(
        ("get_claim_context", {"claim_id": "CLM-1001"}),
        decision("CLM-1001", "decline", 0.0),
        reply="Declined.",
    )
    main.run("CLM-1001", "thread-1", llm)
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [step["kind"] for step in steps] == [
        "tool_call",
        "tool_result",
        "tool_call",
        "tool_result",
        "message",
    ]
    assert steps[0]["text"] == 'get_claim_context({"claim_id": "CLM-1001"})'
    assert steps[-1]["text"] == "Declined."


def test_long_results_are_shortened_in_the_steps(client):
    main.run("CLM-1001", "t", script(("get_policy_wording", {}), reply="Read."))
    result = client.get("/api/claims/CLM-1001/steps").json()[1]["text"]
    assert result.endswith(" ...")
    assert len(result) < 700


def test_a_message_with_a_tool_call_is_recorded_as_both(client):
    call = {"name": "get_policy_wording", "args": {}, "id": "1"}
    llm = StubModel(
        messages=iter(
            [
                AIMessage(content="Reading.", tool_calls=[call]),
                AIMessage(content="Done."),
            ]
        )
    )
    main.run("CLM-1001", "t", llm)
    kinds = [s["kind"] for s in client.get("/api/claims/CLM-1001/steps").json()]
    assert kinds == ["message", "tool_call", "tool_result", "message"]


def test_the_tools_pass_on_the_backend_answers(client):
    context = json.loads(main.get_claim_context.invoke({"claim_id": "CLM-1001"}))
    assert context["claim"]["claim_id"] == "CLM-1001"
    assert main.get_policy_wording.invoke({}).startswith("# UnderCover")
    refused = main.pay_claim.invoke({"claim_id": "CLM-1001", "amount": 5.0})
    assert refused.startswith("Refused:")
    unknown = main.get_claim_context.invoke({"claim_id": "CLM-0000"})
    assert unknown == "Refused: No claim CLM-0000"


def test_the_agent_package_reads_nothing_from_data():
    for source in Path(main.__file__).parent.glob("*.py"):
        text = source.read_text(encoding="utf-8")
        for forbidden in ("data/", "evals", "read_text", "open("):
            assert forbidden not in text, f"{source.name}: {forbidden}"


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
