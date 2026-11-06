from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main
from backend import db
from backend.main import app


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


def test_get_claim(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    claim = main.get_claim.invoke({"claim_id": "CLM-1001"})
    assert claim["claim_id"] == "CLM-1001"
    assert claim["policy"]["plan"] == "premium"


def test_get_policy_wording(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    assert "Emergency Medical" in main.get_policy_wording.invoke({})


def test_decide_claim(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    result = main.decide_claim.invoke(
        {
            "claim_id": "CLM-1001",
            "decision": "approve",
            "payout": 420.0,
            "reason": "A routine trip delay with receipts.",
            "reference": "Policy wording, section 3",
        }
    )
    assert result["decision"] == "approve"
    assert result["payout"] == 420.0


def test_pay_claim(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    main.decide_claim.invoke(
        {
            "claim_id": "CLM-1001",
            "decision": "approve",
            "payout": 420.0,
            "reason": "A routine trip delay with receipts.",
            "reference": "Policy wording, section 3",
        }
    )
    result = main.pay_claim.invoke({"claim_id": "CLM-1001", "amount": 420.0})
    assert result == {"paid": True, "status": "decided"}


def test_instructions(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    assert "policy wording" in main.instructions()


def test_run_approves_and_pays_under_the_limit(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    replies = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "get_claim", "args": {"claim_id": "CLM-1001"}, "id": "1"}
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
                        "claim_id": "CLM-1001",
                        "decision": "approve",
                        "payout": 420.0,
                        "reason": "A routine trip delay with receipts.",
                        "reference": "Policy wording, section 3",
                    },
                    "id": "3",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "pay_claim",
                    "args": {"claim_id": "CLM-1001", "amount": 420.0},
                    "id": "4",
                }
            ],
        ),
        AIMessage(content="Approved for $420.00. Policy wording, section 3."),
    ]
    reply = main.run("CLM-1001", "thread-1", StubModel(messages=iter(replies)))
    assert reply == "Approved for $420.00. Policy wording, section 3."

    claim = db.require_claim("CLM-1001")
    assert claim["status"] == "decided"
    assert claim["paid_amount"] == 420.0


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
