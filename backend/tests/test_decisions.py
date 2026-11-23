from backend import db

CLAIM = "CLM-1001"


def decide(client, decision="approve", payout=420.0, claim=CLAIM):
    return client.post(
        f"/api/claims/{claim}/decision",
        json={
            "decision": decision,
            "payout": payout,
            "explanation": "It is covered.",
            "policy_section": "3",
        },
    )


def pay(client, amount, claim=CLAIM):
    return client.post(f"/api/claims/{claim}/payment", json={"amount": amount})


def sign_off(client, handler="HND-01", claim=CLAIM):
    return client.post(f"/api/claims/{claim}/sign-off", json={"handler_id": handler})


def detail(client, claim=CLAIM):
    return client.get(f"/api/claims/{claim}").json()


def test_a_payout_at_the_limit_pays_without_sign_off(client):
    assert decide(client, payout=1000.0).status_code == 200
    assert pay(client, 1000.0).json()["amount"] == 1000.0
    assert detail(client)["state"] == "decided"


def test_a_payout_over_the_limit_is_blocked(client):
    decide(client, payout=1000.01)
    assert detail(client)["state"] == "waiting for sign-off"
    response = pay(client, 1000.01)
    assert response.status_code == 409
    assert "sign-off" in response.json()["detail"]
    assert detail(client)["payment"] is None
    assert detail(client)["state"] == "waiting for sign-off"


def test_the_agent_cannot_pay_a_large_payout(client):
    decide(client, payout=1500.0)
    assert pay(client, 1500.0).status_code == 409
    assert detail(client)["payment"] is None


def test_sign_off_pays_the_payout(client):
    decide(client, payout=1500.0)
    payment = sign_off(client).json()
    assert payment["amount"] == 1500.0
    assert payment["signed_off_by"] == "HND-01"
    assert detail(client)["state"] == "decided"
    assert detail(client)["payment"]["amount"] == 1500.0


def test_the_amount_must_match_the_payout(client):
    decide(client, payout=420.0)
    assert pay(client, 400.0).status_code == 409
    assert pay(client, 4200.0).status_code == 409


def test_only_an_approval_is_paid(client):
    assert pay(client, 100.0).status_code == 409
    decide(client, "decline", 0.0)
    assert pay(client, 100.0).status_code == 409
    decide(client, "refer", 0.0, "CLM-1002")
    assert pay(client, 0.0, "CLM-1002").status_code == 409


def test_sign_off_is_refused_for_unknown_or_unauthorized_handlers(client):
    decide(client, payout=1500.0)
    assert sign_off(client, "HND-99").status_code == 404
    with db.session() as conn:
        conn.execute(
            "UPDATE handlers SET data = json_set(data, '$.can_approve_over_limit', 0)"
            " WHERE handler_id = 'HND-02'"
        )
    assert sign_off(client, "HND-02").status_code == 403
    assert detail(client)["payment"] is None


def test_sign_off_needs_a_payout_over_the_limit(client):
    assert sign_off(client).status_code == 409
    decide(client, payout=420.0)
    assert sign_off(client).status_code == 409


def test_a_claim_is_paid_once(client):
    decide(client, payout=420.0)
    assert pay(client, 420.0).status_code == 200
    assert pay(client, 420.0).status_code == 409
    decide(client, payout=1500.0, claim="CLM-1002")
    assert sign_off(client, claim="CLM-1002").status_code == 200
    assert sign_off(client, claim="CLM-1002").status_code == 409
    assert pay(client, 1500.0, "CLM-1002").status_code == 409


def test_decisions_must_make_sense(client):
    assert decide(client, "decline", 200.0).status_code == 422
    assert decide(client, "refer", 5.0).status_code == 422
    assert decide(client, "approve", 0.0).status_code == 422
    assert decide(client, "maybe", 0.0).status_code == 422
    assert detail(client)["decision"] is None


def test_a_claim_has_one_decision(client):
    assert decide(client, "decline", 0.0).status_code == 200
    assert decide(client, "approve", 100.0).status_code == 409
    assert detail(client)["decision"]["decision"] == "decline"
    assert detail(client)["state"] == "decided"


def test_unknown_claims_are_not_found(client):
    assert decide(client, claim="CLM-0000").status_code == 404
    assert client.get("/api/claims/CLM-0000/steps").status_code == 404
    step = {"kind": "message", "text": "Hello"}
    assert client.post("/api/claims/CLM-0000/steps", json=step).status_code == 404


def test_steps_are_listed_in_order(client):
    for kind, text in (("tool_call", "one"), ("tool_result", "two"), ("message", "3")):
        response = client.post(
            f"/api/claims/{CLAIM}/steps", json={"kind": kind, "text": text}
        )
        assert response.status_code == 200
    steps = client.get(f"/api/claims/{CLAIM}/steps").json()
    assert [step["text"] for step in steps] == ["one", "two", "3"]
    assert [step["kind"] for step in steps] == ["tool_call", "tool_result", "message"]
    assert client.get("/api/claims/CLM-1002/steps").json() == []


def test_a_step_needs_a_known_kind(client):
    step = {"kind": "gossip", "text": "x"}
    assert client.post(f"/api/claims/{CLAIM}/steps", json=step).status_code == 422
