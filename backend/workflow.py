"""Changing claims: starting, deciding, paying, signing off and recording steps."""

import sqlite3
from datetime import UTC, datetime

from fastapi import HTTPException

from backend import claims
from backend.db import payout_limit
from backend.models import DecisionRequest, Payment, Status, Step, StepRequest

CENT = 0.005


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def status_of(db: sqlite3.Connection, claim_id: str) -> Status:
    row = db.execute(
        "SELECT status FROM claims WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Claim not found")
    return row["status"]


def start(db: sqlite3.Connection, claim_id: str) -> None:
    if status_of(db, claim_id) in ("waiting_for_sign_off", "decided"):
        raise HTTPException(409, "The claim has already been decided")
    with db:
        db.execute(
            "UPDATE claims SET status = 'in_progress' WHERE claim_id = ?", (claim_id,)
        )


def decide(db: sqlite3.Connection, claim_id: str, request: DecisionRequest) -> None:
    if status_of(db, claim_id) != "in_progress":
        raise HTTPException(409, "The claim is not in progress")
    approved = request.decision == "approve"
    if approved != (request.payout > 0):
        raise HTTPException(422, "Only an approve has a payout, and it must be above 0")
    payout = round(request.payout, 2)
    held = approved and payout > payout_limit()
    with db:
        db.execute(
            "INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?)",
            (
                claim_id,
                request.decision,
                payout,
                request.explanation,
                request.policy_section,
                now(),
            ),
        )
        db.execute(
            "UPDATE claims SET status = ? WHERE claim_id = ?",
            ("waiting_for_sign_off" if held else "decided", claim_id),
        )


def insert_payment(db: sqlite3.Connection, claim_id: str, amount: float) -> Payment:
    """Check the payment rule and record the payment, without committing."""
    status_of(db, claim_id)
    decision = claims.one_decision(db, claim_id)
    if decision is None or decision.decision != "approve":
        raise HTTPException(409, "The claim has no approved decision")
    if claims.one_payment(db, claim_id):
        raise HTTPException(409, "The claim has already been paid")
    if abs(amount - decision.payout) > CENT:
        raise HTTPException(
            409, f"The amount must equal the payout of {decision.payout:.2f}"
        )
    if decision.payout > payout_limit() and claims.one_sign_off(db, claim_id) is None:
        raise HTTPException(
            409, "The payout is over the limit and needs a handler's sign-off"
        )
    payment = Payment(amount=decision.payout, paid_at=now())
    db.execute(
        "INSERT INTO payments VALUES (?, ?, ?)",
        (claim_id, payment.amount, payment.paid_at),
    )
    return payment


def pay(db: sqlite3.Connection, claim_id: str, amount: float) -> Payment:
    with db:
        return insert_payment(db, claim_id, amount)


def sign_off(db: sqlite3.Connection, claim_id: str, handler_id: str) -> None:
    if status_of(db, claim_id) != "waiting_for_sign_off":
        raise HTTPException(409, "The claim is not waiting for sign-off")
    handler = next((h for h in claims.handlers(db) if h.handler_id == handler_id), None)
    if handler is None:
        raise HTTPException(404, "Handler not found")
    if not handler.can_approve_over_limit:
        raise HTTPException(403, "The handler cannot sign off payouts over the limit")
    payout = db.execute(
        "SELECT payout FROM decisions WHERE claim_id = ?", (claim_id,)
    ).fetchone()["payout"]
    with db:
        db.execute(
            "INSERT INTO sign_offs VALUES (?, ?, ?)", (claim_id, handler_id, now())
        )
        db.execute(
            "UPDATE claims SET status = 'decided' WHERE claim_id = ?", (claim_id,)
        )
        insert_payment(db, claim_id, payout)


def add_step(db: sqlite3.Connection, claim_id: str, request: StepRequest) -> Step:
    status_of(db, claim_id)
    created_at = now()
    with db:
        cursor = db.execute(
            "INSERT INTO steps (claim_id, kind, text, created_at) VALUES (?, ?, ?, ?)",
            (claim_id, request.kind, request.text, created_at),
        )
    return Step(
        id=cursor.lastrowid or 0,
        kind=request.kind,
        text=request.text,
        created_at=created_at,
    )


def steps(db: sqlite3.Connection, claim_id: str) -> list[Step]:
    status_of(db, claim_id)
    rows = db.execute(
        "SELECT id, kind, text, created_at FROM steps WHERE claim_id = ? ORDER BY id",
        (claim_id,),
    ).fetchall()
    return [Step(**row) for row in rows]


def claim_next_waiting(db: sqlite3.Connection) -> str | None:
    """Take the first waiting claim, marking it in progress, or return None."""
    with db:
        row = db.execute(
            "SELECT claim_id FROM claims WHERE status = 'waiting' ORDER BY claim_id"
        ).fetchone()
        if row is None:
            return None
        db.execute(
            "UPDATE claims SET status = 'in_progress' WHERE claim_id = ?",
            (row["claim_id"],),
        )
    return row["claim_id"]
