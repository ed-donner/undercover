"""Decisions, payments, sign-off and the steps of the agent's work."""

import sqlite3

from fastapi import HTTPException

from backend.db import now
from backend.models import (
    DecisionIn,
    DecisionRecord,
    Payment,
    PaymentIn,
    SignOffIn,
    Step,
    StepIn,
)
from backend.records import (
    cents,
    decision_record,
    find_decision,
    find_payment,
    load,
    money,
    needs_sign_off,
    payment_record,
    payout_limit_cents,
)


def record_decision(
    conn: sqlite3.Connection, claim_id: str, body: DecisionIn
) -> DecisionRecord:
    """Record the decision on a claim, once."""
    load(conn, "claims", "claim_id", claim_id)
    if find_decision(conn, claim_id):
        raise HTTPException(409, f"{claim_id} already has a decision")
    payout = cents(body.payout)
    if body.decision == "approve" and payout <= 0:
        raise HTTPException(422, "An approval needs a payout above zero")
    if body.decision != "approve" and payout != 0:
        raise HTTPException(422, "A decline or referral has a payout of zero")
    conn.execute(
        "INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?)",
        (
            claim_id,
            body.decision,
            payout,
            body.explanation,
            body.policy_section,
            now(),
        ),
    )
    row = conn.execute("SELECT * FROM decisions WHERE claim_id = ?", (claim_id,))
    return decision_record(row.fetchone())


def pay(conn: sqlite3.Connection, claim_id: str, body: PaymentIn) -> Payment:
    """Pay an approved claim, unless it is over the limit and not signed off."""
    decision = find_decision(conn, claim_id)
    if decision is None or decision["decision"] != "approve":
        raise HTTPException(409, f"{claim_id} has no approval to pay")
    if find_payment(conn, claim_id):
        raise HTTPException(409, f"{claim_id} is already paid")
    amount = cents(body.amount)
    if amount != decision["payout_cents"]:
        raise HTTPException(
            409, f"The approved payout is {money(decision['payout_cents'])}"
        )
    if needs_sign_off(conn, decision):
        raise HTTPException(
            409,
            f"{money(amount)} is over the {money(payout_limit_cents(conn))} limit "
            "and waits for a handler's sign-off",
        )
    return insert_payment(conn, claim_id, amount, None)


def sign_off(conn: sqlite3.Connection, claim_id: str, body: SignOffIn) -> Payment:
    """Let a handler sign off a payout over the limit, which pays it."""
    handler = load(conn, "handlers", "handler_id", body.handler_id)
    if not handler["can_approve_over_limit"]:
        raise HTTPException(403, f"{handler['name']} cannot sign off this payout")
    decision = find_decision(conn, claim_id)
    if decision is None or not needs_sign_off(conn, decision):
        raise HTTPException(409, f"{claim_id} has nothing waiting for sign-off")
    if find_payment(conn, claim_id):
        raise HTTPException(409, f"{claim_id} is already paid")
    return insert_payment(conn, claim_id, decision["payout_cents"], body.handler_id)


def insert_payment(
    conn: sqlite3.Connection, claim_id: str, amount: int, handler_id: str | None
) -> Payment:
    conn.execute(
        "INSERT INTO payments VALUES (?, ?, ?, ?)",
        (claim_id, amount, handler_id, now()),
    )
    row = conn.execute("SELECT * FROM payments WHERE claim_id = ?", (claim_id,))
    return payment_record(row.fetchone())


def record_step(conn: sqlite3.Connection, claim_id: str, body: StepIn) -> Step:
    """Record one step of the agent's work on a claim."""
    load(conn, "claims", "claim_id", claim_id)
    cursor = conn.execute(
        "INSERT INTO steps (claim_id, kind, text, created_at) VALUES (?, ?, ?, ?)",
        (claim_id, body.kind, body.text, now()),
    )
    row = conn.execute("SELECT * FROM steps WHERE id = ?", (cursor.lastrowid,))
    return Step(**row.fetchone())


def list_steps(conn: sqlite3.Connection, claim_id: str) -> list[Step]:
    """Return the steps recorded on a claim, oldest first."""
    load(conn, "claims", "claim_id", claim_id)
    rows = conn.execute(
        "SELECT * FROM steps WHERE claim_id = ? ORDER BY id", (claim_id,)
    )
    return [Step(**row) for row in rows]
