from typing import TypedDict

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main
from agent.models import Recommendation
from agent.safety import apply_context_overrides


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
def test_run_returns_structured_recommendation(store, outcome):
    assert store.start_request("REQ-7008")
    result = main.run("REQ-7008", "thread-1", scripted_model(outcome))
    assert result["outcome"] == outcome
    assert result["policy_citations"] == ["Cancellation Policy: eligibility"]
    assert result["next_action"] == "Support agent to review and confirm."


def test_run_rejects_missing_context(store):
    with pytest.raises(Exception, match="404 Not Found"):
        main.run("REQ-0000", "thread-1", scripted_model())


def test_run_rejects_recommendation_without_fetching_context(store):
    assert store.start_request("REQ-7008")
    with pytest.raises(ValueError, match="did not retrieve request context"):
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
            "priority": False,
            "required_text": "",
        },
    ],
)
def test_context_overrides_hold_ambiguous_requests_and_pass_damage_reports(
    store, scenario: SafetyScenario
):
    request_id = scenario["request_id"]
    assert store.start_request(request_id)
    result = main.run(request_id, "thread-safety", scripted_model("approve"))
    next_action = result["next_action"]
    assert isinstance(next_action, str)
    assert result["outcome"] == scenario["expected_outcome"]
    assert result["priority_human_review"] is scenario["priority"]
    assert scenario["required_text"] in next_action.casefold()


def test_food_safety_report_is_held_for_priority_review():
    context = {
        "request": {
            "type": "return_or_refund",
            "customer_message": "The yogurt was warm when it arrived and smells sour.",
            "requested_scope": "item:ITM-1",
            "evidence": [],
        },
        "order": {"items": [{"name": "Chilled yogurt, 500 g"}]},
    }
    recommendation = Recommendation(
        outcome="approve",
        rationale="Reported within the window.",
        policy_citations=[],
        next_action="Review the refund.",
        priority_human_review=False,
    )

    result = apply_context_overrides(context, recommendation)

    assert result.priority_human_review is True
    assert "do not consume or return the item" in result.next_action.casefold()
    assert "Returns Policy: Food safety or allergy concern" in result.policy_citations


def test_run_rejects_unsupported_action_claim(store):
    assert store.start_request("REQ-7008")
    with pytest.raises(ValueError, match="unconfirmed customer action"):
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
