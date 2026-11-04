"""SQLite access and the claim status rules."""

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException

DATA = Path(__file__).parent.parent / "data"
MAX_ATTEMPTS = 2
SUMMARY_LENGTH = 500

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY, data TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'waiting', attempts INTEGER NOT NULL DEFAULT 0,
    signed_off_by TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS policies (policy_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customers (customer_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions (
    claim_id TEXT PRIMARY KEY, decision TEXT NOT NULL, payout REAL NOT NULL,
    section TEXT NOT NULL, reason TEXT NOT NULL, decided_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS payments (
    claim_id TEXT PRIMARY KEY, amount REAL NOT NULL, paid_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT, claim_id TEXT NOT NULL,
    tool TEXT NOT NULL, summary TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reads (
    claim_id TEXT NOT NULL, document TEXT NOT NULL, number INTEGER NOT NULL,
    title TEXT NOT NULL, PRIMARY KEY (claim_id, document, number));
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, cap INTEGER NOT NULL,
    claim_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'running',
    summary TEXT NOT NULL DEFAULT '', started_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS run_claims (
    run_id INTEGER NOT NULL, claim_id TEXT NOT NULL, PRIMARY KEY (run_id, claim_id));
CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL,
    text TEXT NOT NULL, state TEXT NOT NULL, claim_id TEXT NOT NULL);
"""

TABLES = [
    "claims",
    "policies",
    "customers",
    "decisions",
    "payments",
    "steps",
    "reads",
    "runs",
    "run_claims",
    "todos",
]


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open the database, commit on success and close."""
    conn = sqlite3.connect(os.getenv("UNDERCOVER_DB", "undercover.db"), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            conn.executescript(SCHEMA)
            yield conn
    finally:
        conn.close()


def now() -> str:
    """Return the current time in UTC."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def claim_row(conn: sqlite3.Connection, claim_id: str) -> sqlite3.Row:
    """Return a claim row or answer 404."""
    row = conn.execute("SELECT * FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"No claim {claim_id}")
    return row


def log_step(conn: sqlite3.Connection, claim_id: str, tool: str, summary: str) -> None:
    """Add a step to a claim."""
    conn.execute(
        "INSERT INTO steps (claim_id, tool, summary, at) VALUES (?, ?, ?, ?)",
        (claim_id, tool, summary[:SUMMARY_LENGTH], now()),
    )


def load_json(name: str) -> Any:
    """Read one of the business data files."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def payout_limit() -> float:
    """Return the payout above which a handler must sign off."""
    return float(load_json("company.json")["payout_approval_limit"])


def set_todo_state(
    conn: sqlite3.Connection, claim_id: str, state: str, from_states: tuple[str, ...]
) -> None:
    """Move a claim's to-do items from the given states to a new one."""
    marks = ",".join("?" * len(from_states))
    conn.execute(
        f"UPDATE todos SET state=? WHERE claim_id=? AND state IN ({marks})",  # noqa: S608
        (state, claim_id, *from_states),
    )


def requeue(conn: sqlite3.Connection, claim_id: str) -> str:
    """Put an in-progress claim back in the queue, or leave it for a handler."""
    row = conn.execute(
        "SELECT status, attempts FROM claims WHERE claim_id=?", (claim_id,)
    ).fetchone()
    if row is None or row["status"] != "in_progress":
        return "" if row is None else row["status"]
    if row["attempts"] < MAX_ATTEMPTS:
        status, todo = "waiting", "todo"
    else:
        status, todo = "left_for_handler", "left_for_handler"
    conn.execute("UPDATE claims SET status=? WHERE claim_id=?", (status, claim_id))
    set_todo_state(conn, claim_id, todo, ("todo", "in_progress"))
    return status


def sweep_stuck(conn: sqlite3.Connection) -> None:
    """Requeue every claim left in progress by a run that is over."""
    for row in conn.execute("SELECT claim_id FROM claims WHERE status='in_progress'"):
        requeue(conn, row["claim_id"])
