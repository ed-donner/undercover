"""Reading claims and the records around them."""

import json
import sqlite3

from backend.models import (
    Claim,
    ClaimContext,
    ClaimDetail,
    ClaimSummary,
    Customer,
    Handler,
    PlanLimits,
    Policy,
)
from backend.records import (
    claim_state,
    decision_record,
    dollars,
    find_decision,
    find_payment,
    load,
    payment_record,
)


def get_context(conn: sqlite3.Connection, claim_id: str) -> ClaimContext:
    """Return a claim with its policy, the plan's limits and the customer."""
    claim = load(conn, "claims", "claim_id", claim_id)
    policy = load(conn, "policies", "policy_id", claim["policy_id"])
    return ClaimContext(
        claim=Claim(**claim),
        policy=Policy(**policy),
        plan=PlanLimits(**load(conn, "plans", "plan", policy["plan"])),
        customer=Customer(
            **load(conn, "customers", "customer_id", claim["customer_id"])
        ),
    )


def get_detail(conn: sqlite3.Connection, claim_id: str) -> ClaimDetail:
    """Return a claim in full, with where it stands."""
    context = get_context(conn, claim_id)
    decision = find_decision(conn, claim_id)
    payment = find_payment(conn, claim_id)
    return ClaimDetail(
        **context.model_dump(),
        state=claim_state(conn, claim_id),
        decision=decision_record(decision) if decision else None,
        payment=payment_record(payment) if payment else None,
    )


def list_summaries(conn: sqlite3.Connection) -> list[ClaimSummary]:
    """Return every claim in the queue, in claim id order."""
    names = {
        row["customer_id"]: json.loads(row["data"])["name"]
        for row in conn.execute("SELECT customer_id, data FROM customers")
    }
    summaries = []
    for row in conn.execute("SELECT claim_id, data FROM claims ORDER BY claim_id"):
        claim = json.loads(row["data"])
        decision = find_decision(conn, row["claim_id"])
        summaries.append(
            ClaimSummary(
                **claim,
                customer_name=names[claim["customer_id"]],
                state=claim_state(conn, row["claim_id"]),
                decision=decision["decision"] if decision else None,
                payout=dollars(decision["payout_cents"]) if decision else None,
            )
        )
    return summaries


def list_handlers(conn: sqlite3.Connection) -> list[Handler]:
    """Return the claims handlers."""
    rows = conn.execute("SELECT data FROM handlers ORDER BY handler_id")
    return [Handler(**json.loads(row["data"])) for row in rows]


def policy_wording(conn: sqlite3.Connection) -> str:
    """Return the text of the policy wording."""
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'policy_wording'"
    ).fetchone()
    return row["value"]
