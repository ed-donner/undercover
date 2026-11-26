"""The SQLite database behind the backend, seeded from data/."""

import json
import os
import sqlite3
import threading
from pathlib import Path

DATA = Path(__file__).parent.parent / "data"
DEFAULT_DB = Path(__file__).parent / "undercover.db"
SEEDING = threading.Lock()

SCHEMA = """
CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY,
    position INTEGER NOT NULL,
    policy_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    data TEXT NOT NULL,
    status TEXT NOT NULL,
    decision TEXT,
    payout REAL,
    reason TEXT,
    policy_section TEXT,
    paid_amount REAL,
    signed_off_by TEXT
);
CREATE TABLE policies (policy_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE customers (customer_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def load(name: str) -> list[dict]:
    """Load a JSON file from data/."""
    return json.loads((DATA / name).read_text())


def db_path() -> Path:
    """Return the database path, from UNDERCOVER_DB if set."""
    return Path(os.getenv("UNDERCOVER_DB") or DEFAULT_DB)


def seed(path: Path) -> None:
    """Create a fresh database at path from the files in data/."""
    path.unlink(missing_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT INTO claims (claim_id, position, policy_id, customer_id, data,"
            " status) VALUES (?, ?, ?, ?, ?, 'waiting')",
            [
                (c["claim_id"], i, c["policy_id"], c["customer_id"], json.dumps(c))
                for i, c in enumerate(load("claims.json"))
            ],
        )
        for table, key, name in [
            ("policies", "policy_id", "policies.json"),
            ("customers", "customer_id", "customers.json"),
        ]:
            conn.executemany(
                f"INSERT INTO {table} VALUES (?, ?)",  # noqa: S608
                [(row[key], json.dumps(row)) for row in load(name)],
            )
    conn.close()


def connect() -> sqlite3.Connection:
    """Open the database, seeding it first if it does not exist."""
    path = db_path()
    with SEEDING:
        if not path.exists():
            seed(path)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
