import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main
from backend.main import app

client = TestClient(app)


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


def tool_call(name, **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": name}])


def script(claim_id, decision, payout, pay=None):
    replies = [
        tool_call("start_claim", claim_id=claim_id),
        tool_call("get_claim", claim_id=claim_id),
        tool_call("get_policy", claim_id=claim_id),
        tool_call("get_claim_history", claim_id=claim_id),
        tool_call("get_policy_wording"),
        tool_call(
            "record_decision",
            claim_id=claim_id,
            decision=decision,
            payout=payout,
            reason="The delay is covered.",
            policy_section="Section 3, Trip Delay",
        ),
    ]
    if pay is not None:
        replies.append(tool_call("pay_claim", claim_id=claim_id, amount=pay))
    replies.append(AIMessage(content=f"{claim_id}: {decision}, ${payout:,.2f}"))
    return StubModel(messages=iter(replies))


@pytest.fixture(autouse=True)
def local_backend(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))


def test_run_works_a_claim_end_to_end():
    reply = main.run(
        "CLM-1001", "thread-1", script("CLM-1001", "approve", 420.0, 420.0)
    )
    assert reply == "CLM-1001: approve, $420.00"
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["decision"]["policy_section"] == "Section 3, Trip Delay"
    assert claim["payment"]["amount"] == 420.0
    steps = [s["text"] for s in client.get("/api/claims/CLM-1001/steps").json()]
    assert steps == [
        "Taking the claim from the queue",
        "Reading the claim",
        "Reading the policy and its plan",
        "Reading the customer's earlier claims",
        "Reading the policy wording",
        "Recording the decision: approve, payout $420.00, Section 3, Trip Delay."
        " The delay is covered.",
        "Paying $420.00",
        "Finished: CLM-1001: approve, $420.00",
    ]
    assert all(len(s) <= main.STEP_LENGTH + 3 for s in steps)


def test_payment_over_the_limit_is_refused():
    main.run("CLM-1003", "thread-2", script("CLM-1003", "approve", 1500.0, 1500.0))
    claim = client.get("/api/claims/CLM-1003").json()
    assert claim["status"] == "awaiting_signoff"
    assert claim["payment"] is None
    steps = [s["text"] for s in client.get("/api/claims/CLM-1003/steps").json()]
    assert "Paying $1,500.00" in steps
    assert any(
        s.startswith("pay_claim was refused: Refused (409)") and "sign-off" in s
        for s in steps
    )


def test_long_steps_are_shortened():
    main.StepRecorder("CLM-1001").record("x" * 1000)
    step = client.get("/api/claims/CLM-1001/steps").json()[0]["text"]
    assert len(step) == main.STEP_LENGTH + 3


def test_pay_claim_tool_returns_the_refusal():
    assert main.pay_claim.invoke({"claim_id": "CLM-1001", "amount": 10.0}).startswith(
        "Refused (409)"
    )


def test_main_works_only_waiting_claims_in_order(monkeypatch, capsys):
    client.post("/api/claims/CLM-1002/start")
    worked = []
    monkeypatch.setattr(
        main, "run", lambda claim_id, thread_id, llm: worked.append(claim_id) or "done"
    )
    main.main([])
    assert worked[:3] == ["CLM-1001", "CLM-1003", "CLM-1004"]
    assert len(worked) == 24
    assert "CLM-1001: done" in capsys.readouterr().out


def test_main_works_one_claim(capsys):
    main.main(["CLM-1004"], script("CLM-1004", "decline", 0))
    assert "CLM-1004: decline, $0.00" in capsys.readouterr().out
    assert client.get("/api/claims/CLM-1004").json()["status"] == "decided"


def test_instructions_come_from_the_backend():
    assert main.instructions() == client.get("/api/instructions").json()["text"]


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    assert main.model().reasoning_effort == "low"
    assert main.model().max_retries == main.MODEL_RETRIES
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
