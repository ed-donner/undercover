"""The UnderCover database: SQLite, seeded from the business data in data/."""

import json
import os
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DEFAULT_PATH = ROOT / "backend" / "undercover.db"

RECORD_FILES = {
    "claims": DATA / "claims.json",
    "policies": DATA / "policies.json",
    "customers": DATA / "customers.json",
    "handlers": DATA / "handlers.json",
}
SETTING_FILES = {
    "plans": DATA / "plans.json",
    "company": DATA / "company.json",
    "policy_wording": DATA / "policy_wording.md",
}
SEED_FILES = [*RECORD_FILES.values(), *SETTING_FILES.values()]

SCHEMA = """
CREATE TABLE claims (
    id TEXT PRIMARY KEY,
    record TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'waiting',
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
CREATE TABLE policies (id TEXT PRIMARY KEY, record TEXT NOT NULL);
CREATE TABLE customers (id TEXT PRIMARY KEY, record TEXT NOT NULL);
CREATE TABLE handlers (id TEXT PRIMARY KEY, record TEXT NOT NULL);
CREATE TABLE settings (name TEXT PRIMARY KEY, content TEXT NOT NULL);
CREATE TABLE steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

ID_FIELDS = {
    "claims": "claim_id",
    "policies": "policy_id",
    "customers": "customer_id",
    "handlers": "handler_id",
}


def path() -> Path:
    """Return the database path, from UNDERCOVER_DB if set."""
    return Path(os.getenv("UNDERCOVER_DB", str(DEFAULT_PATH)))


def now() -> str:
    """Return the current time in UTC as an ISO string."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    """Open a connection that returns rows by column name."""
    connection = sqlite3.connect(path(), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def connection() -> Iterator[sqlite3.Connection]:
    """Yield a connection for one request, committing at the end."""
    db = connect()
    try:
        yield db
        db.commit()
    finally:
        db.close()


def seed() -> None:
    """Rebuild the database from the files in SEED_FILES."""
    path().unlink(missing_ok=True)
    db = connect()
    db.executescript(SCHEMA)
    for table, file in RECORD_FILES.items():
        records = json.loads(file.read_text(encoding="utf-8"))
        rows = [(r[ID_FIELDS[table]], json.dumps(r)) for r in records]
        db.executemany(f"INSERT INTO {table} (id, record) VALUES (?, ?)", rows)  # noqa: S608
    for name, file in SETTING_FILES.items():
        db.execute(
            "INSERT INTO settings VALUES (?, ?)",
            (name, file.read_text(encoding="utf-8")),
        )
    db.commit()
    db.close()


def setting(db: sqlite3.Connection, name: str) -> str:
    """Return a setting's content."""
    return db.execute(
        "SELECT content FROM settings WHERE name = ?", (name,)
    ).fetchone()[0]
