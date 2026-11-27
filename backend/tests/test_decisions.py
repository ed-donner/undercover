from contextlib import closing

import pytest

from backend import db

CLAIM = "CLM-1001"


def decide(client, decision="approve", payout=420.0, claim_id=CLAIM):
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": decision,
            "payout": payout,
            "calculation": "245 + 95 + 80 = 420",
            "reasons": "The flight was canceled by the airline.",
            "policy_section": "3. Trip Delay",
        },
    )


def pay(client, amount, claim_id=CLAIM):
    return client.post(f"/api/claims/{claim_id}/payment", json={"amount": amount})


@pytest.fixture
def started(client):
    assert client.post(f"/api/claims/{CLAIM}/start").json()["status"] == "in_progress"
    return client


def test_approve_and_pay(started):
    assert decide(started).json()["status"] == "decided"
    response = pay(started, 420.0)
    assert response.status_code == 200
    claim = response.json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 420.0
    assert claim["decision"]["policy_section"] == "3. Trip Delay"


def test_payment_over_limit_is_blocked_until_sign_off(started):
    assert decide(started, payout=1500.0).json()["status"] == "awaiting_signoff"
    blocked = pay(started, 1500.0)
    assert blocked.status_code == 403
    assert "sign-off" in blocked.json()["detail"]
    assert started.get(f"/api/claims/{CLAIM}").json()["payment"] is None

    signed = started.post(
        f"/api/claims/{CLAIM}/sign-off", json={"handler_id": "HND-01"}
    )
    assert signed.status_code == 200
    claim = signed.json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 1500.0
    assert claim["sign_off"]["handler_name"] == "Dana Whitfield"


def test_sign_off_needs_permission(started):
    with closing(db.connect()) as connection:
        connection.execute(
            "INSERT INTO handlers VALUES ('HND-99', 'Trainee', 'Trainee', 0)"
        )
        connection.commit()
    decide(started, payout=1500.0)
    response = started.post(
        f"/api/claims/{CLAIM}/sign-off", json={"handler_id": "HND-99"}
    )
    assert response.status_code == 403
    assert started.get(f"/api/claims/{CLAIM}").json()["status"] == "awaiting_signoff"


def test_sign_off_errors(started):
    assert (
        started.post(f"/api/claims/{CLAIM}/sign-off", json={"handler_id": "HND-01"})
    ).status_code == 409
    decide(started, payout=1500.0)
    assert (
        started.post(f"/api/claims/{CLAIM}/sign-off", json={"handler_id": "HND-77"})
    ).status_code == 404


def test_payment_errors(started):
    assert pay(started, 420.0).status_code == 409
    decide(started)
    assert pay(started, 999.0).status_code == 409
    assert pay(started, 420.0).status_code == 200
    assert pay(started, 420.0).status_code == 409


def test_cannot_pay_a_decline(started):
    decide(started, decision="decline", payout=0)
    assert pay(started, 0).status_code == 409


def test_payout_must_match_decision(started):
    assert decide(started, decision="decline", payout=100.0).status_code == 422
    assert decide(started, decision="refer", payout=5.0).status_code == 422
    assert decide(started, payout=0).status_code == 422
    assert decide(started, decision="refer", payout=0).json()["status"] == "decided"


def test_decide_needs_a_claim_in_progress(client):
    assert decide(client).status_code == 409


def test_start_and_release(started):
    assert started.post(f"/api/claims/{CLAIM}/start").status_code == 409
    released = started.post(f"/api/claims/{CLAIM}/release").json()
    assert released["status"] == "waiting"
    assert started.post(f"/api/claims/{CLAIM}/release").status_code == 409


def test_steps_in_order(client):
    for kind, content in [("tool_call", "get_claim"), ("message", "Approved")]:
        response = client.post(
            f"/api/claims/{CLAIM}/steps", json={"kind": kind, "content": content}
        )
        assert response.status_code == 200
    steps = client.get(f"/api/claims/{CLAIM}/steps").json()
    assert [(s["kind"], s["content"]) for s in steps] == [
        ("tool_call", "get_claim"),
        ("message", "Approved"),
    ]
    assert steps[0]["step_id"] < steps[1]["step_id"]


def test_steps_for_unknown_claim(client):
    assert client.get("/api/claims/CLM-9999/steps").status_code == 404


def test_instructions(client):
    text = client.get("/api/instructions").json()["text"]
    assert text.startswith("You are the UnderCover Agent")


def test_run_agent_starts_the_agent_in_the_background(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "backend.main.agent_run",
        lambda claim_id, thread_id: calls.append((claim_id, thread_id)),
    )
    response = client.post(f"/api/claims/{CLAIM}/run")
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"
    assert calls[0][0] == CLAIM
    assert calls[0][1]
    assert client.post(f"/api/claims/{CLAIM}/run").status_code == 409
