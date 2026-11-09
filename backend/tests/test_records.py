from decimal import Decimal
from pathlib import Path

from sqlalchemy import update

from backend import db, payouts, tables

WORDING = (
    Path(__file__).resolve().parents[2] / "data" / "policy_wording.md"
).read_text()


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
