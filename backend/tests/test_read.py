import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend import db
from backend.main import app

DATA = Path(__file__).resolve().parents[2] / "data"


def test_seed_reads_no_evals():
    evals = DATA / "evals"
    assert all(evals not in file.parents for file in db.SEED_FILES)
    assert all(file.parent == DATA for file in db.SEED_FILES)


def test_seed_loads_the_queue(client):
    claims = client.get("/api/claims").json()
    expected = [c["claim_id"] for c in json.loads((DATA / "claims.json").read_text())]
    assert [c["claim_id"] for c in claims] == sorted(expected)
    assert {c["status"] for c in claims} == {"waiting"}
    database = db.connect()
    counts = {
        table: database.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
        for table in ["claims", "policies", "customers", "handlers"]
    }
    database.close()
    assert counts == {"claims": 25, "policies": 50, "customers": 49, "handlers": 3}


def test_list_claims_fields(client):
    first = client.get("/api/claims").json()[0]
    assert first == {
        "claim_id": "CLM-1001",
        "claim_type": "trip_delay",
        "summary": "Flight home canceled by the airline, rebooked the next morning",
        "amount_claimed": 420.0,
        "submitted_on": "2026-06-24",
        "status": "waiting",
        "decision": None,
    }


def test_get_claim(client):
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["story"].startswith("My flight home from Rome")
    assert len(claim["items"]) == 3
    assert claim["documents"][0]["type"] == "carrier_report"
    assert claim["status"] == "waiting"
    assert claim["decision"] is None


def test_unknown_claim(client):
    response = client.get("/api/claims/CLM-0000")
    assert response.status_code == 404
    assert response.json() == {"detail": "CLM-0000 was not found"}


def test_get_policy(client):
    policy = client.get("/api/policies/POL-2001").json()
    assert policy["plan"] == "premium"
    assert policy["plan_details"]["trip_delay_max"] == 800.0
    assert policy["deductible_applies_to"] == ["baggage", "emergency_medical"]
    assert policy["add_on_details"] == []


def test_get_policy_with_add_ons(client):
    policies = json.loads((DATA / "policies.json").read_text())
    with_add_on = next(p for p in policies if p["add_ons"])
    policy = client.get(f"/api/policies/{with_add_on['policy_id']}").json()
    names = [a["add_on"] for a in policy["add_on_details"]]
    assert names == with_add_on["add_ons"]


def test_claim_history_has_no_personal_details(client):
    history = client.get("/api/customers/CUS-3001/history").json()
    assert history["previous_claims"][0]["claim_id"] == "CLM-0412"
    text = json.dumps(history)
    for private in ["maya.patel@example.com", "555 0143", "Wayne Street", "1988-03-14"]:
        assert private not in text


def test_policy_wording(client):
    wording = client.get("/api/policy-wording").json()["wording"]
    assert wording.startswith("# UnderCover Travel Insurance: Policy Wording")


def test_instructions(client):
    instructions = client.get("/api/instructions").json()["instructions"]
    assert "UnderCover Agent" in instructions


def test_handlers(client):
    handlers = client.get("/api/handlers").json()
    assert len(handlers) == 3
    assert set(handlers[0]) == {"handler_id", "name", "role", "can_approve_over_limit"}


def test_every_operation_is_documented(client):
    schema = client.get("/openapi.json").json()
    for path_item in schema["paths"].values():
        for operation in path_item.values():
            assert operation["operationId"]
            assert operation["description"]
            assert "\n" not in operation["description"]
            for parameter in operation.get("parameters", []):
                assert parameter["required"]
            body = operation.get("requestBody", {}).get("content", {})
            for content in body.values():
                ref = content["schema"]["$ref"].split("/")[-1]
                model = schema["components"]["schemas"][ref]
                assert set(model.get("required", [])) == set(model["properties"])


def test_startup_seeds_a_missing_database(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "fresh.db"))
    with TestClient(app) as fresh:
        assert len(fresh.get("/api/claims").json()) == 25
