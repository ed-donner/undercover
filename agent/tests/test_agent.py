from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main
from backend.main import app


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


def test_instructions(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    assert "decide_claim" in main.instructions()


def test_claim_tools(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    get_claim, get_policy_wording, decide_claim = main.claim_tools("CLM-1001")

    claim = get_claim.invoke({})
    assert claim["claim_id"] == "CLM-1001"

    wording = get_policy_wording.invoke({})
    assert "Trip Delay" in wording

    result = decide_claim.invoke(
        {
            "decision": "approve",
            "payout": 420.0,
            "reason": "Routine trip delay with receipts.",
            "policy_reference": "Section 3",
        }
    )
    assert result == "Recorded"

    client = TestClient(app)
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert len(steps) == 3
    assert client.get("/api/claims/CLM-1001").json()["status"] == "decided"


def test_run(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    replies = [
        AIMessage(
            content="", tool_calls=[{"name": "get_claim", "args": {}, "id": "1"}]
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
                        "decision": "approve",
                        "payout": 420.0,
                        "reason": "Routine trip delay with receipts.",
                        "policy_reference": "Section 3",
                    },
                    "id": "3",
                }
            ],
        ),
        AIMessage(content="Approved the claim for $420.00."),
    ]
    assert (
        main.run("CLM-1001", "thread-1", StubModel(messages=iter(replies)))
        == "Approved the claim for $420.00."
    )

    client = TestClient(app)
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["decision"] == "approve"

    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [step["text"] for step in steps] == [
        "Read the claim, its policy and the customer's claim history",
        "Read the policy wording",
        "Decided: approve for $420.00",
    ]


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
