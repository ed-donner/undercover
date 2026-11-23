"""The SQLite database."""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

DEFAULT_PATH = Path(__file__).parent / "undercover.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS plans (plan TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS policies (policy_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customers (customer_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS handlers (handler_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS claims (claim_id TEXT PRIMARY KEY, data TEXT NOT NULL);
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
