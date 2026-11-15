import inspect
import json

import pytest

from backend import db, main
from backend.main import app

APPROVE = {
    "decision": "approve",
    "payout": 420.0,
    "policy_section": "Wording section 3",
    "reason": "Covered delay.",
}


def start(client, claim_id="CLM-1001", limit=5):
    run_id = client.post("/api/runs", json={"limit": limit}).json()["id"]
    assert client.post(f"/api/runs/{run_id}/claims/{claim_id}").status_code == 200
    return run_id


def test_seed_has_25_waiting_claims(client):
    claims = client.get("/api/claims").json()
    assert len(claims) == 25
    assert {c["status"] for c in claims} == {"waiting"}


def test_backend_never_reads_the_answer_key():
    assert "evals" not in inspect.getsource(db) + inspect.getsource(main)


def test_decide_then_pay(client):
    start(client)
    assert client.post("/api/claims/CLM-1001/decision", json=APPROVE).json() == {
        "status": "decided"
    }
    assert (
        client.post("/api/claims/CLM-1001/payment", json={"amount": 420.0}).status_code
        == 200
    )
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["paid"] == 420.0
    assert [s["kind"] for s in claim["steps"]] == ["started", "decision", "payment"]


def test_deciding_twice_is_refused(client):
    start(client)
    client.post("/api/claims/CLM-1001/decision", json=APPROVE)
    other = APPROVE | {"decision": "decline", "payout": 0}
    assert client.post("/api/claims/CLM-1001/decision", json=other).status_code == 409
    assert client.get("/api/claims/CLM-1001").json()["decision"] == "approve"


def test_paying_twice_is_refused(client):
    start(client)
    client.post("/api/claims/CLM-1001/decision", json=APPROVE)
    client.post("/api/claims/CLM-1001/payment", json={"amount": 420.0})
    assert (
        client.post("/api/claims/CLM-1001/payment", json={"amount": 420.0}).status_code
        == 409
    )


def test_payment_must_match_the_payout(client):
    start(client)
    client.post("/api/claims/CLM-1001/decision", json=APPROVE)
    assert (
        client.post("/api/claims/CLM-1001/payment", json={"amount": 999.0}).status_code
        == 409
    )


@pytest.mark.parametrize(
    "decision",
    [
        {"decision": "approve", "payout": 0},
        {"decision": "decline", "payout": 10},
        {"decision": "refer", "payout": 10},
    ],
)
def test_payout_must_fit_the_decision(client, decision):
    start(client)
    response = client.post("/api/claims/CLM-1001/decision", json=APPROVE | decision)
    assert response.status_code == 422


def test_declined_claim_cannot_be_paid(client):
    start(client)
    client.post(
        "/api/claims/CLM-1001/decision",
        json=APPROVE | {"decision": "decline", "payout": 0},
    )
    assert (
        client.post("/api/claims/CLM-1001/payment", json={"amount": 0}).status_code
        == 409
    )


def test_payout_over_the_limit_waits_for_sign_off(client):
    start(client)
    big = APPROVE | {"payout": 1250.0}
    assert client.post("/api/claims/CLM-1001/decision", json=big).json() == {
        "status": "awaiting_signoff"
    }
    pay = {"amount": 1250.0}
    assert client.post("/api/claims/CLM-1001/payment", json=pay).status_code == 409
    sign_off = client.post(
        "/api/claims/CLM-1001/sign-off", json={"handler_id": "HND-01"}
    )
    assert sign_off.status_code == 200
    assert client.post("/api/claims/CLM-1001/payment", json=pay).status_code == 200
    assert client.post("/api/claims/CLM-1001/payment", json=pay).status_code == 409


def test_payout_at_the_limit_needs_no_sign_off(client):
    start(client)
    exact = APPROVE | {"payout": 1000.0}
    assert (
        client.post("/api/claims/CLM-1001/decision", json=exact).json()["status"]
        == "decided"
    )


def test_sign_off_needs_a_handler_with_authority(client):
    with db.session() as conn:
        body = json.dumps(
            {"handler_id": "HND-02", "name": "Junior", "can_approve_over_limit": False}
        )
        conn.execute("UPDATE records SET body = ? WHERE id = 'HND-02'", (body,))
    start(client)
    client.post("/api/claims/CLM-1001/decision", json=APPROVE | {"payout": 1250.0})
    junior = client.post("/api/claims/CLM-1001/sign-off", json={"handler_id": "HND-02"})
    assert junior.status_code == 403
    unknown = client.post(
        "/api/claims/CLM-1001/sign-off", json={"handler_id": "HND-99"}
    )
    assert unknown.status_code == 404


def test_sign_off_of_a_claim_that_needs_none_is_refused(client):
    start(client)
    client.post("/api/claims/CLM-1001/decision", json=APPROVE)
    assert (
        client.post(
            "/api/claims/CLM-1001/sign-off", json={"handler_id": "HND-01"}
        ).status_code
        == 409
    )


def test_unknown_claim_is_404(client):
    assert client.get("/api/claims/CLM-0").status_code == 404


def test_lookups_leave_steps_and_hide_contact_details(client):
    start(client)
    policy = client.post("/api/claims/CLM-1001/look-up-policy").json()
    assert policy["policy"]["policy_id"] == "POL-2001"
    assert policy["plan"]["plan"] == "premium"
    history = client.post("/api/claims/CLM-1001/look-up-history").json()
    assert history["previous_claims"]
    assert "email" not in json.dumps(history)
    kinds = [s["kind"] for s in client.get("/api/claims/CLM-1001").json()["steps"]]
    assert kinds == ["started", "policy", "history"]


def test_every_operation_follows_the_api_rules():
    for route in app.routes:
        operation_id = getattr(route, "operation_id", None)
        if not route.path.startswith("/api"):  # type: ignore[attr-defined]
            continue
        assert operation_id
        doc = route.endpoint.__doc__  # type: ignore[attr-defined]
        assert doc
        assert "\n" not in doc.strip()
        for param in inspect.signature(route.endpoint).parameters.values():  # type: ignore[attr-defined]
            assert param.default is inspect.Parameter.empty or param.name == "conn"
