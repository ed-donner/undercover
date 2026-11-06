from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main as agent_main
from backend.main import app

client = TestClient(app)


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


def _script(claim_id: str, decision: str, payout: float) -> list[AIMessage]:
    messages = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "get_claim", "args": {"claim_id": claim_id}, "id": "1"}
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[{"name": "get_policy_wording", "args": {}, "id": "2"}],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "decide_claim",
                    "args": {
                        "claim_id": claim_id,
                        "decision": decision,
                        "payout": payout,
                        "reason": "Because the wording says so.",
                        "reference": "Policy wording, section 3",
                    },
                    "id": "3",
                }
            ],
        ),
    ]
    if decision == "approve":
        messages.append(
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "pay_claim",
                        "args": {"claim_id": claim_id, "amount": payout},
                        "id": "4",
                    }
                ],
            )
        )
    messages.append(AIMessage(content="Decided. Policy wording, section 3."))
    return messages


def test_run_claim_approves_and_pays_under_the_limit(monkeypatch):
    monkeypatch.setattr(agent_main, "backend", lambda: TestClient(app))
    stub = StubModel(messages=iter(_script("CLM-1001", "approve", 420.0)))
    monkeypatch.setattr(agent_main, "model", lambda: stub)

    response = client.post("/api/claims/CLM-1001/run")
    assert response.status_code == 200
    assert response.json()["reply"] == "Decided. Policy wording, section 3."

    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["paid_amount"] == 420.0


def test_run_claim_holds_an_over_limit_approval_for_sign_off(monkeypatch):
    monkeypatch.setattr(agent_main, "backend", lambda: TestClient(app))
    stub = StubModel(messages=iter(_script("CLM-1003", "approve", 3750.0)))
    monkeypatch.setattr(agent_main, "model", lambda: stub)

    client.post("/api/claims/CLM-1003/run")
    claim = client.get("/api/claims/CLM-1003").json()
    assert claim["status"] == "waiting_for_sign_off"
    assert claim["paid_amount"] is None

    response = client.post(
        "/api/claims/CLM-1003/sign-off", json={"handler_id": "HND-01"}
    )
    assert response.status_code == 200
    claim = client.get("/api/claims/CLM-1003").json()
    assert claim["status"] == "decided"
    assert claim["paid_amount"] == 3750.0


def test_run_claim_rejects_a_claim_that_is_not_waiting(monkeypatch):
    monkeypatch.setattr(agent_main, "backend", lambda: TestClient(app))
    stub = StubModel(messages=iter(_script("CLM-1001", "approve", 420.0)))
    monkeypatch.setattr(agent_main, "model", lambda: stub)

    client.post("/api/claims/CLM-1001/run")
    response = client.post("/api/claims/CLM-1001/run")
    assert response.status_code == 409
