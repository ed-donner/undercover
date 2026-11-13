import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.store import Store


def test_queue_and_details(client):
    queue = client.get("/api/claims").json()
    assert len(queue) == 25
    assert {row["status"] for row in queue} == {"waiting"}
    assert queue[0]["customer_name"] == "Maya Patel"
    assert queue[0]["amount_claimed"] == 420
    claim = client.get("/api/claims/CLM-1001").json()
    assert "crew problem" in claim["story"]
    assert len(claim["items"]) == 3
    assert "$245.00" in claim["documents"][1]["content"]
    policy = client.get(f"/api/policies/{claim['policy_id']}").json()
    assert policy["trip"]["destination"] == "Rome, Italy"
    plan = client.get(f"/api/plans/{policy['plan']}").json()
    assert plan["plan"]["deductible"] == 50
    assert plan["electronics_per_item_limit"] == 1200
    customer = client.get(f"/api/customers/{claim['customer_id']}").json()
    assert customer["previous_claims"][0]["amount_paid"] == 140
    assert len(client.get("/api/handlers").json()) == 3
    assert client.get("/api/company").json()["payout_approval_limit"] == 1000
    wording = client.get("/api/wording").json()
    assert wording["version"] == "2026.1"
    assert "## 10. How we work out your payment" in wording["text"]
    assert "claims manual" in client.get("/api/instructions").json()["text"]


@pytest.mark.parametrize(
    "path", ["claims/no", "policies/no", "customers/no", "plans/no"]
)
def test_missing_records(client, path):
    assert client.get(f"/api/{path}").status_code == 404
    assert len(client.get("/api/claims").json()) == 25


def test_seed_allowlist_and_persistence(tmp_path, monkeypatch):
    opened = []
    original = Path.read_text

    def track(path, *args, **kwargs):
        opened.append(path.name)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", track)
    db = Store(tmp_path / "records.db")
    db.initialize()
    assert set(opened) == {
        "company.json",
        "plans.json",
        "policies.json",
        "customers.json",
        "handlers.json",
        "claims.json",
        "policy_wording.md",
        "claims_manual.md",
    }
    assert set(db.get("company", "company")) == {
        "name",
        "currency",
        "payout_approval_limit",
        "policy_wording_version",
    }
    with db.transaction() as connection:
        connection.execute("UPDATE claims SET status = 'decided' WHERE id = 'CLM-1001'")
        body = connection.execute(
            "SELECT body FROM records WHERE kind = 'claims' AND id = 'CLM-1001'"
        ).fetchone()["body"]
        assert json.loads(body)["amount_claimed"] == 42000
    opened.clear()
    with TestClient(create_app(db.path)) as reopened:
        assert reopened.get("/api/claims/CLM-1001").json()["status"] == "decided"
        assert len(reopened.get("/api/claims").json()) == 25
    assert not opened


def test_api_contract(client):
    spec = client.get("/openapi.json").json()
    operations = [op for path in spec["paths"].values() for op in path.values()]
    identifiers = [op["operationId"] for op in operations]
    assert len(set(identifiers)) == len(identifiers)
    for operation in operations:
        assert operation["description"]
        assert all(
            parameter["required"] for parameter in operation.get("parameters", [])
        )
        if "requestBody" in operation:
            assert operation["requestBody"]["required"]
    assert set(spec["paths"]["/api/instructions"]) == {"get"}
    assert not any(path.startswith("/__test__/") for path in spec["paths"])
    assert client.post("/__test__/reset").status_code == 404
    for name in ("DecisionInput", "SignOffInput", "PaymentInput", "ActivityInput"):
        if name in spec["components"]["schemas"]:
            schema = spec["components"]["schemas"][name]
            assert set(schema["required"]) == set(schema["properties"])
    assert client.post("/api/instructions", json={"text": "replace"}).status_code == 405
