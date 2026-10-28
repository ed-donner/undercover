import json

import pytest
from fastapi.routing import APIRoute

from backend import db
from backend.main import app

QUEUE = json.loads((db.DATA / "claims.json").read_text(encoding="utf-8"))


def test_queue_is_seeded_from_claims(client):
    claims = client.get("/api/claims").json()
    assert [claim["claim_id"] for claim in claims] == [c["claim_id"] for c in QUEUE]
    assert len(claims) == 25
    assert {claim["status"] for claim in claims} == {"waiting"}
    assert claims[0] == {
        "claim_id": "CLM-1001",
        "claim_type": "trip_delay",
        "summary": "Flight home canceled by the airline, rebooked the next morning",
        "amount_claimed": 420.0,
        "submitted_on": "2026-06-24",
        "status": "waiting",
        "decision": None,
        "payout": None,
    }


def test_seeding_twice_adds_nothing(client):
    db.init()
    assert len(client.get("/api/claims").json()) == 25


def test_reset_restores_the_queue(client):
    with db.connect() as connection:
        connection.execute("UPDATE claims SET status = 'decided'")
    db.reset()
    claims = client.get("/api/claims").json()
    assert {claim["status"] for claim in claims} == {"waiting"}


def test_get_claim(client):
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "waiting"
    assert claim["policy_id"] == "POL-2001"
    assert len(claim["documents"]) == 4
    assert claim["decision"] is None
    assert claim["sign_off"] is None
    assert claim["payment"] is None


def test_get_policy(client):
    policy = client.get("/api/policies/POL-2001").json()
    assert policy["plan"] == "premium"
    assert policy["plan_details"]["trip_delay_max"] == 800.0
    assert policy["deductible_applies_to"] == ["baggage", "emergency_medical"]
    assert policy["add_on_details"] == []


def test_get_claim_history_leaves_out_personal_details(client):
    history = client.get("/api/customers/CUS-3001/claims").json()
    assert history["previous_claims"][0]["claim_id"] == "CLM-0412"
    for detail in ["email", "phone", "address", "date_of_birth", "name"]:
        assert detail not in history


def test_get_policy_wording(client):
    wording = client.get("/api/policy-wording").json()
    assert wording["version"] == "2026.1"
    assert wording["text"].startswith("# UnderCover Travel Insurance: Policy Wording")


def test_get_instructions(client):
    assert "UnderCover Agent" in client.get("/api/instructions").json()["text"]


def test_list_handlers(client):
    handlers = client.get("/api/handlers").json()
    assert [h["handler_id"] for h in handlers] == ["HND-01", "HND-02", "HND-03"]


@pytest.mark.parametrize(
    "path",
    ["/api/claims/CLM-0000", "/api/policies/POL-0000", "/api/customers/CUS-0/claims"],
)
def test_unknown_records_are_404(client, path):
    response = client.get(path)
    assert response.status_code == 404
    assert response.json()["detail"].startswith("There is no")


def test_every_route_has_an_operation_id_and_a_one_line_docstring():
    for route in app.routes:
        if isinstance(route, APIRoute):
            assert route.operation_id == route.name, route.path
            doc = (route.endpoint.__doc__ or "").strip()
            assert doc, route.path
            assert "\n" not in doc, route.path


def test_no_operation_has_optional_inputs():
    spec = app.openapi()
    schemas = spec.get("components", {}).get("schemas", {})
    for methods in spec["paths"].values():
        for operation in methods.values():
            for parameter in operation.get("parameters", []):
                assert parameter["required"], operation["operationId"]
            if "requestBody" in operation:
                body = operation["requestBody"]["content"]["application/json"]
                schema = schemas[body["schema"]["$ref"].split("/")[-1]]
                assert set(schema["required"]) == set(schema["properties"])
