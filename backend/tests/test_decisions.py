import pytest

from backend import main


def decide(client, claim_id, decision="approve", payout=420.0):
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": decision,
            "payout": payout,
            "reason": "The delay was covered.",
            "policy_section": "Section 3, Trip Delay",
        },
    )


def pay(client, claim_id, amount):
    return client.post(f"/api/claims/{claim_id}/payment", json={"amount": amount})


def sign_off(client, claim_id, handler_id="HND-01"):
    return client.post(
        f"/api/claims/{claim_id}/sign-off", json={"handler_id": handler_id}
    )


def test_approval_within_the_limit_is_decided_and_can_be_paid(client):
    claim = decide(client, "CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["decision"]["payout"] == 420.0
    assert claim["decision"]["policy_section"] == "Section 3, Trip Delay"
    paid = pay(client, "CLM-1001", 420.0).json()
    assert paid["payment"]["amount"] == 420.0


def test_approval_over_the_limit_waits_and_blocks_payment(client):
    claim = decide(client, "CLM-1002", payout=1250.0).json()
    assert claim["status"] == "awaiting_sign_off"
    response = pay(client, "CLM-1002", 1250.0)
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "A payout over $1,000.00 needs a handler's sign-off before it can be paid."
    )
    assert client.get("/api/claims/CLM-1002").json()["payment"] is None


def test_sign_off_pays_once_and_decides(client):
    decide(client, "CLM-1002", payout=1250.0)
    claim = sign_off(client, "CLM-1002").json()
    assert claim["status"] == "decided"
    assert claim["sign_off"]["handler_id"] == "HND-01"
    assert claim["payment"]["amount"] == 1250.0
    assert pay(client, "CLM-1002", 1250.0).status_code == 409


@pytest.mark.parametrize("decision", ["decline", "refer"])
def test_declined_and_referred_claims_cannot_be_paid(client, decision):
    claim = decide(client, "CLM-1001", decision=decision, payout=0).json()
    assert claim["status"] == "decided"
    response = pay(client, "CLM-1001", 100.0)
    assert response.status_code == 409
    assert response.json()["detail"] == "Only an approved claim can be paid."


def test_undecided_claim_cannot_be_paid(client):
    assert pay(client, "CLM-1001", 5000.0).status_code == 409


def test_payment_must_equal_the_payout(client):
    decide(client, "CLM-1001")
    response = pay(client, "CLM-1001", 400.0)
    assert response.status_code == 409
    assert "$420.00" in response.json()["detail"]


def test_decline_with_a_payout_is_rejected(client):
    assert decide(client, "CLM-1001", decision="decline", payout=50).status_code == 422


def test_unknown_decision_is_rejected(client):
    assert decide(client, "CLM-1001", decision="maybe").status_code == 422


def test_claim_is_decided_once(client):
    decide(client, "CLM-1001")
    assert decide(client, "CLM-1001").status_code == 409


def test_sign_off_needs_a_known_handler(client):
    decide(client, "CLM-1002", payout=1250.0)
    assert sign_off(client, "CLM-1002", "HND-99").status_code == 404


def test_sign_off_needs_a_handler_who_can_approve(client, monkeypatch):
    record = main.record

    def without_authority(connection, kind, record_id):
        found = record(connection, kind, record_id)
        if kind == "handler":
            found["can_approve_over_limit"] = False
        return found

    monkeypatch.setattr(main, "record", without_authority)
    decide(client, "CLM-1002", payout=1250.0)
    assert sign_off(client, "CLM-1002").status_code == 403


def test_sign_off_needs_a_claim_waiting_for_it(client):
    decide(client, "CLM-1001")
    assert sign_off(client, "CLM-1001").status_code == 409


def test_steps_come_back_in_order(client):
    for kind, text in [("tool_call", "get_claim"), ("reply", "Approved.")]:
        client.post("/api/claims/CLM-1001/steps", json={"kind": kind, "text": text})
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [(s["kind"], s["text"]) for s in steps] == [
        ("tool_call", "get_claim"),
        ("reply", "Approved."),
    ]


def test_steps_for_an_unknown_claim_are_404(client):
    assert client.get("/api/claims/CLM-0000/steps").status_code == 404
