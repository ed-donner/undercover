import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import api
from backend.main import app


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


@pytest.fixture(autouse=True)
def backend(tmp_path, monkeypatch):
    """Point the agent at the backend in-process, on a throwaway database."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    for name in ("DATABASE_URL", "LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY"):
        monkeypatch.delenv(name, raising=False)
    client = TestClient(app)
    monkeypatch.setattr(api, "client", client)
    return client


@pytest.fixture
def script():
    """Build a stub model from steps: a (tool, args) pair, or a final reply."""

    def build(*steps):
        replies = [
            AIMessage(content=step)
            if isinstance(step, str)
            else AIMessage(
                content="",
                tool_calls=[{"name": step[0], "args": step[1], "id": str(i)}],
            )
            for i, step in enumerate(steps)
        ]
        return StubModel(messages=iter(replies))

    return build
