from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from sqlalchemy import func, select

from backend import db, tables


def count(conn, table):
    return conn.execute(select(func.count()).select_from(table)).scalar_one()


def test_a_new_database_holds_every_record(client):
    with db.connection() as conn:
        counts = {
            table.name: count(conn, table)
            for table in (
                tables.claims,
                tables.policies,
                tables.customers,
                tables.plans,
                tables.add_ons,
                tables.handlers,
            )
        }
        sections = {
            row.document: row.n
            for row in conn.execute(
                select(
                    tables.document_sections.c.document,
                    func.count().label("n"),
                ).group_by(tables.document_sections.c.document)
            )
        }
    assert counts == {
        "claims": 25,
        "policies": 50,
        "customers": 49,
        "plans": 3,
        "add_ons": 3,
        "handlers": 3,
    }
    assert set(sections) == {"policy_wording", "claims_manual"}
    assert all(n > 3 for n in sections.values())


def test_amounts_come_back_exact(client):
    with db.connection() as conn:
        trip = conn.execute(
            select(tables.policies.c.trip).where(
                tables.policies.c.policy_id == "POL-2001"
            )
        ).scalar_one()
        item = conn.execute(
            select(tables.claims.c["items"]).where(
                tables.claims.c.claim_id == "CLM-1001"
            )
        ).scalar_one()[0]
        limit = conn.execute(
            select(tables.settings.c.value).where(
                tables.settings.c.key == "payout_approval_limit"
            )
        ).scalar_one()
    assert trip["trip_cost"] == Decimal("3100.00")
    assert item["amount"] == Decimal("245.00")
    assert limit == "1000.00"


def test_starting_again_adds_nothing(client):
    db.forget_engines()
    with db.connection() as conn:
        assert count(conn, tables.policies) == 50


def test_requests_racing_for_a_new_database_share_one_engine(tmp_path):
    url = f"sqlite:///{tmp_path / 'race.db'}"
    with ThreadPoolExecutor(8) as pool:
        engines = list(pool.map(lambda _: db.engine(url), range(8)))

    assert len({id(e) for e in engines}) == 1
