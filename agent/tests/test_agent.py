from contextlib import nullcontext
from typing import Any, TypedDict

import pytest
from fastapi.testclient import TestClient

from agent import main, service
from agent.models import Recommendation
from agent.safety import apply_context_overrides
from agent.tests.stubs import (
    CITATION,
    FlakyModel,
    StubModel,
    call,
    request_replies,
    scripted_model,
)
from backend import main as backend_main


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
        "preparing_recommendation",
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


def test_request_agent_uses_calculate_refund_tool(store):
    assert store.start_request("REQ-7002")
    replies = [
        call("get_request_context"),
        call(
            "calculate_refund",
            {
                "reason": "damaged_or_defective",
                "lines": [{"item_id": "ITM-10002-1", "quantity": 1}],
            },
        ),
        call(
            "calculate_refund",
            {
                "reason": "damaged_or_defective",
                "lines": [{"item_id": "ITM-NOPE", "quantity": 1}],
            },
        ),
        *request_replies(include_context=False),
    ]
    result = main.run_request(
        "REQ-7002", "thread-refund", StubModel(messages=iter(replies))
    )
    steps = store.get_request("REQ-7002")["steps"]

    assert result["outcome"] == "approve"
    assert any(
        step["stage"] == "calculated_refund" and "₹90.00" in step["message"]
        for step in steps
    )


def test_trace_context_attaches_langfuse_session_only_when_keys_are_set(monkeypatch):
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    _, without_keys = main.trace_context("REQ-7002", "thread-1")
    assert "callbacks" not in without_keys

    sessions: list[str | None] = []
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setattr(main, "CallbackHandler", lambda: "stub-callback")

    def fake_propagate(*, session_id: str | None = None, **kwargs):
        sessions.append(session_id)
        return nullcontext()

    monkeypatch.setattr(main, "propagate_attributes", fake_propagate)
    _, with_keys = main.trace_context("REQ-7002", "request-REQ-7002-attempt-1")
    assert with_keys.get("callbacks") == ["stub-callback"]
    assert with_keys.get("metadata") == {
        "langfuse_session_id": "request-REQ-7002-attempt-1"
    }
    assert sessions == ["request-REQ-7002-attempt-1"]


def test_graph_pauses_at_approval_and_resumes_to_complete_once(store):
    assert store.start_request("REQ-7008") == 1
    thread_id = "request-REQ-7008-attempt-1"
    recommendation = main.run_request("REQ-7008", thread_id, scripted_model())
    graph = main.build_request_graph("REQ-7008", scripted_model())
    _, config = main.trace_context("REQ-7008", thread_id)
    paused = graph.get_state(config)
    held = store.get_request("REQ-7008")

    assert recommendation["outcome"] == "approve"
    assert paused.next == ("approval",)
    assert paused.interrupts[0].value["request_id"] == "REQ-7008"
    assert held["status"] == "waiting_for_agent_review"

    review = {
        "outcome": "approve",
        "notes": "Confirmed pre-dispatch cancellation.",
        "reviewed_by": "Priya Nair",
        "reviewed_at": "2026-03-02T14:25:00+00:00",
    }
    main.resume_request_thread("REQ-7008", thread_id, review, scripted_model())
    decided = store.get_request("REQ-7008")

    assert decided["status"] == "decided"
    assert decided["review"] == review
    assert decided["steps"][-1]["stage"] == "completed"
    assert "Priya Nair" in decided["steps"][-1]["message"]

    main.resume_request_thread("REQ-7008", thread_id, review, scripted_model())
    after_repeat = store.get_request("REQ-7008")
    completed_steps = [
        step for step in after_repeat["steps"] if step["stage"] == "completed"
    ]
    assert len(completed_steps) == 1


def test_runaway_loop_stops_after_30_model_calls(store):
    assert store.start_request("REQ-7008") == 1
    endless = StubModel(messages=iter(call("list_policy_sections") for _ in range(35)))
    with pytest.raises(RuntimeError, match="exceeded 30 model calls"):
        main.run_request("REQ-7008", "thread-runaway", endless)


class InterruptedModel(StubModel):
    """A stub model that stops with KeyboardInterrupt after its scripted replies."""

    def _generate(self, *args: Any, **kwargs: Any):
        try:
            return super()._generate(*args, **kwargs)
        except StopIteration as stop:
            raise KeyboardInterrupt("process stopped mid-request") from stop


def test_stopped_request_resumes_from_checkpoint_on_same_attempt(store):
    early_replies = [
        call("get_request_context"),
        call("record_progress", {"stage": "reading_request"}),
    ]
    interrupted = InterruptedModel(messages=iter(early_replies))
    with pytest.raises(KeyboardInterrupt, match="process stopped mid-request"):
        main.work_request("REQ-7008", interrupted)

    mid_flight = store.get_request("REQ-7008")
    assert mid_flight["status"] == "in_progress"
    assert mid_flight["attempts"] == 0
    assert [step["stage"] for step in mid_flight["steps"]] == [
        "started",
        "reading_request",
    ]

    remaining = StubModel(messages=iter(request_replies(include_context=False)[1:]))
    resumed = main.work_request("REQ-7008", remaining)
    finished = store.get_request("REQ-7008")
    stages = [step["stage"] for step in finished["steps"]]

    assert resumed["status"] == "done"
    assert finished["status"] == "waiting_for_agent_review"
    assert finished["attempts"] == 0
    assert finished["recommendation"]["outcome"] == "approve"
    assert stages == [
        "started",
        "reading_request",
        "read_section",
        "checking_policy",
        "preparing_recommendation",
    ]


def test_agent_service_resumes_signed_off_request_and_runs_queue(
    api, store, monkeypatch
):
    monkeypatch.setattr(main, "model", scripted_model)
    monkeypatch.setattr(backend_main, "run_in_background", lambda *args: None)
    main.work_request("REQ-7008", scripted_model())

    with TestClient(service.app) as agent_client:
        assert agent_client.get("/health").json() == {"status": "ok"}
        assert agent_client.post("/requests/REQ-0000/resume").status_code == 404
        assert agent_client.post("/requests/REQ-7008/resume").status_code == 409

        monkeypatch.setattr(
            backend_main,
            "notify_agent_resume",
            lambda rid: agent_client.post(f"/requests/{rid}/resume"),
        )
        reviewed = api.post(
            "/api/requests/REQ-7008/review",
            json={
                "outcome": "approve",
                "notes": "Confirmed.",
                "reviewed_by": "Priya Nair",
            },
        )
        assert reviewed.status_code == 200
        decided = store.get_request("REQ-7008")
        assert decided["status"] == "decided"
        assert decided["review"]["reviewed_by"] == "Priya Nair"

        started_run = agent_client.post("/runs", json={"cap": 2})
        assert started_run.status_code == 200
        assert agent_client.post("/runs", json={"cap": 2}).status_code == 409
