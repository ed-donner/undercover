from typing import TypedDict

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main
from backend.main import app
from backend.store import Store


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


class SafetyScenario(TypedDict):
    """Expected behavior for a synthetic request edge case."""

    request_id: str
    expected_outcome: str
    priority: bool
    required_text: str


def scripted_model(
    outcome="approve",
    rationale="The request meets the cited sample policy.",
    include_context=True,
):
    replies = []
    if include_context:
        replies.append(
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "get_request_context", "args": {}, "id": "context"}
                ],
            )
        )
    replies.append(
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "record_progress",
                    "args": {"stage": "checking_policy"},
                    "id": "progress",
                }
            ],
        )
    )
    replies.append(
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "Recommendation",
                    "args": {
                        "outcome": outcome,
                        "rationale": rationale,
                        "policy_citations": ["Cancellation Policy: eligibility"],
                        "next_action": "Support agent to review and confirm.",
                        "priority_human_review": False,
                    },
                    "id": "recommendation",
                }
            ],
        )
    )
    return StubModel(messages=iter(replies))


@pytest.mark.parametrize("outcome", ["approve", "decline", "request_information"])
def test_run_returns_structured_recommendation(tmp_path, monkeypatch, outcome):
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / f"{outcome}.sqlite3"))
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    store = Store(tmp_path / f"{outcome}.sqlite3")
    store.initialize()
    assert store.start_run("REQ-7008")
    with TestClient(app):
        result = main.run("REQ-7008", "thread-1", scripted_model(outcome))
    assert result["outcome"] == outcome
    assert result["policy_citations"] == ["Cancellation Policy: eligibility"]
    assert result["next_action"] == "Support agent to review and confirm."


def test_run_rejects_missing_context(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / "missing.sqlite3"))
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    Store(tmp_path / "missing.sqlite3").initialize()
    with TestClient(app), pytest.raises(Exception, match="404 Not Found"):
        main.run("REQ-0000", "thread-1", scripted_model())


def test_run_rejects_recommendation_without_fetching_context(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / "skipped.sqlite3"))
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    store = Store(tmp_path / "skipped.sqlite3")
    store.initialize()
    assert store.start_run("REQ-7008")
    with (
        TestClient(app),
        pytest.raises(ValueError, match="did not retrieve request context"),
    ):
        main.run("REQ-7008", "thread-skipped", scripted_model(include_context=False))


@pytest.mark.parametrize(
    "scenario",
    [
        {
            "request_id": "REQ-7001",
            "expected_outcome": "request_information",
            "priority": False,
            "required_text": "confirm which item or order",
        },
        {
            "request_id": "REQ-7002",
            "expected_outcome": "approve",
            "priority": True,
            "required_text": "do not consume or return the item",
        },
    ],
)
def test_context_overrides_hold_ambiguous_and_food_safety_requests(
    tmp_path, monkeypatch, scenario: SafetyScenario
):
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / "safety.sqlite3"))
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    store = Store(tmp_path / "safety.sqlite3")
    store.initialize()
    request_id = scenario["request_id"]
    assert store.start_run(request_id)
    with TestClient(app):
        result = main.run(request_id, "thread-safety", scripted_model("approve"))
    next_action = result["next_action"]
    assert isinstance(next_action, str)
    assert result["outcome"] == scenario["expected_outcome"]
    assert result["priority_human_review"] is scenario["priority"]
    assert scenario["required_text"] in next_action.casefold()


def test_run_rejects_unsupported_action_claim(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / "claim.sqlite3"))
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    store = Store(tmp_path / "claim.sqlite3")
    store.initialize()
    assert store.start_run("REQ-7008")
    with (
        TestClient(app),
        pytest.raises(ValueError, match="unconfirmed customer action"),
    ):
        main.run(
            "REQ-7008",
            "thread-claim",
            scripted_model(rationale="The order has been cancelled."),
        )


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
