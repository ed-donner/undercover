"""The UnderCover database: SQLite, seeded from data/ on first start."""

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_DB = Path(__file__).parent / "undercover.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS handlers (
    handler_id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
    can_approve_over_limit INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS customers (customer_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS policies (policy_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, status TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS steps (
    step_id INTEGER PRIMARY KEY AUTOINCREMENT, claim_id TEXT NOT NULL,
    kind TEXT NOT NULL, content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS decisions (
    claim_id TEXT PRIMARY KEY, decision TEXT NOT NULL, payout REAL NOT NULL,
    calculation TEXT NOT NULL, reasons TEXT NOT NULL, policy_section TEXT NOT NULL,
    decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sign_offs (
    claim_id TEXT PRIMARY KEY, handler_id TEXT NOT NULL,
    signed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS payments (
    claim_id TEXT PRIMARY KEY, amount REAL NOT NULL,
    paid_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def path() -> Path:
    """Return the database file, from UNDERCOVER_DB if set."""
    return Path(os.getenv("UNDERCOVER_DB", str(DEFAULT_DB)))


def connect() -> sqlite3.Connection:
    """Open a connection to the database."""
    connection = sqlite3.connect(path(), timeout=10, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def get_db() -> Iterator[sqlite3.Connection]:
    """Give a request a connection, committing when it succeeds."""
    with closing(connect()) as connection:
        yield connection
        connection.commit()


def load(name: str) -> Any:
    """Read one of the seed files in data/."""
    text = (DATA_DIR / name).read_text(encoding="utf-8")
    return json.loads(text) if name.endswith(".json") else text


def seed(connection: sqlite3.Connection) -> None:
    """Load UnderCover's records from the six seed files and the policy wording."""
    for key, name in [
        ("company", "company.json"),
        ("plans", "plans.json"),
        ("policy_wording", "policy_wording.md"),
    ]:
        connection.execute(
            "INSERT INTO settings VALUES (?, ?)", (key, json.dumps(load(name)))
        )
    connection.executemany(
        "INSERT INTO handlers VALUES (:handler_id, :name, :role, "
        ":can_approve_over_limit)",
        load("handlers.json"),
    )
    connection.executemany(
        "INSERT INTO customers VALUES (?, ?)",
        [(c["customer_id"], json.dumps(c)) for c in load("customers.json")],
    )
    connection.executemany(
        "INSERT INTO policies VALUES (?, ?)",
        [(p["policy_id"], json.dumps(p)) for p in load("policies.json")],
    )
    connection.executemany(
        "INSERT INTO claims VALUES (?, ?, 'waiting', ?)",
        [(c["claim_id"], c["customer_id"], json.dumps(c)) for c in load("claims.json")],
    )


def init() -> None:
    """Create the tables, and seed them if the database is new."""
    path().parent.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as connection:
        connection.executescript(SCHEMA)
        if not connection.execute("SELECT 1 FROM settings").fetchone():
            seed(connection)
        connection.commit()


def setting(connection: sqlite3.Connection, key: str) -> Any:
    """Return one of the stored settings: company, plans or policy_wording."""
    row = connection.execute("SELECT data FROM settings WHERE key = ?", (key,))
    return json.loads(row.fetchone()["data"])
