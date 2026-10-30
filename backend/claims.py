"""A claim's state: its row, its steps, its sign-off and its payment."""

from decimal import Decimal
from typing import Any

from backend import data, db, money
from backend.data import CLAIM_IDS_BY_SUBMITTED_ON, CLAIMS, CUSTOMERS, POLICIES
from backend.errors import Conflict, NotFound


def get_row(claim_id: str) -> dict[str, Any]:
    """Return a claim's mutable state, or raise NotFound."""
    with db.connection() as conn:
        row = conn.execute(
            "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
        ).fetchone()
    if row is None:
        raise NotFound(f"No claim {claim_id}")
    return _with_dollars(dict(row))


def _with_dollars(row: dict[str, Any]) -> dict[str, Any]:
    """Swap the `*_cents` columns for `Decimal` dollars, under the wire names."""
    for column, name in (("payout_cents", "payout"), ("paid_cents", "paid_amount")):
        cents = row.pop(column)
        row[name] = None if cents is None else money.from_cents(cents)
    return row


def list_summaries() -> list[dict[str, Any]]:
    """List every claim in the queue, oldest submitted first."""
    with db.connection() as conn:
        statuses = {
            row["claim_id"]: row["status"]
            for row in conn.execute("SELECT claim_id, status FROM claims")
        }
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
    over_limit = decision == "approve" and payout > data.PAYOUT_APPROVAL_LIMIT
    with db.connection() as conn:
        decided = conn.execute(
            """UPDATE claims SET status = ?, decision = ?, payout_cents = ?,
               reason = ?, policy_reference = ?, decided_on = ?,
               over_approval_limit = ?
               WHERE claim_id = ? AND status IN ('waiting', 'in progress')""",
            (
                "waiting for sign-off" if over_limit else "decided",
                decision,
                money.to_cents(payout),
                reason,
                policy_reference,
                db.now(),
                int(over_limit),
                claim_id,
            ),
        )
    if decided.rowcount == 0:
        raise Conflict("Claim has already been decided")
    return get_row(claim_id)


def record_step(claim_id: str, text: str) -> None:
    """Record one step of the agent's work; a waiting claim becomes in progress."""
    get_row(claim_id)
    with db.connection() as conn:
        conn.execute(
            "INSERT INTO claim_steps (claim_id, recorded_on, text) VALUES (?, ?, ?)",
            (claim_id, db.now(), text),
        )
        conn.execute(
            "UPDATE claims SET status = 'in progress' "
            "WHERE claim_id = ? AND status = 'waiting'",
            (claim_id,),
        )


def list_steps(claim_id: str) -> list[dict[str, Any]]:
    """List a claim's steps, in the order they happened."""
    get_row(claim_id)
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT recorded_on, text FROM claim_steps WHERE claim_id = ? ORDER BY id",
            (claim_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def sign_off(claim_id: str, handler_id: str) -> dict[str, Any]:
    """Have a handler sign off an over-limit approval."""
    if get_row(claim_id)["status"] != "waiting for sign-off":
        raise Conflict("Claim is not waiting for sign-off")
    handler = data.handler(handler_id)
    if handler is None or not handler["can_approve_over_limit"]:
        raise Conflict("This handler cannot sign off this claim")
    with db.connection() as conn:
        conn.execute(
            "UPDATE claims SET status = 'decided', signed_off_by = ?, "
            "signed_off_on = ? WHERE claim_id = ?",
            (handler_id, db.now(), claim_id),
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
    with db.connection() as conn:
        paid = conn.execute(
            """UPDATE claims SET paid_cents = ?, paid_on = ?
               WHERE claim_id = ? AND decision = 'approve'
               AND paid_cents IS NULL AND payout_cents = ?
               AND (over_approval_limit = 0 OR signed_off_by IS NOT NULL)""",
            (money.to_cents(amount), db.now(), claim_id, money.to_cents(amount)),
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
            "UPDATE claims SET status = 'in progress' WHERE claim_id = ?", (claim_id,)
        )
    return get_row(claim_id)


def requeue(claim_id: str) -> dict[str, Any]:
    """Put a stuck claim back in the queue as waiting."""
    if get_row(claim_id)["status"] not in ("waiting", "in progress"):
        raise Conflict("Claim is already decided")
    with db.connection() as conn:
        conn.execute(
            "UPDATE claims SET status = 'waiting' WHERE claim_id = ?", (claim_id,)
        )
    return get_row(claim_id)
