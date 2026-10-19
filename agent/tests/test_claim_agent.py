import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from agent import claim_agent, harness
from agent.tests.conftest import call, down_after, flaky, stub

CLAIM = "CLM-1001"


def decision(outcome: str, payout: float, claim_id: str = CLAIM) -> AIMessage:
    return call(
        "record_decision",
        claim_id=claim_id,
        decision=outcome,
        payout=payout,
        explanation="The delay is covered.",
        policy_section="Section 3, Trip Delay",
    )


def start(client: TestClient, claim_id: str = CLAIM) -> None:
    assert client.post(f"/api/claims/{claim_id}/start").status_code == 200


def get(client: TestClient, path: str = ""):
    return client.get(f"/api/claims/{CLAIM}{path}").json()


def test_the_claim_agent_has_seven_tools_and_no_way_to_the_answer_key():
    names = {tool.name for tool in claim_agent.TOOLS}
    assert names == {
        "get_claim",
        "get_policy",
        "get_customer",
        "list_sections",
        "read_section",
        "record_decision",
        "pay_claim",
    }


def test_tools_read_through_the_backend():
    assert "Maya Patel" in claim_agent.get_customer.invoke({"customer_id": "CUS-3001"})
    assert "premium" in claim_agent.get_policy.invoke({"policy_id": "POL-2001"})
    assert "My flight home" in claim_agent.get_claim.invoke({"claim_id": CLAIM})
    sections = claim_agent.list_sections.invoke({"document": "manual"})
    assert "9. Repeat claims" in sections.splitlines()
    text = claim_agent.read_section.invoke({"document": "manual", "section": 9})
    assert text.startswith("## 9. Repeat claims")


def test_tools_return_errors_to_the_model():
    assert claim_agent.get_claim.invoke({"claim_id": "CLM-9999"}).startswith(
        "Error 404"
    )
    section = {"document": "wording", "section": 99}
    assert claim_agent.read_section.invoke(section).startswith("Error 404")


def test_the_agent_reads_decides_and_pays_a_small_claim(client: TestClient):
    start(client)
    replies = [
        call("get_claim", claim_id=CLAIM),
        call("get_policy", policy_id="POL-2001"),
        call("get_customer", customer_id="CUS-3001"),
        call("read_section", document="manual", section=9),
        call("read_section", document="wording", section=3),
        decision("approve", 200),
        call("pay_claim", claim_id=CLAIM, amount=200),
        AIMessage(content="Approved $200.00 for the delay."),
    ]
    reply = claim_agent.claim_run(CLAIM, "thread-1", stub(*replies))
    assert reply == "Approved $200.00 for the delay."
    claim = get(client)
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 200
    steps = get(client, "/steps")
    kinds = [step["kind"] for step in steps]
    assert kinds.count("tool_call") == kinds.count("tool_result") == 7
    assert kinds[-1] == "message"
    assert steps[0]["text"] == "get_claim({'claim_id': 'CLM-1001'})"
    reads = [step["text"] for step in steps if step["kind"] == "read"]
    assert reads == [
        "Claims manual, 9. Repeat claims",
        "Policy wording, 3. Trip Delay",
    ]


def test_a_refused_read_is_not_recorded_as_read(client: TestClient):
    start(client)
    replies = [
        call("read_section", document="manual", section=99),
        AIMessage(content="There is no such section."),
    ]
    claim_agent.claim_run(CLAIM, "thread-2", stub(*replies))
    assert "read" not in {step["kind"] for step in get(client, "/steps")}


def test_a_large_payment_is_held(client: TestClient):
    start(client)
    replies = [
        decision("approve", 1250),
        call("pay_claim", claim_id=CLAIM, amount=1250),
        AIMessage(content="Approved $1,250.00. It waits for sign-off."),
    ]
    claim_agent.claim_run(CLAIM, "thread-3", stub(*replies))
    claim = get(client)
    assert claim["status"] == "waiting_for_sign_off"
    assert claim["payment"] is None
    assert get(client, "/steps")[3]["text"].startswith("pay_claim: Error 409")


def test_an_error_is_recorded_and_raised(client: TestClient):
    start(client)
    with pytest.raises(RuntimeError, match="The model is down"):
        claim_agent.claim_run(CLAIM, "thread-4", down_after())
    last = get(client, "/steps")[-1]
    assert (last["kind"], last["text"]) == ("error", "RuntimeError: The model is down")


def test_a_model_that_fails_once_is_retried(client: TestClient):
    start(client)
    replies = [decision("decline", 0), AIMessage(content="Declined.")]
    claim_agent.claim_run(CLAIM, "thread-5", flaky(*replies, failures=2))
    assert get(client)["status"] == "decided"


def test_a_model_that_keeps_failing_gives_up(client: TestClient):
    start(client)
    with pytest.raises(RuntimeError, match="timed out"):
        claim_agent.claim_run(CLAIM, "thread-6", flaky(failures=5))


def test_work_reports_a_decision_from_the_record(client: TestClient):
    start(client)
    replies = [decision("approve", 200), AIMessage(content="Approved $999.")]
    line = claim_agent.work(CLAIM, "thread-7", stub(*replies))
    assert line == "CLM-1001: approved $200.00, paid."
    assert get(client)["payment"]["amount"] == 200


def test_work_reports_other_outcomes(client: TestClient):
    start(client)
    replies = [decision("approve", 1250), AIMessage(content="Done.")]
    line = claim_agent.work(CLAIM, "thread-8", stub(*replies))
    assert line == "CLM-1001: approved $1,250.00, waiting for sign-off."
    start(client, "CLM-1002")
    declined = decision("decline", 0, "CLM-1002")
    assert claim_agent.work("CLM-1002", "t", stub(declined)) == "CLM-1002: declined."
    start(client, "CLM-1003")
    referred = decision("refer", 0, "CLM-1003")
    assert claim_agent.work("CLM-1003", "t", stub(referred)) == "CLM-1003: referred."


def test_a_failed_claim_goes_back_and_the_second_failure_leaves_it(
    client: TestClient,
):
    start(client)
    first = claim_agent.work(CLAIM, "thread-9", down_after())
    assert (
        first
        == "CLM-1001: failed (RuntimeError: The model is down), back in the queue."
    )
    assert get(client)["status"] == "waiting"
    start(client)
    second = claim_agent.work(CLAIM, "thread-9", down_after())
    assert second.endswith("left for a handler.")
    assert get(client)["status"] == "needs_handler"
    kinds = [step["kind"] for step in get(client, "/steps")]
    assert kinds == ["error", "error", "error", "error"]


def test_a_claim_with_no_decision_is_a_failure(client: TestClient):
    start(client)
    line = claim_agent.work(CLAIM, "thread-10", stub(AIMessage(content="Done.")))
    assert "the agent finished without a decision" in line
    assert get(client)["status"] == "waiting"


def test_a_decided_claim_is_not_reset_and_is_paid_once(client: TestClient):
    start(client)
    line = claim_agent.work(CLAIM, "thread-11", down_after(decision("approve", 200)))
    assert line == "CLM-1001: approved $200.00, paid."
    claim = get(client)
    assert (claim["status"], claim["payment"]["amount"]) == ("decided", 200)
    assert claim_agent.work(CLAIM, "thread-11", stub()).endswith("paid.")
    assert get(client)["decision"]["payout"] == 200


def test_the_call_limit_ends_an_agent_that_never_decides(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    start(client)
    monkeypatch.setattr(claim_agent, "CALL_LIMIT", 2)
    loop = [call("get_claim", claim_id=CLAIM)] * 5
    line = claim_agent.work(CLAIM, "thread-12", stub(*loop))
    assert "finished without a decision" in line


def test_the_default_model(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    default = harness.model()
    assert default.model_name == "deepseek/deepseek-v4.1-flash"
    assert default.reasoning_effort == "low"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    free = harness.model()
    assert free.model_name == "openrouter/free"
    assert free.reasoning_effort is None
