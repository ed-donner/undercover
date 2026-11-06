from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def decide(claim_id: str, decision: str, payout: float = 0.0) -> None:
    response = client.post(
        f"/api/claims/{claim_id}/decide",
        json={
            "decision": decision,
            "payout": payout,
            "reason": "Because the wording says so.",
            "reference": "Policy wording, section 3",
        },
    )
    assert response.status_code == 200


def test_approve_and_pay_under_the_limit():
    decide("CLM-1001", "approve", 420.0)

    response = client.post("/api/claims/CLM-1001/pay", json={"amount": 420.0})
    assert response.status_code == 200
    assert response.json() == {"paid": True, "status": "decided"}

    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["paid_amount"] == 420.0

    events = client.get("/api/claims/CLM-1001/events").json()
    assert [event["operation_id"] for event in events] == ["decide_claim", "pay_claim"]


def test_approve_over_the_limit_holds_for_sign_off():
    decide("CLM-1003", "approve", 3750.0)

    response = client.post("/api/claims/CLM-1003/pay", json={"amount": 3750.0})
    assert response.status_code == 200
    assert response.json() == {"paid": False, "status": "waiting_for_sign_off"}

    claim = client.get("/api/claims/CLM-1003").json()
    assert claim["status"] == "waiting_for_sign_off"
    assert claim["paid_amount"] is None

    events = client.get("/api/claims/CLM-1003/events").json()
    assert "sign-off" in events[-1]["message"]


def test_sign_off_releases_the_payment():
    decide("CLM-1003", "approve", 3750.0)
    client.post("/api/claims/CLM-1003/pay", json={"amount": 3750.0})

    response = client.post(
        "/api/claims/CLM-1003/sign-off", json={"handler_id": "HND-01"}
    )
    assert response.status_code == 200
    assert response.json() == {"paid": True, "status": "decided"}

    claim = client.get("/api/claims/CLM-1003").json()
    assert claim["status"] == "decided"
    assert claim["paid_amount"] == 3750.0
    assert claim["signed_off_by"] == "HND-01"

    events = client.get("/api/claims/CLM-1003/events").json()
    assert [event["operation_id"] for event in events] == [
        "decide_claim",
        "pay_claim",
        "sign_off_claim",
        "pay_claim",
    ]


def test_decline_needs_no_payment():
    decide("CLM-1002", "decline")
    claim = client.get("/api/claims/CLM-1002").json()
    assert claim["status"] == "decided"
    assert claim["paid_amount"] is None


def test_cannot_decide_a_claim_twice():
    decide("CLM-1002", "decline")
    response = client.post(
        "/api/claims/CLM-1002/decide",
        json={
            "decision": "approve",
            "payout": 100.0,
            "reason": "Changed my mind.",
            "reference": "Policy wording, section 3",
        },
    )
    assert response.status_code == 409


def test_cannot_pay_a_declined_claim():
    decide("CLM-1002", "decline")
    response = client.post("/api/claims/CLM-1002/pay", json={"amount": 100.0})
    assert response.status_code == 400


def test_cannot_sign_off_a_claim_that_is_not_waiting():
    response = client.post(
        "/api/claims/CLM-1001/sign-off", json={"handler_id": "HND-01"}
    )
    assert response.status_code == 409
