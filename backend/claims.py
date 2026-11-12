"""A claim's state: its row, its steps, its sign-off and its payment."""

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, insert, or_, select, update

from backend import db, money, payouts, reference, tables
from backend.errors import Conflict, NotFound
from backend.statuses import ClaimStatus

LEASE_SECONDS = 30


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
    columns = tables.claims.c
    with db.connection() as conn:
        rows = conn.execute(
            select(
                columns.claim_id,
                columns.claim_type,
                columns.summary,
                columns.amount_claimed_cents,
                columns.status,
            ).order_by(columns.submitted_on, columns.claim_id)
        )
        return [money.dollar_fields(dict(row._mapping)) for row in rows]


def get_full(claim_id: str) -> dict[str, Any]:
    """Return a claim in full, with its policy and its customer's claim history."""
    row = get_row(claim_id)
    with db.connection() as conn:
        content = conn.execute(
            select(*tables.CONTENT_COLUMNS).where(tables.claims.c.claim_id == claim_id)
        ).one()
    claim = money.dollar_fields(dict(content._mapping))
    return {
        **claim,
        **row,
        "policy": reference.policy(claim["policy_id"]),
        "customer_previous_claims": reference.customer(claim["customer_id"])[
            "previous_claims"
        ],
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
                status=ClaimStatus.WAITING_FOR_SIGN_OFF
                if over_limit
                else ClaimStatus.DECIDED,
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
                tables.claims.c.status == ClaimStatus.WAITING,
            )
            .values(status=ClaimStatus.IN_PROGRESS)
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
    if row["status"] != ClaimStatus.WAITING_FOR_SIGN_OFF:
        raise Conflict("Claim is not waiting for sign-off")
    handler = reference.handler(handler_id)
    if handler is None or not handler["can_approve_over_limit"]:
        raise Conflict("This handler cannot sign off this claim")
    with db.connection() as conn:
        conn.execute(
            update(tables.claims)
            .where(tables.claims.c.claim_id == claim_id)
            .values(
                status=ClaimStatus.IN_PROGRESS,
                signed_off_by=handler_id,
                signed_off_on=db.now(),
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
            .values(status=ClaimStatus.DECIDED, paid_cents=cents, paid_on=db.now())
        )
    if paid.rowcount == 0:
        raise Conflict(_why_not_payable(row, amount))
    return get_row(claim_id)


def acquire_lease(claim_id: str, owner: str) -> int:
    """Lease a claim to an agent for a short time; holding it again renews it.

    Raises Conflict while another agent holds a lease that has not run out.
    Returns the length of the lease in seconds.
    """
    get_row(claim_id)
    columns = tables.claims.c
    with db.connection() as conn:
        leased = conn.execute(
            update(tables.claims)
            .where(
                columns.claim_id == claim_id,
                or_(
                    columns.lease_owner.is_(None),
                    columns.lease_owner == owner,
                    columns.lease_expires_on < db.now(),
                ),
            )
            .values(lease_owner=owner, lease_expires_on=db.now(LEASE_SECONDS))
        )
    if leased.rowcount == 0:
        raise Conflict("Claim is being worked by another agent")
    return LEASE_SECONDS


def release_lease(claim_id: str, owner: str) -> None:
    """Give up a lease, if this agent still holds it."""
    get_row(claim_id)
    columns = tables.claims.c
    with db.connection() as conn:
        conn.execute(
            update(tables.claims)
            .where(columns.claim_id == claim_id, columns.lease_owner == owner)
            .values(lease_owner=None, lease_expires_on=None)
        )


def list_unfinished() -> list[str]:
    """List the claims to carry on with: stopped or ready to pay, and not leased."""
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
            .where(
                or_(tables.claims.c.status == ClaimStatus.IN_PROGRESS, payable),
                or_(
                    tables.claims.c.lease_expires_on.is_(None),
                    tables.claims.c.lease_expires_on < db.now(),
                ),
            )
            .order_by(tables.claims.c.claim_id)
        )
        return [claim_id for (claim_id,) in rows]


def start_work(claim_id: str, launch: Callable[[str], None]) -> dict[str, Any]:
    """Launch the agent on a waiting claim, then mark it in progress.

    If the launch fails the claim stays waiting.
    """
    if get_row(claim_id)["status"] != ClaimStatus.WAITING:
        raise Conflict("Claim is not waiting")
    launch(claim_id)
    with db.connection() as conn:
        conn.execute(
            update(tables.claims)
            .where(tables.claims.c.claim_id == claim_id)
            .values(status=ClaimStatus.IN_PROGRESS)
        )
    return get_row(claim_id)


def requeue(claim_id: str) -> dict[str, Any]:
    """Put a stuck claim back in the queue as waiting, to start afresh."""
    row = get_row(claim_id)
    if (
        row["status"] not in (ClaimStatus.WAITING, ClaimStatus.IN_PROGRESS)
        or row["decision"]
    ):
        raise Conflict("Claim is already decided")
    with db.connection() as conn:
        conn.execute(
            update(tables.claims)
            .where(tables.claims.c.claim_id == claim_id)
            .values(status=ClaimStatus.WAITING, thread=tables.claims.c.thread + 1)
        )
    return get_row(claim_id)
