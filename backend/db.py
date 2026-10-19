"""The SQLite database: connections, schema and seeding from data/."""

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from functools import cache
from pathlib import Path
from typing import Any

DATA = Path(__file__).parent.parent / "data"
DEFAULT_DB = Path(__file__).parent / "undercover.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    claim_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    amount_claimed REAL NOT NULL,
    submitted_on TEXT NOT NULL,
    status TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS policies (
    policy_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS handlers (
    handler_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
    claim_id TEXT PRIMARY KEY,
    decision TEXT NOT NULL,
    payout REAL NOT NULL,
    explanation TEXT NOT NULL,
    policy_section TEXT NOT NULL,
    decided_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
    claim_id TEXT PRIMARY KEY,
    amount REAL NOT NULL,
    paid_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sign_offs (
    claim_id TEXT PRIMARY KEY,
    handler_id TEXT NOT NULL,
    signed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_limit INTEGER NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS todos (
    run_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL,
    PRIMARY KEY (run_id, position)
);
CREATE TABLE IF NOT EXISTS run_claims (
    run_id INTEGER NOT NULL,
    claim_id TEXT NOT NULL,
    PRIMARY KEY (run_id, claim_id)
);
CREATE TABLE IF NOT EXISTS failures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    failed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def load_json(name: str) -> Any:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@cache
def payout_limit() -> float:
    return float(load_json("company.json")["payout_approval_limit"])


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(
        os.getenv("UNDERCOVER_DB", DEFAULT_DB), check_same_thread=False
    )
    conn.row_factory = sqlite3.Row
    return conn


def get_db() -> Iterator[sqlite3.Connection]:
    with closing(connect()) as conn:
        yield conn


def seed(conn: sqlite3.Connection) -> None:
    for claim in load_json("claims.json"):
        conn.execute(
            "INSERT INTO claims VALUES (?, ?, ?, ?, ?, ?, ?, 'waiting', ?)",
            (
                claim["claim_id"],
                claim["customer_id"],
                claim["policy_id"],
                claim["claim_type"],
                claim["summary"],
                claim["amount_claimed"],
                claim["submitted_on"],
                json.dumps(claim),
            ),
        )
    for policy in load_json("policies.json"):
        conn.execute(
            "INSERT INTO policies VALUES (?, ?)",
            (policy["policy_id"], json.dumps(policy)),
        )
    for customer in load_json("customers.json"):
        conn.execute(
            "INSERT INTO customers VALUES (?, ?, ?)",
            (customer["customer_id"], customer["name"], json.dumps(customer)),
        )
    for handler in load_json("handlers.json"):
        conn.execute(
            "INSERT INTO handlers VALUES (?, ?)",
            (handler["handler_id"], json.dumps(handler)),
        )


def init_db() -> None:
    """Create the tables and, on a new database, load the queue."""
    with closing(connect()) as conn, conn:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0:
            seed(conn)
