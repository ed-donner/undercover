from concurrent.futures import ThreadPoolExecutor

import pytest

from backend.tests.helpers import read_sources, start


def decide(client, claim_id="CLM-1001", outcome="approve", payout=420):
    run = start(client, claim_id).json()
    read_sources(client.app.state.store, run["run_id"], claim_id)
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "run_id": run["run_id"],
            "outcome": outcome,
            "payout": payout,
            "calculation": "Eligible expenses total the approved amount.",
            "explanation": "The evidence supports this decision. See cited sections.",
            "policy_sections": [3, 10],
            "manual_version": "2026.2",
            "manual_sections": [4, 9],
        },
    )


def test_start_once(client):
    run = start(client)
    assert run.status_code == 202
    assert run.json()["thread_id"]
    assert client.get("/api/claims/CLM-1001").json()["status"] == "in_progress"
    assert start(client).status_code == 409
    assert len(client.get("/api/claims/CLM-1001/runs").json()) == 1
    assert start(client, "no").status_code == 404


@pytest.mark.parametrize(
    ("outcome", "payout"), [("approve", 420), ("decline", 0), ("refer", 0)]
)
def test_decisions(client, outcome, payout):
    response = decide(client, outcome=outcome, payout=payout)
    assert response.status_code == 200
    claim = response.json()
    assert claim["status"] == "decided"
    assert claim["decision"]["outcome"] == outcome
    assert claim["decision"]["payout"] == payout
    assert claim["decision"]["policy_sections"] == [3, 10]
    assert claim["decision"]["recorded_at"]
    assert claim["decision"]["calculation"]
    assert claim["decision"]["explanation"]
    assert (
        client.post("/api/claims/CLM-1001/decision", json=claim["decision"]).status_code
        == 422
    )
    replacement = {k: v for k, v in claim["decision"].items() if k != "recorded_at"}
    assert (
        client.post("/api/claims/CLM-1001/decision", json=replacement).status_code
        == 409
    )
    if outcome != "approve":
        assert (
            client.post("/api/claims/CLM-1001/payment", json={"amount": 1}).status_code
            == 409
        )


@pytest.mark.parametrize(
    ("outcome", "payout"),
    [
        ("other", 0),
        ("approve", 0),
        ("approve", -1),
        ("decline", 1),
        ("refer", 1),
        ("approve", "NaN"),
        ("approve", "Infinity"),
        ("approve", 1.001),
    ],
)
def test_invalid_decisions(client, outcome, payout):
    assert decide(client, outcome=outcome, payout=payout).status_code == 422
    assert client.get("/api/claims/CLM-1001").json()["decision"] is None


@pytest.mark.parametrize("amount", [1000, 1000.01])
def test_payment_limit(client, amount):
    claim = decide(client, payout=amount).json()
    path = "/api/claims/CLM-1001"
    payment = client.post(f"{path}/payment", json={"amount": amount})
    if amount == 1000:
        assert claim["status"] == "decided"
        assert payment.status_code == 200
    else:
        assert claim["status"] == "waiting_for_sign_off"
        assert payment.status_code == 409
        assert client.get(path).json()["payment"] is None
        assert (
            client.post(f"{path}/sign-off", json={"handler_id": "no"}).status_code
            == 404
        )
        signed = client.post(f"{path}/sign-off", json={"handler_id": "HND-01"}).json()
        assert signed["status"] == "decided"
        assert signed["sign_off"]["handler_id"] == "HND-01"
        assert signed["sign_off"]["signed_at"]
        assert signed["payment"] is None
        assert (
            client.post(f"{path}/payment", json={"amount": amount}).status_code == 200
        )
    paid = client.get(path).json()
    assert paid["payment"]["amount"] == amount
    assert paid["payment"]["paid_at"]
    assert client.post(f"{path}/payment", json={"amount": amount}).status_code == 409
    assert (
        client.post(f"{path}/sign-off", json={"handler_id": "HND-02"}).status_code
        == 409
    )
    assert client.get(path).json() == paid


@pytest.mark.parametrize("amount", [0, -1, "NaN", "Infinity", 10.001])
def test_invalid_payment_amounts(client, amount):
    decide(client)
    assert (
        client.post("/api/claims/CLM-1001/payment", json={"amount": amount}).status_code
        == 422
    )
    assert client.get("/api/claims/CLM-1001").json()["payment"] is None


def test_payment_before_decision_and_mismatch(client):
    path = "/api/claims/CLM-1001"
    assert client.post(f"{path}/payment", json={"amount": 420}).status_code == 409
    decide(client)
    assert client.post(f"{path}/payment", json={"amount": 419}).status_code == 409
    assert client.get(path).json()["payment"] is None


def test_concurrent_payments(client):
    decide(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(
                    "/api/claims/CLM-1001/payment", json={"amount": 420}
                ),
                range(2),
            )
        )
    assert sorted(response.status_code for response in responses) == [200, 409]
    with client.app.state.store.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 1


def test_run_cannot_decide_another_claim(client):
    run = start(client).json()
    assert (
        client.post(
            "/api/claims/CLM-1002/decision",
            json={
                "run_id": run["run_id"],
                "outcome": "refer",
                "payout": 0,
                "calculation": "No payout.",
                "explanation": "Evidence is missing. Please review.",
                "policy_sections": [11],
                "manual_version": "2026.2",
                "manual_sections": [4],
            },
        ).status_code
        == 409
    )
