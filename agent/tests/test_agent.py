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


def scripted_model(outcome="approve"):
    replies = []
    replies.extend(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "get_request_context", "args": {}, "id": "context"}
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "record_progress",
                        "args": {"stage": "checking_policy"},
                        "id": "progress",
                    }
                ],
            ),
        ]
    )
    replies.append(
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "Recommendation",
                    "args": {
                        "outcome": outcome,
                        "rationale": "The request meets the cited sample policy.",
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
    assert store.start_run("REQ-7001")
    with TestClient(app):
        result = main.run("REQ-7001", "thread-1", scripted_model(outcome))
    assert result["outcome"] == outcome
    assert result["policy_citations"] == ["Cancellation Policy: eligibility"]
    assert result["next_action"] == "Support agent to review and confirm."


def test_run_rejects_missing_context(tmp_path, monkeypatch):
    monkeypatch.setenv("SHOPPIE_DATABASE_PATH", str(tmp_path / "missing.sqlite3"))
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    Store(tmp_path / "missing.sqlite3").initialize()
    with TestClient(app), pytest.raises(Exception, match="404 Not Found"):
        main.run("REQ-0000", "thread-1", scripted_model())


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
