import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)

REASON = {"reason": "Covered by the wording.", "policy_section": "Section 3"}


def decide(claim_id, decision, payout):
    client.post(f"/api/claims/{claim_id}/start")
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={"decision": decision, "payout": payout, **REASON},
    )


def status(claim_id):
    return client.get(f"/api/claims/{claim_id}").json()["status"]


def test_approve_under_the_limit_and_pay():
    assert client.post("/api/claims/CLM-1001/start").json()["status"] == "in_progress"
    response = client.post(
        "/api/claims/CLM-1001/decision",
        json={"decision": "approve", "payout": 420.0, **REASON},
    )
    assert response.json()["status"] == "in_progress"
    claim = client.post("/api/claims/CLM-1001/payment", json={"amount": 420.0}).json()
    assert claim["status"] == "decided"
    assert claim["decision"]["payout"] == 420.0
    assert claim["payment"] == {"amount": 420.0, "signed_off_by": None}


def test_payment_over_the_limit_is_blocked_until_sign_off():
    assert decide("CLM-1003", "approve", 1500.0).json()["status"] == "awaiting_signoff"
    response = client.post("/api/claims/CLM-1003/payment", json={"amount": 1500.0})
    assert response.status_code == 409
    assert "sign-off" in response.json()["detail"]
    assert client.get("/api/claims/CLM-1003").json()["payment"] is None

    claim = client.post("/api/claims/CLM-1003/signoff", json={"handler_id": "HND-01"})
    assert claim.json()["status"] == "decided"
    assert claim.json()["payment"] == {
        "amount": 1500.0,
        "signed_off_by": "Dana Whitfield",
    }
    assert (
        client.post("/api/claims/CLM-1003/payment", json={"amount": 1500.0}).status_code
        == 409
    )


def test_exactly_the_limit_needs_no_sign_off():
    assert decide("CLM-1003", "approve", 1000.0).json()["status"] == "in_progress"


def test_pay_the_wrong_amount():
    decide("CLM-1001", "approve", 420.0)
    response = client.post("/api/claims/CLM-1001/payment", json={"amount": 500.0})
    assert response.status_code == 409
    assert status("CLM-1001") == "in_progress"


def test_pay_twice():
    decide("CLM-1001", "approve", 420.0)
    client.post("/api/claims/CLM-1001/payment", json={"amount": 420.0})
    assert (
        client.post("/api/claims/CLM-1001/payment", json={"amount": 420.0}).status_code
        == 409
    )


@pytest.mark.parametrize("decision", ["decline", "refer"])
def test_decline_and_refer_are_decided_and_unpaid(decision):
    assert decide("CLM-1002", decision, 0).json()["status"] == "decided"
    assert (
        client.post("/api/claims/CLM-1002/payment", json={"amount": 10.0}).status_code
        == 409
    )


def test_pay_before_deciding():
    client.post("/api/claims/CLM-1001/start")
    assert (
        client.post("/api/claims/CLM-1001/payment", json={"amount": 420.0}).status_code
        == 409
    )


def test_decide_out_of_order():
    body = {"decision": "decline", "payout": 0, **REASON}
    assert client.post("/api/claims/CLM-1001/decision", json=body).status_code == 409
    decide("CLM-1001", "decline", 0)
    assert client.post("/api/claims/CLM-1001/decision", json=body).status_code == 409
    assert client.post("/api/claims/CLM-1001/start").status_code == 409


def test_resume_an_undecided_claim():
    client.post("/api/claims/CLM-1001/start")
    resumed = client.post("/api/claims/CLM-1001/start")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "in_progress"
    decide("CLM-1001", "approve", 420.0)
    assert client.post("/api/claims/CLM-1001/start").status_code == 409


@pytest.mark.parametrize(
    ("decision", "payout"),
    [("pay", 10), ("approve", -5), ("approve", 0), ("decline", 50), ("refer", 1)],
)
def test_bad_decisions(decision, payout):
    client.post("/api/claims/CLM-1001/start")
    response = client.post(
        "/api/claims/CLM-1001/decision",
        json={"decision": decision, "payout": payout, **REASON},
    )
    assert response.status_code == 422


def test_sign_off_rules():
    assert (
        client.post(
            "/api/claims/CLM-1001/signoff", json={"handler_id": "HND-01"}
        ).status_code
        == 409
    )
    decide("CLM-1003", "approve", 1500.0)
    assert (
        client.post(
            "/api/claims/CLM-1003/signoff", json={"handler_id": "HND-99"}
        ).status_code
        == 422
    )
    assert status("CLM-1003") == "awaiting_signoff"


def test_steps_in_order():
    for text in ["first", "second", "third"]:
        client.post("/api/claims/CLM-1001/steps", json={"text": text})
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [s["text"] for s in steps] == ["first", "second", "third"]
    assert client.get("/api/claims/CLM-1002/steps").json() == []
    assert (
        client.post("/api/claims/CLM-9999/steps", json={"text": "x"}).status_code == 404
    )


def test_queue_shows_decisions():
    decide("CLM-1003", "approve", 1500.0)
    summary = client.get("/api/claims").json()[2]
    assert (summary["status"], summary["decision"], summary["payout"]) == (
        "awaiting_signoff",
        "approve",
        1500.0,
    )
