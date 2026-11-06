import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import __main__ as cli
from agent import main
from backend.main import INSTRUCTIONS, app

api = TestClient(app)


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


@pytest.fixture(autouse=True)
def backend(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))


def stub(*replies):
    return StubModel(messages=iter(replies))


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
        "policy_section": "Section 3, Trip Delay",
    }


def claim(claim_id):
    return api.get(f"/api/claims/{claim_id}").json()


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
    assert main.run("CLM-1001", "thread-1", model) == "Approved $420.00 for the delay."
    decided = claim("CLM-1001")
    assert decided["status"] == "decided"
    assert decided["decision"] == "approve"
    assert decided["reason"] == "The wording covers it."
    assert decided["policy_section"] == "Section 3, Trip Delay"
    assert decided["paid_amount"] == 420.0
    steps = api.get("/api/claims/CLM-1001/steps").json()
    kinds_and_names = [(step["kind"], step["name"]) for step in steps]
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
    assert {step["thread_id"] for step in steps} == {"thread-1"}
    assert json.loads(steps[0]["content"]) == {"claim_id": "CLM-1001"}
    assert steps[-1]["content"] == "Approved $420.00 for the delay."


def test_the_backend_refuses_the_agent_a_payment_over_the_limit():
    model = stub(
        calls(("record_decision", decision("CLM-1003", "approve", 1500))),
        calls(("pay_claim", {"claim_id": "CLM-1003", "amount": 1500})),
        AIMessage(content="Approved $1,500.00, which waits for a handler's sign-off."),
    )
    main.run("CLM-1003", "thread-1", model)
    held = claim("CLM-1003")
    assert held["status"] == "waiting_for_sign_off"
    assert held["paid_amount"] is None
    payment = api.get("/api/claims/CLM-1003/steps").json()[-2]
    assert payment["name"] == "pay_claim"
    assert "waits for a handler's sign-off" in payment["content"]


def test_a_decline_is_decided_and_unpaid():
    model = stub(
        calls(("record_decision", decision("CLM-1013", "decline", 0))),
        AIMessage(content="Declined."),
    )
    main.run("CLM-1013", "thread-1", model)
    assert claim("CLM-1013")["status"] == "decided"
    assert claim("CLM-1013")["paid_amount"] is None


def test_a_claim_that_isnt_waiting_cant_be_run():
    api.post("/api/claims/CLM-1001/start")
    with pytest.raises(Exception, match="409 Conflict"):
        main.run("CLM-1001", "thread-1", stub(AIMessage(content="Done.")))


def test_the_instructions_come_from_the_backend(monkeypatch):
    prompts = []

    def create_agent(*args, system_prompt, **kwargs):
        prompts.append(system_prompt)
        return real_create_agent(*args, system_prompt=system_prompt, **kwargs)

    real_create_agent = main.create_agent
    monkeypatch.setattr(main, "create_agent", create_agent)
    main.run("CLM-1001", "thread-1", stub(AIMessage(content="Done.")))
    assert prompts == [INSTRUCTIONS.read_text(encoding="utf-8")]


def test_the_agent_looks_up_sections_and_its_steps_show_what_it_read():
    model = stub(
        calls(("search_documents", {"query": "wild animals"})),
        calls(("read_section", {"document": "claims_manual", "section": 7})),
        AIMessage(content="Read the note on wild animals."),
    )
    main.run("CLM-1001", "thread-1", model)
    steps = api.get("/api/claims/CLM-1001/steps").json()
    assert [(step["kind"], step["name"]) for step in steps] == [
        ("tool_call", "search_documents"),
        ("tool_result", "search_documents"),
        ("tool_call", "read_section"),
        ("tool_result", "read_section"),
        ("reply", "agent"),
    ]
    assert json.loads(steps[1]["content"])[0]["title"] == "Interpretation notes"
    assert json.loads(steps[2]["content"]) == {
        "document": "claims_manual",
        "section": 7,
    }
    assert "**Wild animals.**" in json.loads(steps[3]["content"])["text"]


def test_the_agent_looks_things_up_instead_of_reading_whole_documents():
    assert [tool.name for tool in main.TOOLS] == [
        "get_claim",
        "get_policy",
        "get_customer",
        "list_sections",
        "search_documents",
        "read_section",
        "record_decision",
        "pay_claim",
    ]
    contents = json.loads(main.list_sections.invoke({}))
    assert {"document": "claims_manual", "section": 9, "title": "Repeat claims"} in (
        contents
    )


def test_the_model_sees_no_personal_details():
    customer = json.loads(main.get_customer.invoke({"customer_id": "CUS-3001"}))
    assert set(customer) == {"name", "customer_since", "previous_claims"}
    assert customer["name"] == "Maya Patel"


def test_tools_hand_refusals_back_to_the_model():
    assert "There is no customer" in main.get_customer.invoke({"customer_id": "X"})
    refusal = main.pay_claim.invoke({"claim_id": "CLM-1001", "amount": 420})
    assert "only an approved claim" in refusal


def test_the_command_line_works_only_the_waiting_claims(monkeypatch, capsys):
    worked = []
    monkeypatch.setattr(
        main, "run", lambda claim_id, _: worked.append(claim_id) or "ok"
    )
    api.post("/api/claims/CLM-1001/start")
    cli.work([])
    assert worked == [f"CLM-{number}" for number in range(1002, 1026)]
    assert capsys.readouterr().out.startswith("CLM-1002: ok\nCLM-1003: ok\n")


def test_the_command_line_works_the_claims_named(monkeypatch):
    worked = []
    monkeypatch.setattr(
        main, "run", lambda claim_id, _: worked.append(claim_id) or "ok"
    )
    cli.work(["CLM-1004", "CLM-1009"])
    assert worked == ["CLM-1004", "CLM-1009"]


def test_the_command_line_says_when_nothing_is_waiting(capsys):
    for number in range(1001, 1026):
        api.post(f"/api/claims/CLM-{number}/start")
    cli.work([])
    assert capsys.readouterr().out == "No claims are waiting.\n"


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"
