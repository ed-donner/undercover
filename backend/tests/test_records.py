import json
from decimal import Decimal
from pathlib import Path

from sqlalchemy import update

from backend import db, payouts, tables

DATA = Path(__file__).resolve().parents[2] / "data"
WORDING = (DATA / "policy_wording.md").read_text()


def test_the_approval_limit_follows_the_database(client):
    assert not payouts.needs_sign_off(Decimal("600.00"))

    with db.connection() as conn:
        conn.execute(
            update(tables.settings)
            .where(tables.settings.c.key == "payout_approval_limit")
            .values(value="500.00")
        )

    assert payouts.needs_sign_off(Decimal("600.00"))


def test_a_section_is_the_wording_in_the_file(client):
    headings = client.get("/api/documents/policy_wording/sections").json()
    assert "Trip Delay" in " ".join(headings)

    for heading in headings:
        response = client.get(
            "/api/documents/policy_wording/section", params={"heading": heading}
        )
        assert response.json()["text"] in WORDING


def test_only_handlers_who_can_sign_off_are_listed(client):
    handlers = client.get("/api/handlers").json()
    assert [h["handler_id"] for h in handlers] == ["HND-01", "HND-02", "HND-03"]


def test_a_claim_comes_with_its_policy_and_the_customers_history(client):
    claim = client.get("/api/claims/CLM-1001").json()

    assert claim["policy"]["policy_id"] == "POL-2001"
    assert claim["policy"]["trip"]["trip_cost"] == "3100.00"
    previous = [c["claim_id"] for c in claim["customer_previous_claims"]]
    assert previous == [c["claim_id"] for c in customer_claims("CUS-3001")]


def customer_claims(customer_id):
    customers = json.loads((DATA / "customers.json").read_text())
    return next(c for c in customers if c["customer_id"] == customer_id)[
        "previous_claims"
    ]
