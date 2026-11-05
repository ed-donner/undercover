"""The UnderCover backend's data layer: SQLite, seeded from data/."""

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from fastapi import HTTPException

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

_lock = threading.Lock()
_state: dict[str, sqlite3.Connection | None] = {"connection": None}

SCHEMA = """
CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    claim_type TEXT NOT NULL,
    submitted_on TEXT NOT NULL,
    incident_date TEXT NOT NULL,
    incident_location TEXT NOT NULL,
    summary TEXT NOT NULL,
    story TEXT NOT NULL,
    items TEXT NOT NULL,
    amount_claimed REAL NOT NULL,
    documents TEXT NOT NULL,
    status TEXT NOT NULL,
    decision TEXT,
    payout REAL,
    reason TEXT,
    reference TEXT,
    decided_at TEXT,
    signed_off_by TEXT,
    signed_off_at TEXT,
    paid_amount REAL,
    paid_at TEXT
);

CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    date_of_birth TEXT NOT NULL,
    address TEXT NOT NULL,
    customer_since TEXT NOT NULL,
    previous_claims TEXT NOT NULL
);

CREATE TABLE policies (
    policy_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    plan TEXT NOT NULL,
    add_ons TEXT NOT NULL,
    purchased_on TEXT NOT NULL,
    sold_through TEXT NOT NULL,
    trip TEXT NOT NULL,
    travelers TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE plans (
    plan TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    trip_cancellation_max REAL NOT NULL,
    trip_delay_waiting_hours REAL NOT NULL,
    trip_delay_max REAL NOT NULL,
    baggage_delay_waiting_hours REAL NOT NULL,
    baggage_delay_max REAL NOT NULL,
    baggage_max REAL NOT NULL,
    per_item_limit REAL NOT NULL,
    passport_max REAL NOT NULL,
    emergency_medical_max REAL NOT NULL,
    deductible REAL NOT NULL
);

CREATE TABLE handlers (
    handler_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    email TEXT NOT NULL,
    can_approve_over_limit INTEGER NOT NULL
);

CREATE TABLE claim_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def get_connection() -> sqlite3.Connection:
    """Return the backend's one shared SQLite connection, seeding it on first use."""
    if _state["connection"] is None:
        _state["connection"] = sqlite3.connect(":memory:", check_same_thread=False)
        _state["connection"].row_factory = sqlite3.Row
        reset_database()
    return _state["connection"]


def reset_database() -> None:
    """Drop and recreate every table, then reseed it from data/."""
    if _state["connection"] is None:
        _state["connection"] = sqlite3.connect(":memory:", check_same_thread=False)
        _state["connection"].row_factory = sqlite3.Row
    with _lock, _state["connection"] as conn:
        conn.executescript(
            "DROP TABLE IF EXISTS claims;"
            "DROP TABLE IF EXISTS customers;"
            "DROP TABLE IF EXISTS policies;"
            "DROP TABLE IF EXISTS plans;"
            "DROP TABLE IF EXISTS handlers;"
            "DROP TABLE IF EXISTS claim_events;"
        )
        conn.executescript(SCHEMA)
        _seed(conn)


def _load(name: str) -> Any:
    with (DATA_DIR / name).open() as f:
        return json.load(f)


def _seed(conn: sqlite3.Connection) -> None:
    for claim in _load("claims.json"):
        conn.execute(
            """
            INSERT INTO claims (
                claim_id, policy_id, customer_id, claim_type, submitted_on,
                incident_date, incident_location, summary, story, items,
                amount_claimed, documents, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'waiting')
            """,
            (
                claim["claim_id"],
                claim["policy_id"],
                claim["customer_id"],
                claim["claim_type"],
                claim["submitted_on"],
                claim["incident_date"],
                claim["incident_location"],
                claim["summary"],
                claim["story"],
                json.dumps(claim["items"]),
                claim["amount_claimed"],
                json.dumps(claim["documents"]),
            ),
        )

    for customer in _load("customers.json"):
        conn.execute(
            """
            INSERT INTO customers (
                customer_id, name, email, phone, date_of_birth,
                address, customer_since, previous_claims
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                customer["customer_id"],
                customer["name"],
                customer["email"],
                customer["phone"],
                customer["date_of_birth"],
                json.dumps(customer["address"]),
                customer["customer_since"],
                json.dumps(customer["previous_claims"]),
            ),
        )

    for policy in _load("policies.json"):
        conn.execute(
            """
            INSERT INTO policies (
                policy_id, customer_id, plan, add_ons, purchased_on,
                sold_through, trip, travelers, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                policy["policy_id"],
                policy["customer_id"],
                policy["plan"],
                json.dumps(policy["add_ons"]),
                policy["purchased_on"],
                policy["sold_through"],
                json.dumps(policy["trip"]),
                json.dumps(policy["travelers"]),
                policy["status"],
            ),
        )

    for plan in _load("plans.json")["plans"]:
        conn.execute(
            """
            INSERT INTO plans (
                plan, name, trip_cancellation_max, trip_delay_waiting_hours,
                trip_delay_max, baggage_delay_waiting_hours, baggage_delay_max,
                baggage_max, per_item_limit, passport_max,
                emergency_medical_max, deductible
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan["plan"],
                plan["name"],
                plan["trip_cancellation_max"],
                plan["trip_delay_waiting_hours"],
                plan["trip_delay_max"],
                plan["baggage_delay_waiting_hours"],
                plan["baggage_delay_max"],
                plan["baggage_max"],
                plan["per_item_limit"],
                plan["passport_max"],
                plan["emergency_medical_max"],
                plan["deductible"],
            ),
        )

    for handler in _load("handlers.json"):
        conn.execute(
            """
            INSERT INTO handlers (handler_id, name, role, email, can_approve_over_limit)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                handler["handler_id"],
                handler["name"],
                handler["role"],
                handler["email"],
                handler["can_approve_over_limit"],
            ),
        )


def payout_approval_limit() -> float:
    """Return the payout above which a claim needs a handler's sign-off."""
    return float(_load("company.json")["payout_approval_limit"])


def policy_wording() -> str:
    """Return the text of the policy wording."""
    return (DATA_DIR / "policy_wording.md").read_text()


def agent_instructions() -> str:
    """Return the agent's instructions."""
    path = Path(__file__).resolve().parent / "agent_instructions.md"
    return path.read_text()


def fetch_claims() -> list[sqlite3.Row]:
    """Return every claim in the queue."""
    return get_connection().execute("SELECT * FROM claims ORDER BY claim_id").fetchall()


def fetch_claim(claim_id: str) -> sqlite3.Row | None:
    """Return one claim, or None if it does not exist."""
    return (
        get_connection()
        .execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,))
        .fetchone()
    )


def require_claim(claim_id: str) -> sqlite3.Row:
    """Return one claim, or raise a 404 if it does not exist."""
    row = fetch_claim(claim_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
    return row


def fetch_customer(customer_id: str) -> sqlite3.Row | None:
    """Return one customer, or None if it does not exist."""
    return (
        get_connection()
        .execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))
        .fetchone()
    )


def fetch_policy(policy_id: str) -> sqlite3.Row | None:
    """Return one policy, or None if it does not exist."""
    return (
        get_connection()
        .execute("SELECT * FROM policies WHERE policy_id = ?", (policy_id,))
        .fetchone()
    )


def fetch_plan(plan: str) -> sqlite3.Row | None:
    """Return one plan's limits, or None if it does not exist."""
    query = "SELECT * FROM plans WHERE plan = ?"
    return get_connection().execute(query, (plan,)).fetchone()


def fetch_handlers() -> list[sqlite3.Row]:
    """Return every claims handler."""
    query = "SELECT * FROM handlers ORDER BY handler_id"
    return get_connection().execute(query).fetchall()


def fetch_handler(handler_id: str) -> sqlite3.Row | None:
    """Return one handler, or None if it does not exist."""
    return (
        get_connection()
        .execute("SELECT * FROM handlers WHERE handler_id = ?", (handler_id,))
        .fetchone()
    )


def fetch_events(claim_id: str) -> list[sqlite3.Row]:
    """Return a claim's event log, in order."""
    return (
        get_connection()
        .execute(
            "SELECT * FROM claim_events WHERE claim_id = ? ORDER BY id", (claim_id,)
        )
        .fetchall()
    )


def insert_event(
    claim_id: str, operation_id: str, message: str, created_at: str
) -> None:
    """Record one step the agent or a handler took on a claim."""
    with _lock, get_connection() as conn:
        conn.execute(
            """
            INSERT INTO claim_events (claim_id, operation_id, message, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (claim_id, operation_id, message, created_at),
        )


def update_claim(claim_id: str, **fields: Any) -> None:
    """Update one or more fields on a claim. Field names are ours, never a user's."""
    assignments = ", ".join(f"{field} = ?" for field in fields)
    query = f"UPDATE claims SET {assignments} WHERE claim_id = ?"  # noqa: S608
    with _lock, get_connection() as conn:
        conn.execute(query, (*fields.values(), claim_id))
