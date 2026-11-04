import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_the_queue_is_exactly_the_25_claims_in_data():
    claims = client.get("/api/claims").json()
    assert [claim["claim_id"] for claim in claims] == [
        f"CLM-{number}" for number in range(1001, 1026)
    ]
    assert {claim["status"] for claim in claims} == {"waiting"}


def test_the_queue_shows_where_each_claim_stands():
    first = client.get("/api/claims").json()[0]
    assert first == {
        "claim_id": "CLM-1001",
        "claim_type": "trip_delay",
        "summary": "Flight home canceled by the airline, rebooked the next morning",
        "submitted_on": "2026-06-24",
        "amount_claimed": 420.0,
        "status": "waiting",
        "decision": None,
        "payout": None,
        "paid_amount": None,
        "customer_name": "Maya Patel",
    }


def test_get_claim():
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["story"].startswith("My flight home from Rome")
    assert len(claim["items"]) == 3
    assert len(claim["documents"]) == 4
    assert claim["amount_claimed"] == 420.0
    assert claim["status"] == "waiting"
    assert claim["decision"] is None
    assert claim["paid_amount"] is None


def test_get_policy_with_its_plan():
    policy = client.get("/api/policies/POL-2001").json()
    assert policy["plan"] == "premium"
    assert policy["plan_details"]["deductible"] == 50.0
    assert policy["plan_details"]["per_item_limit"] == 300.0
    assert policy["plan_details"]["trip_delay_max"] == 800.0
    assert policy["add_on_details"] == []


def test_get_policy_with_an_add_on():
    policy = client.get("/api/policies/POL-2009").json()
    assert policy["add_on_details"] == [
        {
            "add_on": "electronics_plus",
            "name": "Electronics Plus",
            "effect": "Raises the per-item limit for electronics to the amount below.",
            "electronics_per_item_limit": 1200.0,
        }
    ]


def test_get_customer_with_claim_history():
    customer = client.get("/api/customers/CUS-3001").json()
    assert customer["name"] == "Maya Patel"
    assert [claim["claim_id"] for claim in customer["previous_claims"]] == ["CLM-0412"]


def test_list_handlers():
    handlers = client.get("/api/handlers").json()
    assert [handler["name"] for handler in handlers] == [
        "Dana Whitfield",
        "Marcus Oyelaran",
        "Priya Raman",
    ]


def test_get_policy_wording():
    wording = client.get("/api/policy-wording").json()
    assert wording["version"] == "2026.1"
    assert wording["text"].startswith("# UnderCover Travel Insurance: Policy Wording")


@pytest.mark.parametrize(
    "url",
    ["/api/claims/CLM-9999", "/api/policies/POL-9999", "/api/customers/CUS-9999"],
)
def test_unknown_records_are_not_found(url):
    response = client.get(url)
    assert response.status_code == 404
    assert response.json()["detail"].startswith("There is no ")
