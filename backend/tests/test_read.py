from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.db import db_path, seed
from backend.main import app

client = TestClient(app)


def test_list_claims_in_queue_order():
    claims = client.get("/api/claims").json()
    assert len(claims) == 25
    assert claims[0]["claim_id"] == "CLM-1001"
    assert claims[0]["customer_name"] == "Maya Patel"
    assert {c["status"] for c in claims} == {"waiting"}


def test_get_claim():
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["amount_claimed"] == 420.0
    assert claim["customer_name"] == "Maya Patel"
    assert len(claim["items"]) == 3
    assert len(claim["documents"]) == 4
    assert claim["story"].startswith("My flight home from Rome")
    assert claim["decision"] is None
    assert claim["payment"] is None


def test_unknown_claim():
    assert client.get("/api/claims/CLM-9999").status_code == 404
    assert client.get("/api/claims/CLM-9999/policy").status_code == 404


def test_get_policy():
    policy = client.get("/api/claims/CLM-1001/policy").json()
    assert policy["policy_id"] == "POL-2001"
    assert policy["plan"]["name"] == "UnderCover Premium"
    assert policy["plan"]["deductible"] == 50.0
    assert policy["add_ons"] == []


def test_policy_add_ons():
    claims = client.get("/api/claims").json()
    add_ons = [
        client.get(f"/api/claims/{c['claim_id']}/policy").json()["add_ons"]
        for c in claims
    ]
    assert any(add_ons)
    assert all(a["effect"] for found in add_ons for a in found)


def test_history_has_no_personal_details():
    response = client.get("/api/claims/CLM-1001/history")
    history = response.json()
    assert history[0]["claim_id"] == "CLM-0412"
    for field in ["email", "phone", "address", "date_of_birth"]:
        assert field not in response.text


def test_policy_wording():
    text = client.get("/api/policy-wording").json()["text"]
    assert text.startswith("# UnderCover Travel Insurance: Policy Wording")


def test_instructions():
    assert "UnderCover Agent" in client.get("/api/instructions").json()["text"]


def test_handlers():
    handlers = client.get("/api/handlers").json()
    assert [h["handler_id"] for h in handlers] == ["HND-01", "HND-02", "HND-03"]
    assert "email" not in handlers[0]


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_operation_ids():
    paths = client.get("/openapi.json").json()["paths"]
    ids = {op["operationId"] for path in paths.values() for op in path.values()}
    assert {"list_claims", "get_claim", "get_policy", "get_claim_history"} <= ids


def test_reset_restores_the_seed():
    path = db_path()
    path.write_text("not a database")
    seed(path)
    assert len(client.get("/api/claims").json()) == 25


@pytest.mark.parametrize("source", sorted(Path("backend").rglob("*.py")))
def test_backend_never_reads_evals(source):
    if "tests" not in source.parts:
        assert "evals" not in source.read_text()
