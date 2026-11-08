from typing import TypedDict

import pytest

from agent import main
from agent.models import Recommendation
from agent.safety import apply_context_overrides
from agent.tests.stubs import CITATION, FlakyModel, request_replies, scripted_model


class SafetyScenario(TypedDict):
    """Expected behavior for a synthetic request edge case."""

    request_id: str
    expected_outcome: str
    priority: bool
    required_text: str


@pytest.mark.parametrize("outcome", ["approve", "decline", "request_information"])
def test_request_agent_reads_sections_and_returns_a_recommendation(store, outcome):
    assert store.start_request("REQ-7008")
    result = main.run_request("REQ-7008", "thread-1", scripted_model(outcome=outcome))
    steps = store.get_request("REQ-7008")["steps"]

    assert result["outcome"] == outcome
    assert result["policy_citations"] == [CITATION]
    read = [step["message"] for step in steps if step["stage"] == "read_section"]
    assert read == [
        "Read Shoppie Cancellation Policy, 2. Customer-requested cancellations."
    ]
    assert [step["stage"] for step in steps] == [
        "started",
        "reading_request",
        "read_section",
        "checking_policy",
    ]


def test_request_agent_rejects_an_unknown_request(store):
    with pytest.raises(Exception, match="404 Not Found"):
        main.run_request("REQ-0000", "thread-1", scripted_model())


def test_request_agent_rejects_a_recommendation_without_context(store):
    assert store.start_request("REQ-7008")
    with pytest.raises(ValueError, match="did not retrieve request context"):
        main.run_request(
            "REQ-7008", "thread-skipped", scripted_model(include_context=False)
        )


def test_request_agent_retries_a_model_error(store, monkeypatch):
    monkeypatch.setattr(main, "RETRY_DELAY", 0)
    flaky = FlakyModel(messages=iter(request_replies()))
    result = main.work_request("REQ-7008", flaky)
    request = store.get_request("REQ-7008")
    assert result["status"] == "done"
    assert flaky.failures == 0
    assert request["attempts"] == 0
    assert request["recommendation"]["outcome"] == "approve"


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
    result = main.run_request(request_id, "thread-safety", scripted_model())
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


def test_request_agent_rejects_an_unsupported_action_claim(store):
    assert store.start_request("REQ-7008")
    with pytest.raises(ValueError, match="unconfirmed customer action"):
        main.run_request(
            "REQ-7008",
            "thread-claim",
            scripted_model(rationale="The order has been cancelled."),
        )


def test_work_request_stores_one_recommendation_and_reports_a_line(store):
    result = main.work_request("REQ-7008", scripted_model(outcome="decline"))
    request = store.get_request("REQ-7008")

    assert result["status"] == "done"
    assert result["line"].startswith("REQ-7008: decline, waiting for support review.")
    assert request["status"] == "waiting_for_agent_review"
    assert request["recommendation"]["outcome"] == "decline"
    assert main.work_request("REQ-7008", scripted_model())["status"] == "skipped"
    assert store.get_request("REQ-7008")["recommendation"]["outcome"] == "decline"


def test_work_request_returns_a_failure_to_the_queue_then_to_support(store):
    claim = {"rationale": "The order has been cancelled."}
    first = main.work_request("REQ-7008", scripted_model(**claim))
    after_first = store.get_request("REQ-7008")
    second = main.work_request("REQ-7008", scripted_model(**claim))
    after_second = store.get_request("REQ-7008")

    assert first["status"] == "waiting"
    assert "attempt 1, back in the queue" in first["line"]
    assert after_first["status"] == "waiting"
    assert second["status"] == "left_for_support"
    assert "left for a support agent" in second["line"]
    assert after_second["status"] == "waiting_for_agent_review"
    assert after_second["recommendation"] is None


def test_work_request_skips_an_unknown_request(store):
    result = main.work_request("REQ-0000", scripted_model())
    assert result == {
        "request_id": "REQ-0000",
        "status": "skipped",
        "line": "REQ-0000: not a waiting request, so not worked.",
    }


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    default = main.model()
    assert default.model_name == "deepseek/deepseek-v4.1-flash"
    assert default.reasoning_effort == "low"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    override = main.model()
    assert override.model_name == "openrouter/free"
    assert override.reasoning_effort is None
