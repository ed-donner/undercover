"""The SQLite database."""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_PATH = Path(__file__).parent / "undercover.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS plans (plan TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS policies (policy_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customers (customer_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS handlers (handler_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claims (claim_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions (
    claim_id TEXT PRIMARY KEY, decision TEXT NOT NULL, payout_cents INTEGER NOT NULL,
    explanation TEXT NOT NULL, policy_section TEXT NOT NULL, decided_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
    claim_id TEXT PRIMARY KEY, amount_cents INTEGER NOT NULL,
    signed_off_by TEXT, paid_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT, claim_id TEXT NOT NULL,
    status TEXT NOT NULL, started_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT, claim_id TEXT NOT NULL,
    kind TEXT NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL
);
"""


def db_path() -> Path:
    """Return the database file, which UNDERCOVER_DB can override."""
    return Path(os.getenv("UNDERCOVER_DB", DEFAULT_PATH))


@contextmanager
def session() -> Iterator[sqlite3.Connection]:
    """Open the database for one unit of work, committing it at the end."""
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def now() -> str:
    """Return the current time for a record."""
    return datetime.now(UTC).isoformat(timespec="seconds")
