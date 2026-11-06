"""Stub models that play out a script, so no test calls a real model."""

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from backend.main import app

api = TestClient(app)


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies, after failing a number of times."""

    failures: int = 0

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, *args, **kwargs):
        if self.failures:
            self.failures -= 1
            raise ConnectionError("The model provider timed out.")
        return super()._generate(*args, **kwargs)


def stub(*replies, failures=0):
    return StubModel(messages=iter(replies), failures=failures)


def calls(*tool_calls):
    """A model reply that calls each of the tools given, with their arguments."""
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": f"call-{number}"}
            for number, (name, args) in enumerate(tool_calls)
        ],
    )


def decision(claim_id, decision, payout):
    return {
        "claim_id": claim_id,
        "decision": decision,
        "payout": payout,
        "reason": "The wording covers it.",
        "policy_section": "Policy wording, section 3, Trip Delay",
    }


def claim(claim_id):
    return api.get(f"/api/claims/{claim_id}").json()


def steps(claim_id):
    return api.get(f"/api/claims/{claim_id}/steps").json()
