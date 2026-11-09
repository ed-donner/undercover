import pytest


def decide(client, payout, decision="approve"):
    return client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": decision,
            "payout": payout,
            "reason": "Stubbed.",
            "policy_reference": "Section 3",
        },
    )


def decide_other(client, claim_id, payout):
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": "approve",
            "payout": payout,
            "reason": "Stubbed.",
            "policy_reference": "Section 3",
        },
    )


def pay(client, amount):
    return client.post("/api/claims/CLM-1001/payment", json={"amount": amount})


def test_approve_within_limit_is_decided(client):
    response = client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "approve",
            "payout": "420.00",
            "reason": "Routine trip delay with receipts.",
            "policy_reference": "Section 3",
        },
    )
    assert response.status_code == 200
    claim = response.json()
    assert claim["status"] == "decided"
    assert claim["over_approval_limit"] == 0


def test_approve_over_limit_waits_for_sign_off(client):
    response = client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "approve",
            "payout": "1200.00",
            "reason": "Large emergency medical claim.",
            "policy_reference": "Section 7",
        },
    )
    claim = response.json()
    assert claim["status"] == "waiting for sign-off"
    assert claim["over_approval_limit"] == 1

    payment = client.post("/api/claims/CLM-1001/payment", json={"amount": "1200.00"})
    assert payment.status_code == 409


def test_sign_off_then_pay(client):
    client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "approve",
            "payout": "1200.00",
            "reason": "Large emergency medical claim.",
            "policy_reference": "Section 7",
        },
    )
    sign_off = client.post(
        "/api/claims/CLM-1001/sign-off", json={"handler_id": "HND-01"}
    )
    assert sign_off.status_code == 200
    signed = sign_off.json()
    assert signed["status"] == "in progress"
    assert signed["signed_off_by"] == "HND-01"
    assert signed["signed_off_on"] is not None
    assert signed["paid_amount"] is None

    payment = client.post("/api/claims/CLM-1001/payment", json={"amount": "1200.00"})
    assert payment.status_code == 200
    assert payment.json()["paid_amount"] == "1200.00"
    assert payment.json()["status"] == "decided"


def test_sign_off_when_not_waiting_is_blocked(client):
    response = client.post(
        "/api/claims/CLM-1001/sign-off", json={"handler_id": "HND-01"}
    )
    assert response.status_code == 409


def test_pay_without_decision_is_blocked(client):
    response = client.post("/api/claims/CLM-1001/payment", json={"amount": "100.00"})
    assert response.status_code == 409


def test_decline_is_decided_and_unpayable(client):
    client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "decline",
            "payout": "0.00",
            "reason": "Not a covered reason.",
            "policy_reference": "Section 2",
        },
    )
    payment = client.post("/api/claims/CLM-1001/payment", json={"amount": "100.00"})
    assert payment.status_code == 409


def test_a_decided_claim_cannot_be_decided_again(client):
    decide(client, "420.00")

    response = decide(client, "999.00")

    assert response.status_code == 409
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["payout"] == "420.00"


def test_the_same_payment_twice_is_done_once(client):
    decide(client, "420.00")
    first = pay(client, "420.00").json()

    second = pay(client, "420.00")

    assert second.status_code == 200
    assert second.json()["paid_on"] == first["paid_on"]


def test_a_different_payment_on_a_paid_claim_is_refused(client):
    decide(client, "420.00")
    pay(client, "420.00")

    response = pay(client, "421.00")

    assert response.status_code == 409
    assert "already been paid" in response.json()["detail"]


def test_the_same_decision_twice_is_done_once(client):
    first = decide(client, "420.00").json()

    second = decide(client, "420.00")

    assert second.status_code == 200
    assert second.json()["decided_on"] == first["decided_on"]


def test_a_signed_off_claim_cannot_be_decided_differently(client):
    decide(client, "1200.00")
    client.post("/api/claims/CLM-1001/sign-off", json={"handler_id": "HND-01"})

    assert decide(client, "1100.00").status_code == 409
    assert decide(client, "0.00", decision="decline").status_code == 409


def test_the_same_sign_off_twice_is_done_once(client):
    decide(client, "1200.00")
    body = {"handler_id": "HND-01"}
    first = client.post("/api/claims/CLM-1001/sign-off", json=body).json()

    second = client.post("/api/claims/CLM-1001/sign-off", json=body)

    assert second.status_code == 200
    assert second.json()["signed_off_on"] == first["signed_off_on"]


def test_unfinished_claims_are_stopped_or_ready_to_pay(client):
    client.post("/api/claims/CLM-1001/steps", json={"text": "started"})
    decide_other(client, "CLM-1002", "420.00")
    decide_other(client, "CLM-1003", "1200.00")
    decide_other(client, "CLM-1004", "1200.00")
    client.post("/api/claims/CLM-1004/sign-off", json={"handler_id": "HND-01"})
    decide_other(client, "CLM-1005", "300.00")
    client.post("/api/claims/CLM-1005/payment", json={"amount": "300.00"})

    claims = client.get("/api/unfinished-claims").json()

    assert claims == ["CLM-1001", "CLM-1002", "CLM-1004"]


def test_payment_must_equal_the_approved_payout(client):
    decide(client, "420.00")

    response = pay(client, "421.00")

    assert response.status_code == 409
    assert client.get("/api/claims/CLM-1001").json()["paid_amount"] is None


def test_amounts_are_exact_to_the_cent(client):
    claim = decide(client, "0.10").json()
    assert claim["payout"] == "0.10"
    assert pay(client, "0.10").json()["paid_amount"] == "0.10"


@pytest.mark.parametrize("amount", ["-1.00", "1.005", "abc"])
def test_malformed_amounts_are_rejected(client, amount):
    assert decide(client, amount).status_code == 422


def test_record_step_moves_claim_in_progress_and_lists_in_order(client):
    client.post(
        "/api/claims/CLM-1001/steps", json={"text": "Read the claim and policy"}
    )
    client.post("/api/claims/CLM-1001/steps", json={"text": "Read the policy wording"})

    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "in progress"

    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [step["text"] for step in steps] == [
        "Read the claim and policy",
        "Read the policy wording",
    ]


def test_a_sign_off_tells_the_agent_once_after_it_is_saved(client, agent_stub):
    decide(client, "1200.00")

    client.post("/api/claims/CLM-1001/sign-off", json={"handler_id": "HND-01"})

    assert agent_stub.calls == ["/api/claims/CLM-1001/resume"]


def test_the_sign_off_stands_when_the_agent_is_unreachable(client):
    decide(client, "1200.00")

    response = client.post(
        "/api/claims/CLM-1001/sign-off", json={"handler_id": "HND-01"}
    )

    assert response.status_code == 200
    assert client.get("/api/claims/CLM-1001").json()["signed_off_by"] == "HND-01"


@pytest.mark.parametrize("decision", ["decline", "refer"])
def test_only_an_approval_has_a_payout(client, decision):
    response = client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": decision,
            "payout": "50.00",
            "reason": "r",
            "policy_reference": "s",
        },
    )

    assert response.status_code == 422
