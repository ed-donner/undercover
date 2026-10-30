"""A claim's state: its row, its steps, its sign-off and its payment."""

from typing import Any

from backend import data, db
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
    return dict(row)


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
    claim_id: str, decision: str, payout: float, reason: str, policy_reference: str
) -> dict[str, Any]:
    """Record a decision; an approval over the limit waits for a handler's sign-off."""
    get_row(claim_id)
    over_limit = decision == "approve" and payout > data.PAYOUT_APPROVAL_LIMIT
    with db.connection() as conn:
        conn.execute(
            """UPDATE claims SET status = ?, decision = ?, payout = ?, reason = ?,
               policy_reference = ?, decided_on = ?, over_approval_limit = ?,
               signed_off_by = NULL, signed_off_on = NULL,
               paid_amount = NULL, paid_on = NULL
               WHERE claim_id = ?""",
            (
                "waiting for sign-off" if over_limit else "decided",
                decision,
                payout,
                reason,
                policy_reference,
                db.now(),
                int(over_limit),
                claim_id,
            ),
        )
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


def pay(claim_id: str, amount: float) -> dict[str, Any]:
    """Pay an approved claim, once any required sign-off is given."""
    row = get_row(claim_id)
    if row["decision"] != "approve":
        raise Conflict("Claim is not approved")
    if row["over_approval_limit"] and row["signed_off_by"] is None:
        raise Conflict("Claim needs a handler's sign-off before payment")
    with db.connection() as conn:
        conn.execute(
            "UPDATE claims SET paid_amount = ?, paid_on = ? WHERE claim_id = ?",
            (amount, db.now(), claim_id),
        )
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
