"""Stub models that give scripted replies in place of a real model."""

from typing import Any

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

CITATION = "Shoppie Cancellation Policy: 2. Customer-requested cancellations"


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


class FlakyModel(StubModel):
    """A stub model whose first call fails like a provider timeout."""

    failures: int = 1

    def _generate(self, *args: Any, **kwargs: Any):
        if self.failures:
            self.failures -= 1
            raise ConnectionError("provider timeout")
        return super()._generate(*args, **kwargs)


def call(name: str, args: dict[str, Any] | None = None) -> AIMessage:
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args or {}, "id": name}]
    )


def request_replies(
    outcome="approve",
    rationale="The request meets the cited sample policy.",
    include_context=True,
) -> list[AIMessage]:
    replies = [call("get_request_context")] if include_context else []
    return [
        *replies,
        call("record_progress", {"stage": "reading_request"}),
        call("list_policy_sections"),
        call(
            "read_policy_section",
            {"policy": "cancellation", "section": "2-customer-requested-cancellations"},
        ),
        call("read_policy_section", {"policy": "cancellation", "section": "nope"}),
        call("record_progress", {"stage": "checking_policy"}),
        call(
            "Recommendation",
            {
                "outcome": outcome,
                "rationale": rationale,
                "policy_citations": [CITATION],
                "next_action": "Support agent to review and confirm.",
                "priority_human_review": False,
            },
        ),
    ]


def scripted_model(**kwargs: Any) -> StubModel:
    return StubModel(messages=iter(request_replies(**kwargs)))
