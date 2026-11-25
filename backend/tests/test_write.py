import json

import pytest

from backend import db

APPROVE_SMALL = {
    "decision": "approve",
    "payout": 420.0,
    "reason": "The flight was canceled for a crew problem.",
    "policy_section": "3. Trip Delay",
}
APPROVE_LARGE = APPROVE_SMALL | {"payout": 1150.0}
DECLINE = APPROVE_SMALL | {"decision": "decline", "payout": 0}


def start(client, claim_id="CLM-1001"):
    assert client.post(f"/api/claims/{claim_id}/start").status_code == 200


def decide(client, decision, claim_id="CLM-1001"):
    start(client, claim_id)
    response = client.post(f"/api/claims/{claim_id}/decision", json=decision)
    assert response.status_code == 200
    return response.json()


def pay(client, amount, claim_id="CLM-1001"):
    return client.post(f"/api/claims/{claim_id}/payment", json={"amount": amount})


def test_start_claim(client):
    start(client)
    assert client.get("/api/claims/CLM-1001").json()["status"] == "in_progress"
    response = client.post("/api/claims/CLM-1001/start")
    assert response.status_code == 409
    assert response.json()["detail"] == "CLM-1001 is in_progress, not waiting"


def test_decision_needs_a_claim_in_progress(client):
    response = client.post("/api/claims/CLM-1001/decision", json=APPROVE_SMALL)
    assert response.status_code == 409


def test_small_approval_is_decided(client):
    claim = decide(client, APPROVE_SMALL)
    assert claim["status"] == "decided"
    assert claim["decision"] == "approve"
    assert claim["payout"] == 420.0
    assert claim["policy_section"] == "3. Trip Delay"
    assert claim["decided_at"]


def test_large_approval_waits_for_signoff(client):
    claim = decide(client, APPROVE_LARGE)
    assert claim["status"] == "awaiting_signoff"


@pytest.mark.parametrize("decision", ["decline", "refer"])
def test_decline_or_refer_is_decided(client, decision):
    claim = decide(client, DECLINE | {"decision": decision})
    assert claim["status"] == "decided"


@pytest.mark.parametrize(
    "bad",
    [
        DECLINE | {"payout": 100.0},
        APPROVE_SMALL | {"decision": "maybe"},
        APPROVE_SMALL | {"payout": -1},
    ],
)
def test_invalid_decisions(client, bad):
    start(client)
    response = client.post("/api/claims/CLM-1001/decision", json=bad)
    assert response.status_code == 422


def test_pay_small_approval(client):
    decide(client, APPROVE_SMALL)
    claim = pay(client, 420.0).json()
    assert claim["paid_amount"] == 420.0
    assert claim["paid_at"]


@pytest.mark.parametrize(
    ("decision", "amount", "message"),
    [
        (None, 420.0, "CLM-1001 has no decision yet"),
        (DECLINE, 0, "CLM-1001 was not approved, so nothing is paid"),
        (
            APPROVE_LARGE,
            1150.0,
            "The payout is over $1,000.00, so the payment waits for a "
            "handler's sign-off",
        ),
        (APPROVE_SMALL, 400.0, "The amount must be the approved payout of $420.00"),
    ],
)
def test_payment_refused(client, decision, amount, message):
    if decision:
        decide(client, decision)
    response = pay(client, amount)
    assert response.status_code == 409
    assert response.json()["detail"] == message


def test_pay_only_once(client):
    decide(client, APPROVE_SMALL)
    pay(client, 420.0)
    response = pay(client, 420.0)
    assert response.status_code == 409
    assert response.json()["detail"] == "CLM-1001 has already been paid"


def test_signoff_releases_payment(client):
    decide(client, APPROVE_LARGE)
    claim = client.post(
        "/api/claims/CLM-1001/signoff", json={"handler_id": "HND-01"}
    ).json()
    assert claim["status"] == "decided"
    assert claim["signed_off_by"] == "HND-01"
    assert claim["signed_off_at"]
    assert pay(client, 1150.0).json()["paid_amount"] == 1150.0


def test_signoff_needs_a_claim_awaiting_signoff(client):
    decide(client, APPROVE_SMALL)
    response = client.post(
        "/api/claims/CLM-1001/signoff", json={"handler_id": "HND-01"}
    )
    assert response.status_code == 409


def test_signoff_needs_a_known_handler(client):
    decide(client, APPROVE_LARGE)
    response = client.post(
        "/api/claims/CLM-1001/signoff", json={"handler_id": "HND-99"}
    )
    assert response.status_code == 404


def test_signoff_needs_authority(client):
    database = db.connect()
    record = json.loads(
        database.execute("SELECT record FROM handlers WHERE id = 'HND-03'").fetchone()[
            0
        ]
    )
    record["can_approve_over_limit"] = False
    database.execute(
        "UPDATE handlers SET record = ? WHERE id = 'HND-03'", (json.dumps(record),)
    )
    database.commit()
    database.close()
    decide(client, APPROVE_LARGE)
    response = client.post(
        "/api/claims/CLM-1001/signoff", json={"handler_id": "HND-03"}
    )
    assert response.status_code == 403
    assert client.get("/api/claims/CLM-1001").json()["status"] == "awaiting_signoff"


def test_steps_in_order(client):
    for n in range(3):
        client.post(
            "/api/claims/CLM-1001/steps",
            json={"kind": "message", "content": f"step {n}"},
        )
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [s["content"] for s in steps] == ["step 0", "step 1", "step 2"]
    assert all(s["created_at"] for s in steps)


def test_start_keeps_earlier_steps(client):
    client.post("/api/claims/CLM-1001/steps", json={"kind": "error", "content": "old"})
    start(client)
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [s["content"] for s in steps] == ["old"]


def test_read_steps(client):
    response = client.post(
        "/api/claims/CLM-1001/steps",
        json={"kind": "read", "content": "Claims manual, 9. Repeat claims"},
    )
    assert response.status_code == 200
    assert client.get("/api/claims/CLM-1001/steps").json()[0]["kind"] == "read"


def release(client, problem="No decision recorded", claim_id="CLM-1001"):
    response = client.post(f"/api/claims/{claim_id}/release", json={"problem": problem})
    assert response.status_code == 200
    return response.json()


def test_release_claim(client):
    start(client)
    claim = release(client)
    assert claim["status"] == "waiting"
    assert claim["attempts"] == 1
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert steps[-1]["kind"] == "error"
    assert steps[-1]["content"] == "No decision recorded"


def test_a_retry_is_marked_as_a_new_attempt(client):
    start(client)
    release(client, "The model provider timed out")
    start(client)
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [(s["kind"], s["content"]) for s in steps] == [
        ("error", "The model provider timed out"),
        ("attempt", "Attempt 2"),
    ]


def test_second_failure_leaves_the_claim_for_a_handler(client):
    start(client)
    release(client, "First problem")
    start(client)
    claim = release(client, "Second problem")
    assert claim["status"] == "needs_handler"
    assert claim["attempts"] == 2
    assert client.post("/api/claims/CLM-1001/start").status_code == 409
    errors = [
        s["content"]
        for s in client.get("/api/claims/CLM-1001/steps").json()
        if s["kind"] == "error"
    ]
    assert errors == ["First problem", "Second problem"]


def test_a_decided_claim_is_never_released(client):
    decide(client, APPROVE_SMALL)
    response = client.post(
        "/api/claims/CLM-1001/release", json={"problem": "Late failure"}
    )
    assert response.status_code == 409
    assert client.get("/api/claims/CLM-1001").json()["status"] == "decided"


def test_release_needs_a_claim_in_progress(client):
    response = client.post(
        "/api/claims/CLM-1001/release", json={"problem": "No decision recorded"}
    )
    assert response.status_code == 409
