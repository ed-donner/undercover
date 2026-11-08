"""A claim's state: its row, its steps, its sign-off and its payment."""

from decimal import Decimal
from typing import Any

from sqlalchemy import insert, or_, select, update

from backend import data, db, money, payouts
from backend.data import CLAIM_IDS_BY_SUBMITTED_ON, CLAIMS, CUSTOMERS, POLICIES
from backend.errors import Conflict, NotFound


def get_row(claim_id: str) -> dict[str, Any]:
    """Return a claim's mutable state, or raise NotFound."""
    with db.connection() as conn:
        row = conn.execute(
            select(db.claims).where(db.claims.c.claim_id == claim_id)
        ).one_or_none()
    if row is None:
        raise NotFound(f"No claim {claim_id}")
    return _with_dollars(dict(row._mapping))


def _with_dollars(row: dict[str, Any]) -> dict[str, Any]:
    """Swap the `*_cents` columns for `Decimal` dollars, under the wire names."""
    for column, name in (("payout_cents", "payout"), ("paid_cents", "paid_amount")):
        cents = row.pop(column)
        row[name] = None if cents is None else money.from_cents(cents)
    return row


def list_summaries() -> list[dict[str, Any]]:
    """List every claim in the queue, oldest submitted first."""
    with db.connection() as conn:
        rows = conn.execute(select(db.claims.c.claim_id, db.claims.c.status))
        statuses = {claim_id: status for claim_id, status in rows}
    return [
        {
            "claim_id": claim_id,
            "claim_type": CLAIMS[claim_id]["claim_type"],
            "summary": CLAIMS[claim_id]["summary"],
            "amount_claimed": CLAIMS[claim_id]["amount_claimed"],
            "status": statuses[claim_id],
        }
        for claim_id in CLAIM_IDS_BY_SUBMITTED_ON
    ]


def get_full(claim_id: str) -> dict[str, Any]:
    """Return a claim in full, with its policy and its customer's claim history."""
    row = get_row(claim_id)
    claim = {k: v for k, v in CLAIMS[claim_id].items() if k != "status"}
    return {
        **claim,
        **row,
        "policy": POLICIES[claim["policy_id"]],
        "customer_previous_claims": CUSTOMERS[claim["customer_id"]]["previous_claims"],
    }


def decide(
    claim_id: str,
    decision: str,
    payout: Decimal,
    reason: str,
    policy_reference: str,
) -> dict[str, Any]:
    """Record a claim's one decision; an approval over the limit needs a sign-off."""
    get_row(claim_id)
    over_limit = decision == "approve" and payouts.needs_sign_off(payout)
    with db.connection() as conn:
        decided = conn.execute(
            update(db.claims)
            .where(
                db.claims.c.claim_id == claim_id,
                db.claims.c.status.in_(["waiting", "in progress"]),
            )
            .values(
                status="waiting for sign-off" if over_limit else "decided",
                decision=decision,
                payout_cents=money.to_cents(payout),
                reason=reason,
                policy_reference=policy_reference,
                decided_on=db.now(),
                over_approval_limit=int(over_limit),
            )
        )
    if decided.rowcount == 0:
        raise Conflict("Claim has already been decided")
    return get_row(claim_id)


def record_step(claim_id: str, text: str) -> None:
    """Record one step of the agent's work; a waiting claim becomes in progress."""
    get_row(claim_id)
    with db.connection() as conn:
        conn.execute(
            insert(db.claim_steps).values(
                claim_id=claim_id, recorded_on=db.now(), text=text
            )
        )
        conn.execute(
            update(db.claims)
            .where(db.claims.c.claim_id == claim_id, db.claims.c.status == "waiting")
            .values(status="in progress")
        )


def list_steps(claim_id: str) -> list[dict[str, Any]]:
    """List a claim's steps, in the order they happened."""
    get_row(claim_id)
    with db.connection() as conn:
        rows = conn.execute(
            select(db.claim_steps.c.recorded_on, db.claim_steps.c.text)
            .where(db.claim_steps.c.claim_id == claim_id)
            .order_by(db.claim_steps.c.id)
        )
        return [dict(row._mapping) for row in rows]


def sign_off(claim_id: str, handler_id: str) -> dict[str, Any]:
    """Have a handler sign off an over-limit approval."""
    if get_row(claim_id)["status"] != "waiting for sign-off":
        raise Conflict("Claim is not waiting for sign-off")
    handler = data.handler(handler_id)
    if handler is None or not handler["can_approve_over_limit"]:
        raise Conflict("This handler cannot sign off this claim")
    with db.connection() as conn:
        conn.execute(
            update(db.claims)
            .where(db.claims.c.claim_id == claim_id)
            .values(status="decided", signed_off_by=handler_id, signed_off_on=db.now())
        )
    return get_row(claim_id)


def _why_not_payable(row: dict[str, Any], amount: Decimal) -> str:
    if row["paid_amount"] is not None:
        return "Claim has already been paid"
    if row["decision"] != "approve":
        return "Claim is not approved"
    if row["over_approval_limit"] and row["signed_off_by"] is None:
        return "Claim needs a handler's sign-off before payment"
    return f"Payment must be the approved payout of {row['payout']}, not {amount}"


def pay(claim_id: str, amount: Decimal) -> dict[str, Any]:
    """Pay an approved claim its payout, once, after any required sign-off."""
    row = get_row(claim_id)
    cents = money.to_cents(amount)
    with db.connection() as conn:
        paid = conn.execute(
            update(db.claims)
            .where(
                db.claims.c.claim_id == claim_id,
                db.claims.c.decision == "approve",
                db.claims.c.paid_cents.is_(None),
                db.claims.c.payout_cents == cents,
                or_(
                    db.claims.c.over_approval_limit == 0,
                    db.claims.c.signed_off_by.is_not(None),
                ),
            )
            .values(paid_cents=cents, paid_on=db.now())
        )
    if paid.rowcount == 0:
        raise Conflict(_why_not_payable(row, amount))
    return get_row(claim_id)


def start_work(claim_id: str) -> dict[str, Any]:
    """Mark a waiting claim as in progress, before the agent starts on it."""
    if get_row(claim_id)["status"] != "waiting":
        raise Conflict("Claim is not waiting")
    with db.connection() as conn:
        conn.execute(
            update(db.claims)
            .where(db.claims.c.claim_id == claim_id)
            .values(status="in progress")
        )
    return get_row(claim_id)


def requeue(claim_id: str) -> dict[str, Any]:
    """Put a stuck claim back in the queue as waiting, to start afresh."""
    if get_row(claim_id)["status"] not in ("waiting", "in progress"):
        raise Conflict("Claim is already decided")
    with db.connection() as conn:
        conn.execute(
            update(db.claims)
            .where(db.claims.c.claim_id == claim_id)
            .values(status="waiting", thread=db.claims.c.thread + 1)
        )
    return get_row(claim_id)
