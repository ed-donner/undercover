from fastapi.testclient import TestClient

CLAIM = "CLM-1001"


def start(client: TestClient, claim_id: str = CLAIM):
    return client.post(f"/api/claims/{claim_id}/start")


def decide(client: TestClient, decision: str, payout: float, claim_id: str = CLAIM):
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": decision,
            "payout": payout,
            "explanation": "It is covered.",
            "policy_section": "Section 3, Trip Delay",
        },
    )


def pay(client: TestClient, amount: float, claim_id: str = CLAIM):
    return client.post(f"/api/claims/{claim_id}/payment", json={"amount": amount})


def status(client: TestClient, claim_id: str = CLAIM) -> str:
    return client.get(f"/api/claims/{claim_id}").json()["status"]


def hold_large_claim(client: TestClient, payout: float = 1250.0) -> None:
    start(client)
    assert decide(client, "approve", payout).status_code == 200


def test_start(client: TestClient):
    assert status(client) == "waiting"
    assert start(client).json()["status"] == "in_progress"
    assert start(client).status_code == 409
    assert start(client, "CLM-9999").status_code == 404


def test_decline_is_decided_and_cannot_be_paid(client: TestClient):
    start(client)
    claim = decide(client, "decline", 0).json()
    assert claim["status"] == "decided"
    assert claim["decision"]["decision"] == "decline"
    assert claim["decision"]["explanation"] == "It is covered."
    assert claim["decision"]["policy_section"] == "Section 3, Trip Delay"
    assert pay(client, 10).status_code == 409
    assert start(client).status_code == 409


def test_decision_needs_a_claim_in_progress(client: TestClient):
    assert decide(client, "decline", 0).status_code == 409
    start(client)
    decide(client, "decline", 0)
    assert decide(client, "decline", 0).status_code == 409


def test_small_approve_is_paid_once(client: TestClient):
    start(client)
    assert decide(client, "approve", 200).json()["status"] == "decided"
    paid = pay(client, 200)
    assert paid.status_code == 200
    assert paid.json()["amount"] == 200
    assert client.get(f"/api/claims/{CLAIM}").json()["payment"]["amount"] == 200
    assert pay(client, 200).status_code == 409


def test_payment_must_equal_the_payout(client: TestClient):
    start(client)
    decide(client, "approve", 200)
    assert pay(client, 199).status_code == 409
    assert client.get(f"/api/claims/{CLAIM}").json()["payment"] is None


def test_large_approve_waits_and_payment_is_blocked(client: TestClient):
    hold_large_claim(client)
    assert status(client) == "waiting_for_sign_off"
    blocked = pay(client, 1250)
    assert blocked.status_code == 409
    assert "sign-off" in blocked.json()["detail"]
    claim = client.get(f"/api/claims/{CLAIM}").json()
    assert claim["payment"] is None
    assert claim["status"] == "waiting_for_sign_off"


def test_sign_off_releases_the_payment(client: TestClient):
    hold_large_claim(client)
    response = client.post(
        f"/api/claims/{CLAIM}/sign-off", json={"handler_id": "HND-01"}
    )
    claim = response.json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 1250
    assert claim["sign_off"]["handler_id"] == "HND-01"
    assert claim["sign_off"]["handler_name"] == "Dana Whitfield"
    again = client.post(f"/api/claims/{CLAIM}/sign-off", json={"handler_id": "HND-01"})
    assert again.status_code == 409
    assert pay(client, 1250).status_code == 409


def test_sign_off_needs_a_known_handler_and_a_held_claim(client: TestClient):
    hold_large_claim(client)
    unknown = client.post(f"/api/claims/{CLAIM}/sign-off", json={"handler_id": "HND-9"})
    assert unknown.status_code == 404
    assert status(client) == "waiting_for_sign_off"
    waiting = client.post(
        "/api/claims/CLM-1002/sign-off", json={"handler_id": "HND-01"}
    )
    assert waiting.status_code == 409


def test_the_limit_is_over_1000(client: TestClient):
    start(client)
    assert decide(client, "approve", 1000).json()["status"] == "decided"
    start(client, "CLM-1002")
    held = decide(client, "approve", 1000.01, "CLM-1002")
    assert held.json()["status"] == "waiting_for_sign_off"


def test_bad_decisions_are_rejected(client: TestClient):
    start(client)
    assert decide(client, "decline", 50).status_code == 422
    assert decide(client, "approve", 0).status_code == 422
    assert decide(client, "approve", -5).status_code == 422
    assert client.post(f"/api/claims/{CLAIM}/decision", json={}).status_code == 422
    assert pay(client, 0).status_code == 422
    assert status(client) == "in_progress"


def test_steps_come_back_in_order(client: TestClient):
    for kind, text in [
        ("tool_call", "get_claim"),
        ("tool_result", "{}"),
        ("message", "Done"),
    ]:
        step = client.post(
            f"/api/claims/{CLAIM}/steps", json={"kind": kind, "text": text}
        )
        assert step.status_code == 200
    steps = client.get(f"/api/claims/{CLAIM}/steps").json()
    assert [step["text"] for step in steps] == ["get_claim", "{}", "Done"]
    assert steps[0]["id"] < steps[1]["id"]
    assert steps[0]["created_at"]
    assert client.get("/api/claims/CLM-9999/steps").status_code == 404
    bad = client.post(
        "/api/claims/CLM-9999/steps", json={"kind": "message", "text": "x"}
    )
    assert bad.status_code == 404


def test_request_bodies_have_no_optional_fields(client: TestClient):
    schema = client.get("/openapi.json").json()
    for name, model in schema["components"]["schemas"].items():
        if name.endswith("Request"):
            assert set(model["required"]) == set(model["properties"]), name
