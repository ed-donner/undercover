"""A claim's state: its row, its steps, its sign-off and its payment."""

from decimal import Decimal
from typing import Any

from sqlalchemy import and_, insert, or_, select, update

from backend import data, db, money, payouts, tables
from backend.data import CLAIM_IDS_BY_SUBMITTED_ON, CLAIMS, CUSTOMERS, POLICIES
from backend.errors import Conflict, NotFound


def get_row(claim_id: str) -> dict[str, Any]:
    """Return a claim's mutable state, or raise NotFound."""
    with db.connection() as conn:
        row = conn.execute(
            select(*tables.STATE_COLUMNS).where(tables.claims.c.claim_id == claim_id)
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
        rows = conn.execute(select(tables.claims.c.claim_id, tables.claims.c.status))
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
    """Record a claim's one decision; an approval over the limit needs a sign-off.

    Repeating the decision already recorded is done, not an error.
    """
    get_row(claim_id)
    over_limit = decision == "approve" and payouts.needs_sign_off(payout)
    with db.connection() as conn:
        decided = conn.execute(
            update(tables.claims)
            .where(
                tables.claims.c.claim_id == claim_id,
                tables.claims.c.decision.is_(None),
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
    row = get_row(claim_id)
    if decided.rowcount == 0 and (row["decision"], row["payout"]) != (decision, payout):
        raise Conflict("Claim has already been decided")
    return row


def record_step(claim_id: str, text: str) -> None:
    """Record one step of the agent's work; a waiting claim becomes in progress."""
    get_row(claim_id)
    with db.connection() as conn:
        conn.execute(
            insert(tables.claim_steps).values(
                claim_id=claim_id, recorded_on=db.now(), text=text
            )
        )
        conn.execute(
            update(tables.claims)
            .where(
                tables.claims.c.claim_id == claim_id,
                tables.claims.c.status == "waiting",
            )
            .values(status="in progress")
        )


def list_steps(claim_id: str) -> list[dict[str, Any]]:
    """List a claim's steps, in the order they happened."""
    get_row(claim_id)
    with db.connection() as conn:
        rows = conn.execute(
            select(tables.claim_steps.c.recorded_on, tables.claim_steps.c.text)
            .where(tables.claim_steps.c.claim_id == claim_id)
            .order_by(tables.claim_steps.c.id)
        )
        return [dict(row._mapping) for row in rows]


def sign_off(claim_id: str, handler_id: str) -> dict[str, Any]:
    """Have a handler sign off an over-limit approval; the agent then pays it."""
    row = get_row(claim_id)
    if row["signed_off_by"] == handler_id:
        return row
    if row["status"] != "waiting for sign-off":
        raise Conflict("Claim is not waiting for sign-off")
    handler = data.handler(handler_id)
    if handler is None or not handler["can_approve_over_limit"]:
        raise Conflict("This handler cannot sign off this claim")
    with db.connection() as conn:
        conn.execute(
            update(tables.claims)
            .where(tables.claims.c.claim_id == claim_id)
            .values(
                status="in progress", signed_off_by=handler_id, signed_off_on=db.now()
            )
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
    """Pay an approved claim its payout, once, after any required sign-off.

    Repeating a payment already made is done, not an error.
    """
    row = get_row(claim_id)
    if row["paid_amount"] == amount:
        return row
    cents = money.to_cents(amount)
    with db.connection() as conn:
        paid = conn.execute(
            update(tables.claims)
            .where(
                tables.claims.c.claim_id == claim_id,
                tables.claims.c.decision == "approve",
                tables.claims.c.paid_cents.is_(None),
                tables.claims.c.payout_cents == cents,
                or_(
                    tables.claims.c.over_approval_limit == 0,
                    tables.claims.c.signed_off_by.is_not(None),
                ),
            )
            .values(status="decided", paid_cents=cents, paid_on=db.now())
        )
    if paid.rowcount == 0:
        raise Conflict(_why_not_payable(row, amount))
    return get_row(claim_id)


def list_unfinished() -> list[str]:
    """List the claims the agent must carry on with: stopped, or ready to pay."""
    payable = and_(
        tables.claims.c.decision == "approve",
        tables.claims.c.paid_cents.is_(None),
        or_(
            tables.claims.c.over_approval_limit == 0,
            tables.claims.c.signed_off_by.is_not(None),
        ),
    )
    with db.connection() as conn:
        rows = conn.execute(
            select(tables.claims.c.claim_id)
            .where(or_(tables.claims.c.status == "in progress", payable))
            .order_by(tables.claims.c.claim_id)
        )
        return [claim_id for (claim_id,) in rows]


def start_work(claim_id: str) -> dict[str, Any]:
    """Mark a waiting claim as in progress, before the agent starts on it."""
    if get_row(claim_id)["status"] != "waiting":
        raise Conflict("Claim is not waiting")
    with db.connection() as conn:
        conn.execute(
            update(tables.claims)
            .where(tables.claims.c.claim_id == claim_id)
            .values(status="in progress")
        )
    return get_row(claim_id)


def requeue(claim_id: str) -> dict[str, Any]:
    """Put a stuck claim back in the queue as waiting, to start afresh."""
    row = get_row(claim_id)
    if row["status"] not in ("waiting", "in progress") or row["decision"]:
        raise Conflict("Claim is already decided")
    with db.connection() as conn:
        conn.execute(
            update(tables.claims)
            .where(tables.claims.c.claim_id == claim_id)
            .values(status="waiting", thread=tables.claims.c.thread + 1)
        )
    return get_row(claim_id)
