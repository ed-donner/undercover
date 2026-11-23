"""Looking up stored records and the money rules shared by the backend."""

import json
import sqlite3

from fastapi import HTTPException

from backend.models import ClaimState, DecisionRecord, Payment


def load(conn: sqlite3.Connection, table: str, key: str, value: str) -> dict:
    """Return one record from a table, or raise a 404."""
    row = conn.execute(
        f"SELECT data FROM {table} WHERE {key} = ?",  # noqa: S608
        (value,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"No {table[:-1]} {value}")
    return json.loads(row["data"])


def dollars(cents: int) -> float:
    return cents / 100


def cents(amount: float) -> int:
    return round(amount * 100)


def money(amount_cents: int) -> str:
    return f"${dollars(amount_cents):,.2f}"


def payout_limit_cents(conn: sqlite3.Connection) -> int:
    """Return the payout above which a handler must sign off, in cents."""
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'payout_approval_limit_cents'"
    ).fetchone()
    return int(row["value"])


def find_decision(conn: sqlite3.Connection, claim_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM decisions WHERE claim_id = ?", (claim_id,)
    ).fetchone()


def find_payment(conn: sqlite3.Connection, claim_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM payments WHERE claim_id = ?", (claim_id,)
    ).fetchone()


def decision_record(row: sqlite3.Row) -> DecisionRecord:
    return DecisionRecord(
        decision=row["decision"],
        payout=dollars(row["payout_cents"]),
        explanation=row["explanation"],
        policy_section=row["policy_section"],
        decided_at=row["decided_at"],
    )


def payment_record(row: sqlite3.Row) -> Payment:
    return Payment(
        amount=dollars(row["amount_cents"]),
        signed_off_by=row["signed_off_by"],
        paid_at=row["paid_at"],
    )


def needs_sign_off(conn: sqlite3.Connection, decision: sqlite3.Row) -> bool:
    """Whether a decision is an approval over the limit."""
    return decision["decision"] == "approve" and decision[
        "payout_cents"
    ] > payout_limit_cents(conn)


def claim_state(conn: sqlite3.Connection, claim_id: str) -> ClaimState:
    """Work out where a claim stands from what is recorded about it."""
    decision = find_decision(conn, claim_id)
    if decision is None:
        running = conn.execute(
            "SELECT 1 FROM runs WHERE claim_id = ? AND status = 'running'", (claim_id,)
        ).fetchone()
        return "in progress" if running else "waiting"
    if needs_sign_off(conn, decision) and find_payment(conn, claim_id) is None:
        return "waiting for sign-off"
    return "decided"
