import json

import pytest
from fastapi.testclient import TestClient

from backend.db import transaction
from backend.main import INSTRUCTIONS, app
from backend.seed import seed

client = TestClient(app)
SIGN_OFF_REFUSAL = "A payout over $1,000.00 waits for a handler's sign-off."


def start(claim_id):
    return client.post(f"/api/claims/{claim_id}/start")


def decide(claim_id, decision, payout):
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": decision,
            "payout": payout,
            "reason": "The wording covers it.",
            "policy_section": "Section 3, Trip Delay",
        },
    )


def pay(claim_id, amount):
    return client.post(f"/api/claims/{claim_id}/payment", json={"amount": amount})


def sign_off(claim_id, handler_id):
    return client.post(
        f"/api/claims/{claim_id}/sign-off", json={"handler_id": handler_id}
    )


def claim(claim_id):
    return client.get(f"/api/claims/{claim_id}").json()


def test_start_a_claim_once():
    assert start("CLM-1001").json()["status"] == "in_progress"
    second = start("CLM-1001")
    assert second.status_code == 409
    assert second.json()["detail"] == (
        "Claim CLM-1001 can't be started: it is in progress."
    )


def test_start_an_unknown_claim():
    assert start("CLM-9999").status_code == 404


def test_an_approval_within_the_limit_is_paid_by_the_agent():
    start("CLM-1001")
    decided = decide("CLM-1001", "approve", 420).json()
    assert decided["status"] == "in_progress"
    assert decided["decision"] == "approve"
    assert decided["payout"] == 420.0
    assert decided["decided_at"]
    paid = pay("CLM-1001", 420).json()
    assert paid["status"] == "decided"
    assert paid["paid_amount"] == 420.0
    assert paid["paid_at"]
    again = pay("CLM-1001", 420)
    assert again.status_code == 409
    assert again.json()["detail"] == "Claim CLM-1001 has already been paid $420.00."


def test_a_payout_of_exactly_the_limit_needs_no_sign_off():
    start("CLM-1002")
    decide("CLM-1002", "approve", 1000)
    assert pay("CLM-1002", 1000).json()["status"] == "decided"


def test_an_approval_over_the_limit_waits_for_a_handler():
    start("CLM-1003")
    assert decide("CLM-1003", "approve", 1500).json()["status"] == (
        "waiting_for_sign_off"
    )
    refused = pay("CLM-1003", 1500)
    assert refused.status_code == 403
    assert refused.json()["detail"] == SIGN_OFF_REFUSAL
    assert claim("CLM-1003")["paid_amount"] is None
    signed = sign_off("CLM-1003", "HND-01").json()
    assert signed["status"] == "decided"
    assert signed["signed_off_by"] == "HND-01"
    assert signed["signed_off_at"]
    assert signed["paid_amount"] == 1500.0
    assert signed["paid_at"]
    assert pay("CLM-1003", 1500).status_code == 409


@pytest.mark.parametrize(
    ("decision", "payout", "amount"),
    [
        ("approve", 420, 400),
        ("approve", 1500, 1000),
        ("decline", 0, 420),
        ("refer", 0, 420),
    ],
)
def test_a_payment_must_be_the_approved_payout(decision, payout, amount):
    start("CLM-1001")
    decide("CLM-1001", decision, payout)
    assert pay("CLM-1001", amount).status_code == 409
    assert claim("CLM-1001")["paid_amount"] is None


def test_a_claim_without_a_decision_cant_be_paid():
    start("CLM-1001")
    refused = pay("CLM-1001", 420)
    assert refused.status_code == 409
    assert refused.json()["detail"] == (
        "Claim CLM-1001 can't be paid: only an approved claim can."
    )


@pytest.mark.parametrize("decision", ["decline", "refer"])
def test_a_decline_or_referral_is_decided(decision):
    start("CLM-1001")
    decided = decide("CLM-1001", decision, 0).json()
    assert decided["status"] == "decided"
    assert decided["decision"] == decision
    assert decided["reason"] == "The wording covers it."
    assert decided["policy_section"] == "Section 3, Trip Delay"


@pytest.mark.parametrize(
    ("decision", "payout"),
    [("decline", 50), ("refer", 10), ("approve", 0), ("maybe", 0), ("approve", -5)],
)
def test_a_decision_must_make_sense(decision, payout):
    start("CLM-1001")
    assert decide("CLM-1001", decision, payout).status_code == 422


def test_a_decision_needs_a_reason_and_a_section():
    start("CLM-1001")
    response = client.post(
        "/api/claims/CLM-1001/decision",
        json={"decision": "decline", "payout": 0, "reason": "", "policy_section": ""},
    )
    assert response.status_code == 422


def test_a_decision_needs_a_claim_in_progress():
    waiting = decide("CLM-1001", "decline", 0)
    assert waiting.status_code == 409
    assert waiting.json()["detail"] == (
        "Claim CLM-1001 can't take a decision: it is waiting."
    )
    assert decide("CLM-9999", "decline", 0).status_code == 404


def test_a_decision_is_final():
    start("CLM-1001")
    decide("CLM-1001", "approve", 420)
    second = decide("CLM-1001", "decline", 0)
    assert second.status_code == 409
    assert second.json()["detail"] == (
        "Claim CLM-1001 can't take a decision: it is in progress"
        " with the decision to approve."
    )


def test_only_a_claim_waiting_for_sign_off_can_be_signed_off():
    start("CLM-1001")
    decide("CLM-1001", "approve", 420)
    refused = sign_off("CLM-1001", "HND-01")
    assert refused.status_code == 409
    assert claim("CLM-1001")["paid_amount"] is None


def test_sign_off_needs_a_known_handler():
    start("CLM-1003")
    decide("CLM-1003", "approve", 1500)
    assert sign_off("CLM-1003", "HND-99").status_code == 404


def test_sign_off_needs_a_handler_who_can_approve_over_the_limit():
    handler = client.get("/api/handlers").json()[2]
    with transaction() as db:
        db.execute(
            "UPDATE handlers SET record = ? WHERE handler_id = 'HND-03'",
            (json.dumps({**handler, "can_approve_over_limit": False}),),
        )
    start("CLM-1003")
    decide("CLM-1003", "approve", 1500)
    refused = sign_off("CLM-1003", "HND-03")
    assert refused.status_code == 403
    assert refused.json()["detail"] == (
        "Priya Raman can't sign off payouts over $1,000.00."
    )
    assert claim("CLM-1003")["status"] == "waiting_for_sign_off"


def test_steps_come_back_in_order():
    for kind, name in [("tool_call", "get_claim"), ("reply", "agent")]:
        client.post(
            "/api/claims/CLM-1001/steps",
            json={"thread_id": "t-1", "kind": kind, "name": name, "content": "..."},
        )
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [(step["kind"], step["name"]) for step in steps] == [
        ("tool_call", "get_claim"),
        ("reply", "agent"),
    ]
    assert steps[0]["thread_id"] == "t-1"
    assert steps[0]["claim_id"] == "CLM-1001"
    assert steps[0]["content"] == "..."
    assert steps[0]["created_at"]
    assert client.get("/api/claims/CLM-1002/steps").json() == []


def test_steps_need_a_known_claim_and_kind():
    step = {"thread_id": "t-1", "kind": "reply", "name": "agent", "content": "..."}
    assert client.post("/api/claims/CLM-9999/steps", json=step).status_code == 404
    assert client.get("/api/claims/CLM-9999/steps").status_code == 404
    wrong_kind = {**step, "kind": "thought"}
    assert client.post("/api/claims/CLM-1001/steps", json=wrong_kind).status_code == 422


def test_get_instructions():
    assert client.get("/api/instructions").json() == {
        "queue": (INSTRUCTIONS / "queue.md").read_text(encoding="utf-8"),
        "claim": (INSTRUCTIONS / "claim.md").read_text(encoding="utf-8"),
    }


def test_seed_resets_the_queue():
    start("CLM-1001")
    decide("CLM-1001", "decline", 0)
    client.post(
        "/api/claims/CLM-1001/steps",
        json={"thread_id": "t-1", "kind": "reply", "name": "agent", "content": "..."},
    )
    seed()
    assert claim("CLM-1001")["status"] == "waiting"
    assert claim("CLM-1001")["decision"] is None
    assert client.get("/api/claims/CLM-1001/steps").json() == []
