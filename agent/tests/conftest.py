from contextlib import nullcontext

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import common
from backend import db
from backend.main import app

DOWN = [RuntimeError("model unavailable")] * 3


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies, or raises a scripted error."""

    seen: list = []

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, *args, **kwargs):
        self.seen.append(messages)
        reply = next(self.messages)
        if isinstance(reply, Exception):
            raise reply
        self.messages = iter([reply, *self.messages])
        return super()._generate(messages, *args, **kwargs)


def stub(*replies):
    return StubModel(messages=iter(replies), seen=[])


def tool_call(name, **args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": name}])


def decision(claim_id="CLM-1001", payout=420.0):
    return tool_call(
        "record_decision",
        claim_id=claim_id,
        decision="approve",
        payout=payout,
        reason="The carrier canceled the flight for a crew problem.",
        policy_section="3. Trip Delay",
    )


def decided(claim_id="CLM-1001"):
    """A claim agent's replies that decide a claim straight away."""
    return [decision(claim_id, 100.0), AIMessage(content=f"Approved {claim_id}.")]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "test.db"))
    monkeypatch.setenv("UNDERCOVER_AGENT", "off")
    monkeypatch.setattr(common, "RETRY_DELAY", 0)
    db.seed()
    client = TestClient(app)
    monkeypatch.setattr(common, "backend", lambda: nullcontext(client))
    return client
