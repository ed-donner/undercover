from contextlib import nullcontext
from itertools import chain

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import harness


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


class Flaky:
    """Replies that fail with an error a number of times before they begin."""

    def __init__(self, replies: tuple[AIMessage, ...], failures: int):
        self.replies = iter(replies)
        self.failures = failures

    def __iter__(self):
        return self

    def __next__(self) -> AIMessage:
        if self.failures:
            self.failures -= 1
            raise RuntimeError("The model timed out")
        return next(self.replies)


class Down:
    def __iter__(self):
        return self

    def __next__(self) -> AIMessage:
        raise RuntimeError("The model is down")


def stub(*replies: AIMessage) -> StubModel:
    return StubModel(messages=iter(replies))


def flaky(*replies: AIMessage, failures: int = 1) -> StubModel:
    return StubModel(messages=Flaky(replies, failures))


def down_after(*replies: AIMessage) -> StubModel:
    return StubModel(messages=chain(replies, Down()))


def call(name: str, **args) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": name}])


@pytest.fixture(autouse=True)
def backend_in_process(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Point the agent at the test backend, without delays between retries."""
    monkeypatch.setattr(harness, "backend", lambda: nullcontext(client))
    monkeypatch.setattr(harness, "RETRY_DELAY", 0)
