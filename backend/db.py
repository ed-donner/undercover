"""Claim status: the only mutable state, kept in SQLite."""

import os
import sqlite3
from pathlib import Path

from backend.data import CLAIMS

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "undercover.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    decision TEXT,
    payout REAL,
    reason TEXT,
    policy_reference TEXT,
    decided_on TEXT,
    over_approval_limit INTEGER,
    signed_off_by TEXT,
    signed_off_on TEXT,
    paid_amount REAL,
    paid_on TEXT
);

CREATE TABLE IF NOT EXISTS claim_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    recorded_on TEXT NOT NULL,
    text TEXT NOT NULL
);
"""


def db_path() -> Path:
    """Return the SQLite file to use, from DATABASE_PATH or the default."""
    return Path(os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH))


def connect() -> sqlite3.Connection:
    """Open a connection to the claim database, creating and seeding it if needed."""
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    seeded = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    if seeded == 0:
        conn.executemany(
            "INSERT INTO claims (claim_id, status) VALUES (?, 'waiting')",
            [(claim_id,) for claim_id in CLAIMS],
        )
        conn.commit()
    return conn
