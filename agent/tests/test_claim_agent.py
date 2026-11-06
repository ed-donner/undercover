import json

import httpx
from langchain_core.messages import AIMessage

from agent import claim_agent, common
from agent.tests.stubs import api, calls, claim, decision, steps, stub
from backend.main import INSTRUCTIONS


def work(claim_id, model):
    return claim_agent.start(claim_id) or claim_agent.attempt(claim_id, model)


def approve_and_pay(claim_id, payout):
    return stub(
        calls(("record_decision", decision(claim_id, "approve", payout))),
        calls(("pay_claim", {"claim_id": claim_id, "amount": payout})),
        AIMessage(content="Approved and paid."),
    )


def test_an_approval_within_the_limit_is_decided_paid_and_recorded_step_by_step():
    model = stub(
        calls(
            ("get_claim", {"claim_id": "CLM-1001"}),
            ("get_policy", {"policy_id": "POL-2001"}),
            ("get_customer", {"customer_id": "CUS-3001"}),
            ("read_section", {"document": "policy_wording", "section": 3}),
        ),
        calls(("record_decision", decision("CLM-1001", "approve", 420))),
        calls(("pay_claim", {"claim_id": "CLM-1001", "amount": 420})),
        AIMessage(content="Approved $420.00 for the delay."),
    )
    assert work("CLM-1001", model) == "CLM-1001: approved $420.00 and paid."
    decided = claim("CLM-1001")
    assert decided["status"] == "decided"
    assert decided["reason"] == "The wording covers it."
    assert decided["policy_section"] == "Policy wording, section 3, Trip Delay"
    assert decided["paid_amount"] == 420.0
    recorded = steps("CLM-1001")
    kinds_and_names = [(step["kind"], step["name"]) for step in recorded]
    reads = ["get_claim", "get_policy", "get_customer", "read_section"]
    assert kinds_and_names[:4] == [("tool_call", name) for name in reads]
    assert sorted(kinds_and_names[4:8]) == sorted(
        ("tool_result", name) for name in reads
    )
    assert kinds_and_names[8:] == [
        ("tool_call", "record_decision"),
        ("tool_result", "record_decision"),
        ("tool_call", "pay_claim"),
        ("tool_result", "pay_claim"),
        ("reply", "agent"),
    ]
    assert len({step["thread_id"] for step in recorded}) == 1
    assert json.loads(recorded[0]["content"]) == {"claim_id": "CLM-1001"}
    assert recorded[-1]["content"] == "Approved $420.00 for the delay."


def test_the_backend_refuses_the_agent_a_payment_over_the_limit():
    line = work("CLM-1003", approve_and_pay("CLM-1003", 1500))
    assert line == "CLM-1003: approved $1,500.00, waiting for a handler's sign-off."
    held = claim("CLM-1003")
    assert held["status"] == "waiting_for_sign_off"
    assert held["paid_amount"] is None
    payment = steps("CLM-1003")[-2]
    assert payment["name"] == "pay_claim"
    assert "waits for a handler's sign-off" in payment["content"]


def test_a_decline_and_a_referral_are_decided_and_unpaid():
    for claim_id, choice, line in [
        ("CLM-1013", "decline", "CLM-1013: declined."),
        ("CLM-1007", "refer", "CLM-1007: referred."),
    ]:
        model = stub(
            calls(("record_decision", decision(claim_id, choice, 0))),
            AIMessage(content="Done."),
        )
        assert work(claim_id, model) == line
        assert claim(claim_id)["status"] == "decided"
        assert claim(claim_id)["paid_amount"] is None


def test_a_claim_that_isnt_waiting_isnt_worked():
    api.post("/api/claims/CLM-1001/start")
    line = work("CLM-1001", stub(AIMessage(content="Done.")))
    assert line == "Claim CLM-1001 can't be started: it is in progress."
    assert steps("CLM-1001") == []


def test_a_failed_claim_goes_back_in_the_queue_then_is_left_for_a_handler():
    line = work("CLM-1002", stub(failures=99))
    assert line == (
        "CLM-1002 failed: ConnectionError: The model provider timed out."
        " It's back in the queue for one more try."
    )
    assert (claim("CLM-1002")["status"], claim("CLM-1002")["attempts"]) == (
        "waiting",
        1,
    )
    failure = steps("CLM-1002")[-1]
    assert failure["kind"] == "failure"
    assert failure["content"].startswith("This attempt failed: ConnectionError")
    second = work("CLM-1002", stub(failures=99))
    assert second.endswith("It's left for a handler.")
    assert claim("CLM-1002")["status"] == "left_for_handler"
    assert len({step["thread_id"] for step in steps("CLM-1002")}) == 2


def test_a_model_call_that_fails_is_retried():
    model = approve_and_pay("CLM-1001", 420)
    model.failures = 2
    assert work("CLM-1001", model) == "CLM-1001: approved $420.00 and paid."
    assert claim("CLM-1001")["attempts"] == 0


def test_a_tool_whose_call_to_the_backend_fails_is_retried(monkeypatch):
    failed = []
    real_call = common.call

    def flaky(method, url, *args, **kwargs):
        if url.endswith("/decision") and not failed:
            failed.append(url)
            raise httpx.ConnectError("The backend didn't answer.")
        return real_call(method, url, *args, **kwargs)

    monkeypatch.setattr(common, "call", flaky)
    assert work("CLM-1001", approve_and_pay("CLM-1001", 420)).endswith("and paid.")
    assert failed


def test_an_agent_going_round_in_circles_stops_at_the_model_call_limit():
    going_round = stub(
        *[calls(("get_claim", {"claim_id": "CLM-1004"})) for _ in range(40)]
    )
    line = work("CLM-1004", going_round)
    assert line.startswith("CLM-1004 failed: ModelCallLimitExceededError")
    calls_made = [step for step in steps("CLM-1004") if step["kind"] == "tool_call"]
    assert len(calls_made) == claim_agent.MODEL_CALLS
    assert claim("CLM-1004")["status"] == "waiting"


def test_an_agent_that_forgets_to_pay_is_reminded():
    model = stub(
        calls(("record_decision", decision("CLM-1001", "approve", 420))),
        AIMessage(content="Approved."),
        calls(("pay_claim", {"claim_id": "CLM-1001", "amount": 420})),
        AIMessage(content="Paid."),
    )
    assert work("CLM-1001", model) == "CLM-1001: approved $420.00 and paid."
    reminder = next(step for step in steps("CLM-1001") if step["kind"] == "reminder")
    assert reminder["content"] == (
        "You approved CLM-1001 for $420.00 but haven't paid it. Pay it before you"
        " finish."
    )


def test_an_agent_that_stops_without_deciding_is_reminded_twice_then_released():
    model = stub(*[AIMessage(content="Done.") for _ in range(3)])
    line = work("CLM-1005", model)
    assert line == (
        "CLM-1005 failed: the agent stopped without recording a decision."
        " It's back in the queue for one more try."
    )
    kinds = [step["kind"] for step in steps("CLM-1005")]
    assert kinds == ["reply", "reminder", "reply", "reminder", "reply", "failure"]


def test_an_approval_left_unpaid_is_left_for_a_handler():
    model = stub(
        calls(("record_decision", decision("CLM-1001", "approve", 420))),
        *[AIMessage(content="Approved.") for _ in range(3)],
    )
    line = work("CLM-1001", model)
    assert line == (
        "CLM-1001 failed: the agent approved $420.00 but didn't pay it."
        " It's left for a handler."
    )
    assert claim("CLM-1001")["decision"] == "approve"


def test_the_instructions_come_from_the_backend(monkeypatch):
    prompts = []

    def create_agent(*args, system_prompt, **kwargs):
        prompts.append(system_prompt)
        return real_create_agent(*args, system_prompt=system_prompt, **kwargs)

    real_create_agent = claim_agent.create_agent
    monkeypatch.setattr(claim_agent, "create_agent", create_agent)
    work("CLM-1013", stub(AIMessage(content="Done.")))
    assert prompts == [(INSTRUCTIONS / "claim.md").read_text(encoding="utf-8")]


def test_the_agent_looks_up_sections_and_its_steps_show_what_it_read():
    api.post("/api/claims/CLM-1001/start")
    model = stub(
        calls(("search_documents", {"query": "wild animals"})),
        calls(("read_section", {"document": "claims_manual", "section": 7})),
        AIMessage(content="Read the note on wild animals."),
        *[AIMessage(content="Done.") for _ in range(common.MOST_REMINDERS)],
    )
    claim_agent.run("CLM-1001", "thread-1", model)
    recorded = [step for step in steps("CLM-1001") if step["kind"] != "reminder"]
    assert [(step["kind"], step["name"]) for step in recorded[:5]] == [
        ("tool_call", "search_documents"),
        ("tool_result", "search_documents"),
        ("tool_call", "read_section"),
        ("tool_result", "read_section"),
        ("reply", "agent"),
    ]
    assert json.loads(recorded[1]["content"])[0]["title"] == "Interpretation notes"
    assert json.loads(recorded[2]["content"]) == {
        "document": "claims_manual",
        "section": 7,
    }
    assert "**Wild animals.**" in json.loads(recorded[3]["content"])["text"]


def test_the_agent_looks_things_up_instead_of_reading_whole_documents():
    assert [tool.name for tool in claim_agent.TOOLS] == [
        "get_claim",
        "get_policy",
        "get_customer",
        "list_sections",
        "search_documents",
        "read_section",
        "record_decision",
        "pay_claim",
    ]
    contents = json.loads(claim_agent.list_sections.invoke({}))
    assert {"document": "claims_manual", "section": 9, "title": "Repeat claims"} in (
        contents
    )


def test_the_model_sees_no_personal_details():
    customer = json.loads(claim_agent.get_customer.invoke({"customer_id": "CUS-3001"}))
    assert set(customer) == {"name", "customer_since", "previous_claims"}
    assert customer["name"] == "Maya Patel"


def test_tools_hand_refusals_back_to_the_model():
    assert "There is no customer" in claim_agent.get_customer.invoke(
        {"customer_id": "X"}
    )
    refusal = claim_agent.pay_claim.invoke({"claim_id": "CLM-1001", "amount": 420})
    assert "only an approved claim" in refusal


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    default = common.model()
    assert default.model_name == "deepseek/deepseek-v4.1-flash"
    assert default.reasoning_effort == "low"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert common.model().model_name == "openrouter/free"
