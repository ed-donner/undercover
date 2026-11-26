"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

from backend.db import DATA, connect, load
from backend.models import (
    AddOn,
    Claim,
    ClaimSummary,
    Decision,
    Handler,
    Payment,
    Plan,
    Policy,
    PreviousClaim,
    Text,
)

app = FastAPI(title="UnderCover")

PLANS = json.loads((DATA / "plans.json").read_text())
INSTRUCTIONS = Path(__file__).parent / "instructions.md"


def database() -> Iterator[sqlite3.Connection]:
    """Yield a connection to the database for one request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


Db = Annotated[sqlite3.Connection, Depends(database)]


def claim_row(db: sqlite3.Connection, claim_id: str) -> sqlite3.Row:
    """Fetch a claim's row, or raise 404."""
    row = db.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"No claim {claim_id}")
    return row


def customer(db: sqlite3.Connection, customer_id: str) -> dict:
    """Fetch a customer's record."""
    row = db.execute(
        "SELECT data FROM customers WHERE customer_id = ?", (customer_id,)
    ).fetchone()
    return json.loads(row["data"])


def to_claim(db: sqlite3.Connection, row: sqlite3.Row) -> Claim:
    """Build the full claim from its row."""
    decision = None
    if row["decision"]:
        decision = Decision(
            decision=row["decision"],
            payout=row["payout"],
            reason=row["reason"],
            policy_section=row["policy_section"],
        )
    payment = None
    if row["paid_amount"] is not None:
        payment = Payment(amount=row["paid_amount"], signed_off_by=row["signed_off_by"])
    data = json.loads(row["data"])
    data.pop("status")
    return Claim(
        **data,
        customer_name=customer(db, row["customer_id"])["name"],
        status=row["status"],
        decision=decision,
        payment=payment,
    )


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims(db: Db) -> list[ClaimSummary]:
    """List every claim in queue order."""
    rows = db.execute("SELECT * FROM claims ORDER BY position").fetchall()
    summaries = []
    for row in rows:
        data = json.loads(row["data"])
        summaries.append(
            ClaimSummary(
                claim_id=row["claim_id"],
                customer_name=customer(db, row["customer_id"])["name"],
                claim_type=data["claim_type"],
                summary=data["summary"],
                submitted_on=data["submitted_on"],
                amount_claimed=data["amount_claimed"],
                status=row["status"],
                decision=row["decision"],
                payout=row["payout"],
            )
        )
    return summaries


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, db: Db) -> Claim:
    """Get a claim in full, with its decision and payment."""
    return to_claim(db, claim_row(db, claim_id))


@app.get("/api/claims/{claim_id}/policy", operation_id="get_policy")
def get_policy(claim_id: str, db: Db) -> Policy:
    """Get the policy a claim is made under, with its plan and add-ons."""
    row = claim_row(db, claim_id)
    policy = json.loads(
        db.execute(
            "SELECT data FROM policies WHERE policy_id = ?", (row["policy_id"],)
        ).fetchone()["data"]
    )
    plan = next(p for p in PLANS["plans"] if p["plan"] == policy["plan"])
    add_ons = [a for a in PLANS["add_ons"] if a["add_on"] in policy["add_ons"]]
    return Policy(
        **{**policy, "plan": Plan(**plan), "add_ons": [AddOn(**a) for a in add_ons]}
    )


@app.get("/api/claims/{claim_id}/history", operation_id="get_claim_history")
def get_claim_history(claim_id: str, db: Db) -> list[PreviousClaim]:
    """Get the customer's earlier claims, without their contact details."""
    row = claim_row(db, claim_id)
    return [
        PreviousClaim(**c) for c in customer(db, row["customer_id"])["previous_claims"]
    ]


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording() -> Text:
    """Get the policy wording, the contract with the customer."""
    return Text(text=(DATA / "policy_wording.md").read_text())


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> Text:
    """Get the UnderCover Agent's instructions."""
    return Text(text=INSTRUCTIONS.read_text())


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers() -> list[Handler]:
    """List the claims handlers who can sign off payments."""
    return [Handler(**h) for h in load("handlers.json")]
