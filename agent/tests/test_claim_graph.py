import pytest
from langchain_core.messages import AIMessage

from agent import agents, api
from agent.claim_nodes import MAX_MODEL_CALLS, ModelCallLimit
from agent.tests.conftest import StubModel

CLAIM = "CLM-1001"


def decision(kind="approve", payout="420.00"):
    return (
        "decide_claim",
        {
            "decision": kind,
            "payout": payout,
            "reason": "Stubbed.",
            "policy_reference": "Section 3",
        },
    )


def sign_off(backend):
    return backend.post(f"/api/claims/{CLAIM}/sign-off", json={"handler_id": "HND-01"})


def test_an_approval_over_the_limit_waits_then_is_paid_once(backend, script, saver):
    agents.decide_claim(CLAIM, script(decision(payout="1200.00"), "Approved."), saver)

    waiting = api.get_claim(CLAIM)
    assert waiting["status"] == "waiting for sign-off"
    assert waiting["paid_amount"] is None
    assert "waiting for a handler" in agents.decide_claim(CLAIM, script(), saver)

    sign_off(backend)
    assert api.get_claim(CLAIM)["paid_amount"] is None
    agents.decide_claim(CLAIM, script(), saver)

    paid = api.get_claim(CLAIM)
    assert (paid["status"], paid["paid_amount"]) == ("decided", "1200.00")
    assert paid["signed_off_by"] == "HND-01"
    agents.decide_claim(CLAIM, script(), saver)
    assert api.get_claim(CLAIM)["paid_on"] == paid["paid_on"]
    texts = [s["text"] for s in backend.get(f"/api/claims/{CLAIM}/steps").json()]
    assert texts[-3:] == [
        "Waiting for a handler to sign off $1200.00",
        "Signed off by HND-01",
        "Paid $1200.00",
    ]


@pytest.mark.parametrize("kind", ["decline", "refer"])
def test_a_decline_or_referral_is_not_paid(backend, script, saver, kind):
    agents.decide_claim(CLAIM, script(decision(kind, "0.00"), "Done."), saver)

    claim = api.get_claim(CLAIM)
    assert (claim["status"], claim["paid_amount"]) == ("decided", None)


def test_deciding_twice_is_a_repeat_not_a_second_decision(backend, script, saver):
    llm = script(decision(), decision(), "Done.")

    agents.decide_claim(CLAIM, llm, saver)

    claim = api.get_claim(CLAIM)
    assert claim["decision"] == "approve"
    steps = backend.get(f"/api/claims/{CLAIM}/steps").json()
    assert len([s for s in steps if s["text"].startswith("Decided")]) == 2


def test_a_refusal_goes_back_to_the_model(backend, script, saver):
    bad = ("read_section", {"document": "claims_manual", "heading": "No such section"})

    agents.decide_claim(CLAIM, script(bad, decision(), "Done."), saver)

    assert api.get_claim(CLAIM)["paid_amount"] == "420.00"


def test_no_decision_sends_the_claim_back_to_the_agent(backend, script, saver):
    agents.decide_claim(CLAIM, script("I think so.", decision(), "Done."), saver)

    assert api.get_claim(CLAIM)["decision"] == "approve"


def test_a_model_that_never_stops_fails_the_claim(backend, script, saver):
    steps = [("list_sections", {"document": "policy_wording"})] * (MAX_MODEL_CALLS + 1)

    with pytest.raises(ModelCallLimit):
        agents.decide_claim(CLAIM, script(*steps), saver)


class Stopped(BaseException):
    """Stands for a crash, a kill or Ctrl-C, which no `except Exception` catches."""


def stops_after_reading_the_claim():
    """A stub model that reads the claim, then is stopped."""
    call = AIMessage(
        content="", tool_calls=[{"name": "get_claim", "args": {}, "id": "1"}]
    )
    yield call
    raise Stopped


def test_a_stopped_claim_carries_on_from_its_last_step(backend, script, saver):
    with pytest.raises(Stopped):
        agents.decide_claim(
            CLAIM, StubModel(messages=stops_after_reading_the_claim()), saver
        )

    assert api.get_claim(CLAIM)["status"] == "in progress"
    assert api.list_unfinished_claims() == [CLAIM]
    agents.decide_claim(CLAIM, script(decision(), "Done."), saver)

    claim = api.get_claim(CLAIM)
    assert (claim["thread"], claim["paid_amount"]) == (1, "420.00")
    steps = [s["text"] for s in backend.get(f"/api/claims/{CLAIM}/steps").json()]
    assert steps.count("Decided: approve for $420.00") == 1
    assert (
        steps.count("Read the claim, its policy and the customer's claim history") == 1
    )
