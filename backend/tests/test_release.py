import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def start(claim_id):
    return client.post(f"/api/claims/{claim_id}/start")


def release(claim_id):
    return client.post(f"/api/claims/{claim_id}/release")


def decide(claim_id, decision, payout):
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": decision,
            "payout": payout,
            "reason": "The wording covers it.",
            "policy_section": "Policy wording, section 3, Trip Delay",
        },
    )


def claim(claim_id):
    return client.get(f"/api/claims/{claim_id}").json()


def test_a_claim_goes_back_in_the_queue_once_then_is_left_for_a_handler():
    start("CLM-1001")
    first = release("CLM-1001").json()
    assert (first["status"], first["attempts"]) == ("waiting", 1)
    start("CLM-1001")
    second = release("CLM-1001").json()
    assert (second["status"], second["attempts"]) == ("left_for_handler", 2)
    third = start("CLM-1001")
    assert third.status_code == 409
    assert third.json()["detail"] == (
        "Claim CLM-1001 can't be started: it is left for a handler."
    )


def test_the_queue_shows_the_attempts():
    start("CLM-1001")
    release("CLM-1001")
    first = client.get("/api/claims").json()[0]
    assert (first["status"], first["attempts"]) == ("waiting", 1)


@pytest.mark.parametrize(
    ("claim_id", "setup"),
    [
        ("CLM-1001", []),
        ("CLM-1013", [("decline", 0)]),
        ("CLM-1003", [("approve", 1500)]),
    ],
)
def test_only_a_claim_in_progress_can_be_released(claim_id, setup):
    if setup:
        start(claim_id)
        decide(claim_id, *setup[0])
    before = claim(claim_id)
    refused = release(claim_id)
    assert refused.status_code == 409
    assert "can't be released" in refused.json()["detail"]
    assert claim(claim_id) == before


def test_an_approval_that_wasnt_paid_is_left_for_a_handler_with_its_decision():
    start("CLM-1001")
    decide("CLM-1001", "approve", 420)
    left = release("CLM-1001").json()
    assert left["status"] == "left_for_handler"
    assert (left["decision"], left["payout"], left["paid_amount"]) == (
        "approve",
        420.0,
        None,
    )
    payment = client.post("/api/claims/CLM-1001/payment", json={"amount": 420})
    assert payment.status_code == 409
    assert payment.json()["detail"] == (
        "Claim CLM-1001 can't be paid: it is left for a handler"
        " with the decision to approve."
    )


def test_release_an_unknown_claim():
    assert release("CLM-9999").status_code == 404


def test_failures_and_reminders_are_steps():
    for kind in ("failure", "reminder"):
        step = client.post(
            "/api/claims/CLM-1001/steps",
            json={"thread_id": "t", "kind": kind, "name": "harness", "content": "x"},
        )
        assert step.json()["kind"] == kind
