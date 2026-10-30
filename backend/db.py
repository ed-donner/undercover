"""Claim status: the only mutable state, kept in SQLite."""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

from backend.data import CLAIMS

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "undercover.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    decision TEXT,
    payout_cents INTEGER,
    reason TEXT,
    policy_reference TEXT,
    decided_on TEXT,
    over_approval_limit INTEGER,
    signed_off_by TEXT,
    signed_off_on TEXT,
    paid_cents INTEGER,
    paid_on TEXT
);

CREATE TABLE IF NOT EXISTS claim_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    recorded_on TEXT NOT NULL,
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_on TEXT NOT NULL,
    finished_on TEXT,
    summary TEXT
);

CREATE TABLE IF NOT EXISTS run_items (
    run_id INTEGER NOT NULL,
    claim_id TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    PRIMARY KEY (run_id, claim_id)
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


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """Open a connection that commits on success, rolls back on error, and closes."""
    with closing(connect()) as conn, conn:
        yield conn


def now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()
