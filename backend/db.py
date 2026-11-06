"""The UnderCover database, in SQLite."""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

SCHEMA = """
DROP TABLE IF EXISTS runs;
DROP TABLE IF EXISTS steps;
DROP TABLE IF EXISTS claims;
DROP TABLE IF EXISTS policies;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS handlers;

CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY,
    record TEXT NOT NULL,
    status TEXT NOT NULL,
    decision TEXT,
    payout REAL,
    reason TEXT,
    policy_section TEXT,
    decided_at TEXT,
    signed_off_by TEXT,
    signed_off_at TEXT,
    paid_amount REAL,
    paid_at TEXT,
    attempts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE policies (policy_id TEXT PRIMARY KEY, record TEXT NOT NULL);
CREATE TABLE customers (customer_id TEXT PRIMARY KEY, record TEXT NOT NULL);
CREATE TABLE handlers (handler_id TEXT PRIMARY KEY, record TEXT NOT NULL);
CREATE TABLE steps (
    step_id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL REFERENCES claims (claim_id),
    thread_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    todos TEXT NOT NULL DEFAULT '[]',
    summary TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);
"""


def path() -> Path:
    """Return the path of the database file."""
    return Path(os.getenv("UNDERCOVER_DB", Path(__file__).parent / "undercover.db"))


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Open the database for one transaction, committed if nothing goes wrong."""
    connection = sqlite3.connect(path())
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()
