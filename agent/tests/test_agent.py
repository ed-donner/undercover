from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main
from backend.main import app


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


def test_claim_instructions(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    assert "decide_claim" in main.claim_instructions()


def test_claim_tools(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    get_claim, list_sections, read_section, decide_claim = main.claim_tools("CLM-1001")

    claim = get_claim.invoke({})
    assert claim["claim_id"] == "CLM-1001"

    headings = list_sections.invoke({"document": "policy_wording"})
    assert "3. Trip Delay" in headings

    wording = read_section.invoke(
        {"document": "policy_wording", "heading": "3. Trip Delay"}
    )
    assert "delay" in wording.lower()

    manual = read_section.invoke(
        {"document": "claims_manual", "heading": "9. Repeat claims"}
    )
    assert "12 months" in manual

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
    assert [step["text"] for step in steps] == [
        "Read the claim, its policy and the customer's claim history",
        "Read policy wording section: 3. Trip Delay",
        "Read claims manual section: 9. Repeat claims",
        "Decided: approve for $420.00",
    ]
    assert client.get("/api/claims/CLM-1001").json()["status"] == "decided"


def test_run(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    replies = [
        AIMessage(
            content="", tool_calls=[{"name": "get_claim", "args": {}, "id": "1"}]
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "list_sections",
                    "args": {"document": "policy_wording"},
                    "id": "2",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "read_section",
                    "args": {
                        "document": "policy_wording",
                        "heading": "3. Trip Delay",
                    },
                    "id": "3",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "list_sections",
                    "args": {"document": "claims_manual"},
                    "id": "4",
                }
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "read_section",
                    "args": {
                        "document": "claims_manual",
                        "heading": "9. Repeat claims",
                    },
                    "id": "5",
                }
            ],
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
                    "id": "6",
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
        "Read policy wording section: 3. Trip Delay",
        "Read claims manual section: 9. Repeat claims",
        "Decided: approve for $420.00",
    ]


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "deepseek/deepseek-v4.1-flash"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
