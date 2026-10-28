from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage
from pydantic import Field

from agent import main
from backend import main as backend

DECISION = {
    "claim_id": "CLM-1001",
    "decision": "approve",
    "payout": 420.0,
    "reason": "The flight was canceled for a crew problem. The costs are covered.",
    "policy_section": "Section 3, Trip Delay",
}


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    seen: list[list[BaseMessage]] = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append(messages)
        return super()._generate(messages, stop, run_manager, **kwargs)


class BrokenModel(StubModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise RuntimeError("model unavailable")


def call_tool(name, **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": name}])


def stub(*replies):
    return StubModel(messages=iter(replies))


def claim(claim_id):
    return main.call("GET", f"/api/claims/{claim_id}")


def recorded_steps(claim_id):
    return main.call("GET", f"/api/claims/{claim_id}/steps")


def test_tools_call_the_backend():
    assert main.get_claim.invoke({"claim_id": "CLM-1001"})["policy_id"] == "POL-2001"
    assert main.get_policy.invoke({"policy_id": "POL-2001"})["plan"] == "premium"
    history = main.get_claim_history.invoke({"customer_id": "CUS-3001"})
    assert history["previous_claims"][0]["claim_id"] == "CLM-0412"
    assert main.get_policy_wording.invoke({})["version"] == "2026.1"
    assert main.record_decision.invoke(DECISION)["status"] == "decided"
    paid = main.pay_claim.invoke({"claim_id": "CLM-1001", "amount": 420.0})
    assert paid["payment"]["amount"] == 420.0


def test_approve_and_pay():
    reply = main.run(
        "CLM-1001",
        "thread-1",
        stub(
            call_tool("get_claim", claim_id="CLM-1001"),
            call_tool("record_decision", **DECISION),
            call_tool("pay_claim", claim_id="CLM-1001", amount=420.0),
            AIMessage(content="Approved and paid $420.00."),
        ),
    )
    assert reply == "Approved and paid $420.00."
    decided = claim("CLM-1001")
    assert decided["status"] == "decided"
    assert decided["payment"]["amount"] == 420.0
    kinds = [step["kind"] for step in recorded_steps("CLM-1001")]
    assert kinds == ["tool_call", "tool_result"] * 3 + ["reply"]


def test_payment_over_the_limit_is_refused():
    over = DECISION | {"claim_id": "CLM-1002", "payout": 1250.0}
    main.run(
        "CLM-1002",
        "thread-1",
        stub(
            call_tool("record_decision", **over),
            call_tool("pay_claim", claim_id="CLM-1002", amount=1250.0),
            AIMessage(content="Approved, waiting for sign-off."),
        ),
    )
    waiting = claim("CLM-1002")
    assert waiting["status"] == "awaiting_sign_off"
    assert waiting["payment"] is None
    refusal = recorded_steps("CLM-1002")[3]
    assert refusal["kind"] == "tool_result"
    assert "needs a handler's sign-off" in refusal["text"]


def test_decline():
    decline = DECISION | {"decision": "decline", "payout": 0}
    main.run(
        "CLM-1001",
        "thread-1",
        stub(call_tool("record_decision", **decline), AIMessage(content="Declined.")),
    )
    declined = claim("CLM-1001")
    assert declined["status"] == "decided"
    assert declined["decision"]["payout"] == 0
    assert declined["payment"] is None


def test_instructions_come_from_the_backend(tmp_path, monkeypatch):
    instructions = tmp_path / "instructions.md"
    instructions.write_text("Decide claims carefully.", encoding="utf-8")
    monkeypatch.setattr(backend, "INSTRUCTIONS", instructions)
    model = stub(AIMessage(content="Done."))
    main.run("CLM-1001", "thread-1", model)
    assert model.seen[0][0].content == "Decide claims carefully."


def test_a_failing_model_puts_the_claim_back(monkeypatch):
    monkeypatch.setattr(main, "model", lambda: BrokenModel(messages=iter([])))
    backend.db.init()
    with backend.db.connect() as connection:
        backend.start(connection, "CLM-1001")
    backend.work("CLM-1001")
    assert claim("CLM-1001")["status"] == "waiting"
    error = recorded_steps("CLM-1001")[-1]
    assert error["kind"] == "error"
    assert "model unavailable" in error["text"]


def test_failing_model_raises():
    with pytest.raises(RuntimeError):
        main.run("CLM-1001", "thread-1", BrokenModel(messages=iter([])))


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"


def test_the_agent_never_reads_the_data_folder():
    for path in Path(main.__file__).parent.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "data/" not in source
        assert "evals" not in source
