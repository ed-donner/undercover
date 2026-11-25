import inspect

import httpx
import pytest
from langchain_core.messages import AIMessage

from agent import claim, common
from agent.tests.conftest import DOWN, decided, decision, stub, tool_call

READS = [
    tool_call("get_claim", claim_id="CLM-1001"),
    tool_call("get_policy", policy_id="POL-2001"),
    tool_call("get_claim_history", customer_id="CUS-3001"),
    tool_call("list_sections", document="policy-wording"),
    tool_call("read_section", document="policy-wording", number="3"),
    tool_call("read_section", document="claims-manual", number="9"),
]


def status(client, claim_id="CLM-1001"):
    return client.get(f"/api/claims/{claim_id}").json()["status"]


def steps(client, kind=None):
    found = client.get("/api/claims/CLM-1001/steps").json()
    return [s["content"] for s in found if kind in (None, s["kind"])]


def test_full_claim(client):
    llm = stub(
        *READS,
        decision(),
        tool_call("pay_claim", claim_id="CLM-1001", amount=420.0),
        AIMessage(content="Approved and paid $420.00."),
    )
    assert claim.work_claim("CLM-1001", llm) == "CLM-1001: approve, $420.00, paid"
    assert client.get("/api/claims/CLM-1001").json()["paid_amount"] == 420.0
    calls = [s.split("(")[0] for s in steps(client, "tool_call")]
    assert calls == [
        "get_claim",
        "get_policy",
        "get_claim_history",
        "list_sections",
        "read_section",
        "read_section",
        "record_decision",
        "pay_claim",
    ]
    assert steps(client, "read") == [
        "Policy wording, 3. Trip Delay",
        "Claims manual, 9. Repeat claims",
    ]
    assert steps(client, "tool_result")[0].endswith("...")
    assert steps(client)[-1] == "Approved and paid $420.00."


def test_a_refused_section_is_not_a_read(client):
    llm = stub(
        tool_call("read_section", document="claims-manual", number="99"),
        *decided(),
    )
    claim.work_claim("CLM-1001", llm)
    assert steps(client, "read") == []
    assert "read_section: Refused: The claims manual has no section 99" in steps(
        client, "tool_result"
    )


def test_a_failure_puts_the_claim_back(client):
    llm = stub(tool_call("get_claim", claim_id="CLM-1001"), *DOWN)
    assert claim.work_claim("CLM-1001", llm) == (
        "CLM-1001: failed (the agent stopped with an error: model unavailable), "
        "back in the queue"
    )
    assert status(client) == "waiting"
    assert steps(client, "error") == [
        "The agent stopped with an error: model unavailable"
    ]


def test_a_second_failure_leaves_the_claim_for_a_handler(client):
    claim.work_claim("CLM-1001", stub(*DOWN))
    line = claim.work_claim("CLM-1001", stub(*DOWN))
    assert line.endswith("left for a handler")
    assert status(client) == "needs_handler"
    assert "Attempt 2" in steps(client, "attempt")


def test_no_decision_puts_the_claim_back(client):
    line = claim.work_claim("CLM-1001", stub(AIMessage(content="Decline, $0.")))
    assert line == (
        "CLM-1001: failed (the agent finished without recording a decision), "
        "back in the queue"
    )
    assert status(client) == "waiting"


def test_the_call_limit_ends_a_claim(client, monkeypatch):
    monkeypatch.setattr(claim, "CALL_LIMIT", 2)
    loop = [tool_call("get_claim", claim_id="CLM-1001")] * 3
    line = claim.work_claim("CLM-1001", stub(*loop))
    assert line.endswith("back in the queue")
    assert len(steps(client, "tool_call")) == 2


def test_a_transient_error_is_retried(client):
    llm = stub(RuntimeError("timed out"), *decided())
    assert claim.work_claim("CLM-1001", llm) == (
        "CLM-1001: approve, $100.00, not paid yet"
    )
    assert steps(client, "error") == []


def test_a_large_payout_waits_for_signoff(client):
    llm = stub(
        decision(payout=1150.0),
        tool_call("pay_claim", claim_id="CLM-1001", amount=1150.0),
        AIMessage(content="Approved; the payment waits for sign-off."),
    )
    assert claim.work_claim("CLM-1001", llm) == (
        "CLM-1001: approve, $1,150.00, waiting for a handler's sign-off"
    )
    assert client.get("/api/claims/CLM-1001").json()["paid_at"] is None
    assert steps(client, "tool_result")[-1] == (
        "pay_claim: Refused: The payout is over $1,000.00, so the payment waits "
        "for a handler's sign-off"
    )


def test_a_decline_is_reported_without_a_payout(client):
    decline = tool_call(
        "record_decision",
        claim_id="CLM-1001",
        decision="decline",
        payout=0,
        reason="Not covered.",
        policy_section="9. General exclusions",
    )
    line = claim.work_claim("CLM-1001", stub(decline, AIMessage(content="Declined.")))
    assert line == "CLM-1001: decline"


def test_an_unpaid_approval(client):
    llm = stub(decision(), AIMessage(content="Approved."))
    assert claim.work_claim("CLM-1001", llm) == (
        "CLM-1001: approve, $420.00, not paid yet"
    )


def test_a_claim_not_waiting_is_refused(client):
    client.post("/api/claims/CLM-1001/start")
    llm = stub()
    assert claim.work_claim("CLM-1001", llm) == (
        "Refused: CLM-1001 is in_progress, not waiting"
    )
    assert llm.seen == []


def test_instructions_come_from_the_backend(client, monkeypatch, tmp_path):
    (tmp_path / "claim.md").write_text("Served claim instructions.")
    (tmp_path / "queue.md").write_text("Served queue instructions.")
    monkeypatch.setattr("backend.main.INSTRUCTIONS", tmp_path)
    llm = stub(*decided())
    claim.work_claim("CLM-1001", llm)
    assert llm.seen[0][0].content == "Served claim instructions."


def test_tools_only_call_the_backend():
    assert [t.name for t in claim.TOOLS] == [
        "get_claim",
        "get_policy",
        "get_claim_history",
        "list_sections",
        "read_section",
        "record_decision",
        "pay_claim",
    ]
    for module in [claim, common]:
        source = inspect.getsource(module)
        assert "data/" not in source
        assert "open(" not in source


def test_server_errors_raise(monkeypatch):
    transport = httpx.MockTransport(lambda _: httpx.Response(500))
    monkeypatch.setattr(
        common,
        "backend",
        lambda: httpx.Client(transport=transport, base_url="http://x"),
    )
    with pytest.raises(httpx.HTTPStatusError):
        common.call("GET", "/api/policy-wording")


def test_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    default = common.model()
    assert default.model_name == "deepseek/deepseek-v4.1-flash"
    assert default.extra_body == {"reasoning": {"effort": "low"}}
    assert default.request_timeout == 60
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert common.model().model_name == "openrouter/free"
    assert common.model().extra_body is None
