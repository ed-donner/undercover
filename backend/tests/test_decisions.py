def test_approve_within_limit_is_decided(client):
    response = client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "approve",
            "payout": 420.0,
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
            "payout": 1200.0,
            "reason": "Large emergency medical claim.",
            "policy_reference": "Section 7",
        },
    )
    claim = response.json()
    assert claim["status"] == "waiting for sign-off"
    assert claim["over_approval_limit"] == 1

    payment = client.post("/api/claims/CLM-1001/payment", json={"amount": 1200.0})
    assert payment.status_code == 409


def test_sign_off_then_pay(client):
    client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "approve",
            "payout": 1200.0,
            "reason": "Large emergency medical claim.",
            "policy_reference": "Section 7",
        },
    )
    sign_off = client.post(
        "/api/claims/CLM-1001/sign-off", json={"handler_id": "HND-01"}
    )
    assert sign_off.status_code == 200
    assert sign_off.json()["status"] == "decided"

    payment = client.post("/api/claims/CLM-1001/payment", json={"amount": 1200.0})
    assert payment.status_code == 200
    assert payment.json()["paid_amount"] == 1200.0


def test_sign_off_when_not_waiting_is_blocked(client):
    response = client.post(
        "/api/claims/CLM-1001/sign-off", json={"handler_id": "HND-01"}
    )
    assert response.status_code == 409


def test_pay_without_decision_is_blocked(client):
    response = client.post("/api/claims/CLM-1001/payment", json={"amount": 100.0})
    assert response.status_code == 409


def test_decline_is_decided_and_unpayable(client):
    client.post(
        "/api/claims/CLM-1001/decision",
        json={
            "decision": "decline",
            "payout": 0.0,
            "reason": "Not a covered reason.",
            "policy_reference": "Section 2",
        },
    )
    payment = client.post("/api/claims/CLM-1001/payment", json={"amount": 100.0})
    assert payment.status_code == 409


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
