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
        "attempts": 0,
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
    instructions = client.get("/api/instructions").json()
    assert set(instructions) == {"queue", "claim"}
    assert "running the claims queue" in instructions["queue"]
    assert "claims manual" in instructions["claim"]


def test_seed_stores_the_manual(client):
    database = db.connect()
    manual = db.setting(database, "claims_manual")
    database.close()
    assert manual.startswith("# UnderCover Claims Handling Manual")


def test_list_sections(client):
    manual = client.get("/api/documents/claims-manual/sections").json()
    assert manual["document"] == "Claims manual"
    assert manual["introduction"].startswith("# UnderCover Claims Handling Manual")
    assert len(manual["sections"]) == 14
    assert manual["sections"][8] == "9. Repeat claims"
    wording = client.get("/api/documents/policy-wording/sections").json()
    assert len(wording["sections"]) == 12
    assert wording["sections"][0] == "1. Your plan"


def test_list_sections_of_an_unknown_document(client):
    response = client.get("/api/documents/evals/sections")
    assert response.status_code == 404
    assert response.json()["detail"] == (
        "evals is not a document: use policy-wording or claims-manual"
    )


def test_read_section(client):
    section = client.get("/api/documents/claims-manual/sections/9").json()
    assert section["document"] == "Claims manual"
    assert section["section"] == "9. Repeat claims"
    assert section["text"].startswith("Before deciding any claim")
    assert "## " not in section["text"]
    assert "Meals without receipts" not in section["text"]
    last = client.get("/api/documents/policy-wording/sections/12").json()
    assert last["section"] == "12. Definitions"


def test_read_section_tells_1_from_10(client):
    section = client.get("/api/documents/claims-manual/sections/1").json()
    assert section["section"] == "1. Purpose and scope"


def test_read_an_unknown_section(client):
    response = client.get("/api/documents/claims-manual/sections/15")
    assert response.status_code == 404
    assert response.json()["detail"] == "The claims manual has no section 15"


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


def test_startup_closes_an_interrupted_run(client):
    client.post("/api/runs", json={"cap": 1})
    client.post("/api/claims/CLM-1001/start")
    with TestClient(app) as restarted:
        assert restarted.get("/api/runs/latest").json()["status"] == "failed"
        claim = restarted.get("/api/claims/CLM-1001").json()
        assert claim["status"] == "waiting"
        assert claim["attempts"] == 1


def test_startup_seeds_a_missing_database(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "fresh.db"))
    with TestClient(app) as fresh:
        assert len(fresh.get("/api/claims").json()) == 25
