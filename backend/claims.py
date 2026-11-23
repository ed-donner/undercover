"""Reading claims and the records around them."""

import json
import sqlite3

from fastapi import HTTPException

from backend.models import (
    Claim,
    ClaimContext,
    ClaimDetail,
    ClaimState,
    ClaimSummary,
    Customer,
    Handler,
    PlanLimits,
    Policy,
)


def load(conn: sqlite3.Connection, table: str, key: str, value: str) -> dict:
    """Return one record from a table, or raise a 404."""
    row = conn.execute(
        f"SELECT data FROM {table} WHERE {key} = ?",  # noqa: S608
        (value,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"No {table[:-1]} {value}")
    return json.loads(row["data"])


def claim_state(conn: sqlite3.Connection, claim_id: str) -> ClaimState:
    """Work out where a claim stands from what is recorded about it."""
    return "waiting"


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
    return ClaimDetail(**context.model_dump(), state=claim_state(conn, claim_id))


def list_summaries(conn: sqlite3.Connection) -> list[ClaimSummary]:
    """Return every claim in the queue, in claim id order."""
    names = {
        row["customer_id"]: json.loads(row["data"])["name"]
        for row in conn.execute("SELECT customer_id, data FROM customers")
    }
    summaries = []
    for row in conn.execute("SELECT claim_id, data FROM claims ORDER BY claim_id"):
        claim = json.loads(row["data"])
        summaries.append(
            ClaimSummary(
                **claim,
                customer_name=names[claim["customer_id"]],
                state=claim_state(conn, row["claim_id"]),
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
