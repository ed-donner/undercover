from contextlib import nullcontext

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main

CLAIM = "CLM-1001"


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


class BrokenModel(StubModel):
    def _generate(self, *args, **kwargs):
        raise RuntimeError("The model is down")


def call(name: str, **args) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": name}])


def decision(outcome: str, payout: float) -> AIMessage:
    return call(
        "record_decision",
        claim_id=CLAIM,
        decision=outcome,
        payout=payout,
        explanation="The delay is covered.",
        policy_section="Section 3, Trip Delay",
    )


def stub(*replies: AIMessage) -> StubModel:
    return StubModel(messages=iter(replies))


@pytest.fixture(autouse=True)
def backend_in_process(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(main, "backend", lambda: nullcontext(client))
    client.post(f"/api/claims/{CLAIM}/start")


def get(client: TestClient, path: str):
    return client.get(f"/api/claims/{CLAIM}{path}").json()


def test_the_agent_has_six_tools():
    assert {tool.name for tool in main.TOOLS} == {
        "get_claim",
        "get_policy",
        "get_customer",
        "get_policy_wording",
        "record_decision",
        "pay_claim",
    }


def test_tools_read_through_the_backend():
    assert "Maya Patel" in main.get_customer.invoke({"customer_id": "CUS-3001"})
    assert "premium" in main.get_policy.invoke({"policy_id": "POL-2001"})
    assert "Policy Wording" in main.get_policy_wording.invoke({})
    assert "My flight home" in main.get_claim.invoke({"claim_id": CLAIM})


def test_tools_return_errors_to_the_model():
    assert main.get_claim.invoke({"claim_id": "CLM-9999"}).startswith("Error 404")


def test_run_decides_and_pays_a_small_claim(client: TestClient):
    replies = [
        call("get_claim", claim_id=CLAIM),
        call("get_policy", policy_id="POL-2001"),
        call("get_customer", customer_id="CUS-3001"),
        call("get_policy_wording"),
        decision("approve", 200),
        call("pay_claim", claim_id=CLAIM, amount=200),
        AIMessage(content="Approved $200.00 for the delay."),
    ]
    assert (
        main.run(CLAIM, "thread-1", stub(*replies)) == "Approved $200.00 for the delay."
    )
    claim = get(client, "")
    assert claim["status"] == "decided"
    assert claim["decision"]["policy_section"] == "Section 3, Trip Delay"
    assert claim["payment"]["amount"] == 200
    steps = get(client, "/steps")
    kinds = [step["kind"] for step in steps]
    assert kinds == ["tool_call", "tool_result"] * 6 + ["message"]
    assert steps[0]["text"] == "get_claim({'claim_id': 'CLM-1001'})"
    assert steps[1]["text"].startswith("get_claim: ")
    assert steps[-1]["text"] == "Approved $200.00 for the delay."


def test_run_holds_a_large_payment(client: TestClient):
    replies = [
        decision("approve", 1250),
        call("pay_claim", claim_id=CLAIM, amount=1250),
        AIMessage(content="Approved $1,250.00. It waits for sign-off."),
    ]
    main.run(CLAIM, "thread-2", stub(*replies))
    claim = get(client, "")
    assert claim["status"] == "waiting_for_sign_off"
    assert claim["payment"] is None
    refusal = get(client, "/steps")[3]
    assert refusal["text"].startswith("pay_claim: Error 409")


def test_run_records_an_error_and_can_be_retried(client: TestClient):
    with pytest.raises(RuntimeError):
        main.run(CLAIM, "thread-3", BrokenModel(messages=iter([])))
    steps = get(client, "/steps")
    assert steps[-1] == {
        **steps[-1],
        "kind": "error",
        "text": "RuntimeError: The model is down",
    }
    assert get(client, "")["status"] == "in_progress"
    main.run(
        CLAIM, "thread-3", stub(decision("decline", 0), AIMessage(content="Declined."))
    )
    assert get(client, "")["status"] == "decided"


def test_model_name(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
