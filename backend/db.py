"""The UnderCover database, seeded from the business data in data/."""

import json
import os
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

DATA = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DB = Path(__file__).resolve().parent / "undercover.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    kind TEXT NOT NULL,
    id TEXT NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (kind, id)
);
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    data TEXT NOT NULL,
    decision TEXT,
    payout REAL,
    reason TEXT,
    policy_section TEXT,
    decided_at TEXT,
    signed_off_by TEXT,
    signed_off_at TEXT,
    paid_amount REAL,
    paid_at TEXT
);
CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

RECORDS = {
    "policy": ("policies.json", "policy_id"),
    "customer": ("customers.json", "customer_id"),
    "handler": ("handlers.json", "handler_id"),
}


def db_path() -> Path:
    """Return the database file, from UNDERCOVER_DB if set."""
    return Path(os.getenv("UNDERCOVER_DB") or DEFAULT_DB)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open the database for one unit of work, committed at the end."""
    connection = sqlite3.connect(db_path())
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def load(name: str) -> Any:
    """Read one JSON file from data/."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def seed(connection: sqlite3.Connection) -> None:
    """Fill an empty database from data/, leaving out data/evals/."""
    rows = [
        (kind, record[key], json.dumps(record))
        for kind, (name, key) in RECORDS.items()
        for record in load(name)
    ]
    rows.append(("settings", "plans", json.dumps(load("plans.json"))))
    rows.append(("settings", "company", json.dumps(load("company.json"))))
    wording = (DATA / "policy_wording.md").read_text(encoding="utf-8")
    rows.append(("settings", "policy_wording", json.dumps(wording)))
    connection.executemany("INSERT INTO records VALUES (?, ?, ?)", rows)
    connection.executemany(
        "INSERT INTO claims (claim_id, status, data) VALUES (?, 'waiting', ?)",
        [(claim["claim_id"], json.dumps(claim)) for claim in load("claims.json")],
    )


def init() -> None:
    """Create the tables and seed them on first start."""
    with connect() as connection:
        connection.executescript(SCHEMA)
        if not connection.execute("SELECT 1 FROM claims LIMIT 1").fetchone():
            seed(connection)


def reset() -> None:
    """Delete the database and seed a fresh one."""
    db_path().unlink(missing_ok=True)
    init()


if __name__ == "__main__":
    if "--reset" in sys.argv:
        reset()
        print(f"Reset {db_path()}")
    else:
        init()
        print(f"Ready {db_path()}")
