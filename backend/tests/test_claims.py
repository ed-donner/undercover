from pathlib import Path

import pytest

from backend.main import INSTRUCTIONS
from backend.seed import seed

DECISION = {
    "decision": "approve",
    "payout": 215.0,
    "section": "5",
    "reason": "Covered theft.",
}


def start(client, claim_id="CLM-1001", cap=5):
    run_id = client.post("/api/runs", json={"cap": cap}).json()["run_id"]
    assert client.post(f"/api/runs/{run_id}/claims/{claim_id}/start").status_code == 200
    return run_id


def test_seed_loads_every_claim_waiting(client):
    claims = client.get("/api/claims").json()
    assert len(claims) == 25
    assert {c["status"] for c in claims} == {"waiting"}


def test_reseed_resets(client):
    start(client)
    client.post("/api/claims/CLM-1001/decision", json=DECISION)
    seed()
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "waiting"
    assert claim["decision"] is None
    assert client.get("/api/runs/current").json() is None


def test_claim_policy_and_history(client):
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["steps"] == []
    assert claim["reads"] == []
    policy = client.get(f"/api/policies/{claim['policy_id']}").json()
    assert policy["plan_terms"]["plan"] == policy["plan"]
    history = client.get(f"/api/customers/{claim['customer_id']}/history").json()
    assert "previous_claims" in history
    assert "address" not in history


@pytest.mark.parametrize(
    "path", ["/api/claims/NOPE", "/api/policies/NOPE", "/api/customers/NOPE/history"]
)
def test_unknown_records_are_404(client, path):
    assert client.get(path).status_code == 404


def test_decide_twice_is_blocked(client):
    start(client)
    assert (
        client.post("/api/claims/CLM-1001/decision", json=DECISION).status_code == 200
    )
    assert (
        client.post("/api/claims/CLM-1001/decision", json=DECISION).status_code == 409
    )
    assert client.get("/api/claims/CLM-1001").json()["status"] == "decided"


def test_decide_needs_a_claim_in_progress(client):
    assert (
        client.post("/api/claims/CLM-1001/decision", json=DECISION).status_code == 409
    )


def test_only_an_approval_has_a_payout(client):
    start(client)
    bad = {**DECISION, "decision": "decline"}
    assert client.post("/api/claims/CLM-1001/decision", json=bad).status_code == 400


def test_pay_twice_is_blocked(client):
    start(client)
    client.post("/api/claims/CLM-1001/decision", json=DECISION)
    assert (
        client.post("/api/claims/CLM-1001/payment", json={"amount": 215}).status_code
        == 200
    )
    assert (
        client.post("/api/claims/CLM-1001/payment", json={"amount": 215}).status_code
        == 409
    )
    assert client.get("/api/claims/CLM-1001").json()["payment"]["amount"] == 215


def test_pay_must_match_an_approval(client):
    start(client)
    assert (
        client.post("/api/claims/CLM-1001/payment", json={"amount": 1}).status_code
        == 409
    )
    client.post("/api/claims/CLM-1001/decision", json=DECISION)
    assert (
        client.post("/api/claims/CLM-1001/payment", json={"amount": 99}).status_code
        == 400
    )


def test_payout_over_the_limit_waits_for_sign_off(client):
    start(client)
    big = {**DECISION, "payout": 1001.0}
    assert client.post("/api/claims/CLM-1001/decision", json=big).json() == {
        "status": "awaiting_signoff"
    }
    assert (
        client.post("/api/claims/CLM-1001/payment", json={"amount": 1001}).status_code
        == 409
    )
    assert (
        client.post(
            "/api/claims/CLM-1001/sign-off", json={"handler": "Sam"}
        ).status_code
        == 200
    )
    assert (
        client.post("/api/claims/CLM-1001/payment", json={"amount": 1001}).status_code
        == 200
    )
    assert (
        client.post(
            "/api/claims/CLM-1001/sign-off", json={"handler": "Sam"}
        ).status_code
        == 409
    )


def test_exactly_the_limit_pays_without_sign_off(client):
    start(client)
    exact = {**DECISION, "payout": 1000.0}
    assert client.post("/api/claims/CLM-1001/decision", json=exact).json() == {
        "status": "decided"
    }
    assert (
        client.post("/api/claims/CLM-1001/payment", json={"amount": 1000}).status_code
        == 200
    )


def test_steps_are_recorded_in_order(client):
    client.post(
        "/api/claims/CLM-1001/steps", json={"tool": "get_claim", "summary": "a"}
    )
    client.post(
        "/api/claims/CLM-1001/steps", json={"tool": "decide", "summary": "b" * 900}
    )
    steps = client.get("/api/claims/CLM-1001").json()["steps"]
    assert [s["tool"] for s in steps] == ["get_claim", "decide"]
    assert len(steps[1]["summary"]) == 500


def test_instructions_are_served(client):
    instructions = client.get("/api/instructions").json()
    assert "check_missed" in instructions["queue_runner"]
    assert "read_section" in instructions["claim"]


def test_instructions_never_mention_the_answer_key():
    for file in INSTRUCTIONS.glob("*.md"):
        assert "evals" not in file.read_text(encoding="utf-8").lower()


def test_seed_never_reads_the_answer_key():
    for name in ["seed.py", "db.py", "main.py", "runs.py", "lookup.py"]:
        source = (Path(__file__).parent.parent / name).read_text(encoding="utf-8")
        assert "evals" not in source
