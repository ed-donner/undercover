"""Loads UnderCover's records from data/ into the database."""

import json
import sqlite3
from pathlib import Path

from backend.db import SCHEMA, session

DATA = Path(__file__).parent.parent / "data"
SEED_FILES = (
    "company.json",
    "plans.json",
    "policies.json",
    "customers.json",
    "handlers.json",
    "claims.json",
    "policy_wording.md",
)


def read_seed(name: str) -> str:
    """Read one of the seed files. Only SEED_FILES are ever read."""
    return (DATA / name).read_text(encoding="utf-8")


def insert_rows(conn: sqlite3.Connection, table: str, key: str, rows: list[dict]):
    """Insert each record as JSON, keyed by its id."""
    conn.executemany(
        f"INSERT INTO {table} ({key}, data) VALUES (?, ?)",  # noqa: S608
        [(row[key], json.dumps(row)) for row in rows],
    )


def seed(conn: sqlite3.Connection):
    """Fill an empty database from the seed files."""
    company = json.loads(read_seed("company.json"))
    limit_cents = round(company["payout_approval_limit"] * 100)
    conn.executemany(
        "INSERT INTO settings (key, value) VALUES (?, ?)",
        [
            ("payout_approval_limit_cents", str(limit_cents)),
            ("policy_wording", read_seed("policy_wording.md")),
        ],
    )
    insert_rows(conn, "plans", "plan", json.loads(read_seed("plans.json"))["plans"])
    for table, key, name in (
        ("policies", "policy_id", "policies.json"),
        ("customers", "customer_id", "customers.json"),
        ("handlers", "handler_id", "handlers.json"),
        ("claims", "claim_id", "claims.json"),
    ):
        insert_rows(conn, table, key, json.loads(read_seed(name)))


def init_db():
    """Create the tables, and load the seed data if the database is new.

    A run still marked running was cut off by a restart, so it is marked failed.
    """
    with session() as conn:
        conn.executescript(SCHEMA)
        conn.execute("UPDATE runs SET status = 'failed' WHERE status = 'running'")
        if conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0:
            seed(conn)
