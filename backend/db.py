"""SQLite storage for the backend."""

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB_PATH = Path(os.getenv("UNDERCOVER_DB", ROOT / "backend" / "undercover.db"))

TABLES = ["claims", "records", "steps", "runs", "run_claims", "todos"]
SCHEMA = """
CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'waiting',
    decision TEXT,
    payout REAL,
    reason TEXT,
    policy_section TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    paid REAL,
    signed_off_by TEXT
);
CREATE TABLE records (
    kind TEXT NOT NULL,
    id TEXT NOT NULL,
    body TEXT NOT NULL,
    PRIMARY KEY (kind, id)
);
CREATE TABLE steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cap INTEGER NOT NULL,
    summary TEXT,
    finished INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE run_claims (
    run_id INTEGER NOT NULL,
    claim_id TEXT NOT NULL,
    PRIMARY KEY (run_id, claim_id)
);
CREATE TABLE todos (
    run_id INTEGER NOT NULL,
    position INTEGER NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL,
    PRIMARY KEY (run_id, position)
);
"""


def load(name: str) -> Any:  # noqa: ANN401
    """Read a JSON file from the data folder."""
    return json.loads((DATA / name).read_text())


def connect() -> sqlite3.Connection:
    """Open a connection to the database."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def session() -> Iterator[sqlite3.Connection]:
    """Open a connection that commits when the block ends."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def seed(conn: sqlite3.Connection) -> None:
    """Reset the database to the claims queue and records in data/."""
    for table in TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table}")  # noqa: S608
    conn.executescript(SCHEMA)
    for claim in load("claims.json"):
        conn.execute(
            "INSERT INTO claims (claim_id, body) VALUES (?, ?)",
            (claim["claim_id"], json.dumps(claim)),
        )
    records = {
        "policy": ("policies.json", "policy_id"),
        "customer": ("customers.json", "customer_id"),
        "handler": ("handlers.json", "handler_id"),
    }
    for kind, (name, key) in records.items():
        for row in load(name):
            conn.execute(
                "INSERT INTO records VALUES (?, ?, ?)",
                (kind, row[key], json.dumps(row)),
            )
    for plan in load("plans.json")["plans"]:
        conn.execute(
            "INSERT INTO records VALUES ('plan', ?, ?)",
            (plan["plan"], json.dumps(plan)),
        )
    conn.execute(
        "INSERT INTO records VALUES ('company', 'company', ?)",
        (json.dumps(load("company.json")),),
    )
    conn.commit()


def is_seeded(conn: sqlite3.Connection) -> bool:
    """Say whether the database already holds claims."""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE name = 'claims'"
    ).fetchone()
    return row is not None
