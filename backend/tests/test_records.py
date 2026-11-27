import json
from contextlib import closing
from pathlib import Path

from backend import db

DATA = Path(__file__).parents[2] / "data"


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_list_claims(client):
    claims = client.get("/api/claims").json()
    assert len(claims) == 25
    assert {c["status"] for c in claims} == {"waiting"}
    first = claims[0]
    assert first["claim_id"] == "CLM-1001"
    assert first["customer_name"] == "Maya Patel"
    assert first["amount_claimed"] == 420.0


def test_get_claim(client):
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["story"].startswith("My flight home from Rome")
    assert len(claim["items"]) == 3
    assert claim["documents"][0]["type"] == "carrier_report"
    assert claim["decision"] is None


def test_get_policy_includes_plan(client):
    policy = client.get("/api/policies/POL-2001").json()
    assert policy["plan"] == "premium"
    assert policy["plan_details"]["deductible"] == 50.0
    assert policy["plan_details"]["baggage_max"] == 1500.0
    assert policy["deductible_applies_to"] == ["baggage", "emergency_medical"]


def test_get_policy_includes_add_ons(client):
    policies = json.loads((DATA / "policies.json").read_text(encoding="utf-8"))
    with_add_on = next(p for p in policies if p["add_ons"])
    policy = client.get(f"/api/policies/{with_add_on['policy_id']}").json()
    assert [a["add_on"] for a in policy["add_on_details"]] == with_add_on["add_ons"]


def test_get_customer(client):
    customer = client.get("/api/customers/CUS-3001").json()
    assert customer["name"] == "Maya Patel"
    assert customer["previous_claims"][0]["claim_id"] == "CLM-0412"


def test_get_policy_wording(client):
    text = client.get("/api/policy-wording").json()["text"]
    assert "How we work out your payment" in text


def test_list_handlers(client):
    handlers = client.get("/api/handlers").json()
    assert [h["handler_id"] for h in handlers] == ["HND-01", "HND-02", "HND-03"]
    assert "email" not in handlers[0]


def test_not_found(client):
    assert client.get("/api/claims/CLM-9999").status_code == 404
    assert client.get("/api/policies/POL-9999").status_code == 404
    assert client.get("/api/customers/CUS-9999").status_code == 404


def test_seed_never_reads_evals(tmp_path, monkeypatch):
    read = []
    original = Path.read_text

    def recording_read_text(self, *args, **kwargs):
        read.append(self.resolve())
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", recording_read_text)
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "seed.db"))
    db.init()
    assert read
    assert all("evals" not in p.parts and "security" not in p.parts for p in read)
    assert {p.name for p in read} == {
        "company.json",
        "plans.json",
        "policy_wording.md",
        "handlers.json",
        "customers.json",
        "policies.json",
        "claims.json",
    }


def test_seed_holds_only_queue_claims(client):
    queue = json.loads((DATA / "claims.json").read_text(encoding="utf-8"))
    stored = [c["claim_id"] for c in client.get("/api/claims").json()]
    assert stored == sorted(c["claim_id"] for c in queue)


def test_init_seeds_once(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "once.db"))
    db.init()
    db.init()
    with closing(db.connect()) as connection:
        assert connection.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 25


def test_every_operation_is_documented_with_required_inputs(client):
    schema = client.get("/openapi.json").json()
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            assert operation["operationId"], f"{method} {path}"
            assert operation["summary"], f"{method} {path}"
            assert operation.get("description"), f"{method} {path}"
            for parameter in operation.get("parameters", []):
                assert parameter["required"], f"{method} {path} {parameter['name']}"
            if "requestBody" in operation:
                assert operation["requestBody"]["required"], f"{method} {path}"
    for name, model in schema["components"]["schemas"].items():
        if name.endswith("Input"):
            assert set(model.get("required", [])) == set(model["properties"]), name
